import uuid
from decimal import Decimal
import pytest
import pymupdf
from sqlalchemy import select

from app.config import settings
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.export import ShipmentExportRecord
from app.models.field_review import DocumentFieldReview
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.shipment import Shipment, ShipmentStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.user import User, UserRole
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.security import hash_password, create_access_token
from app.services.ai.base import ProviderConfigurationError
from app.services.simulation.engine import (
    SimulationEngine,
    create_synthetic_pdf,
    SCENARIOS_CATALOG,
)


@pytest.fixture
async def simulation_users(db_session):
    """Creates an executive and a manager user for simulation tests."""
    exec_user = User(
        email="test_exec_sim@cargolens.in",
        full_name="Simulation Executive",
        hashed_password=hash_password("TestExecPass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr_user = User(
        email="test_mgr_sim@cargolens.in",
        full_name="Simulation Manager",
        hashed_password=hash_password("TestMgrPass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add(exec_user)
    db_session.add(mgr_user)
    await db_session.commit()
    await db_session.refresh(exec_user)
    await db_session.refresh(mgr_user)
    return exec_user, mgr_user


@pytest.mark.asyncio
async def test_create_synthetic_pdf_validity():
    """Verifies that synthetic PDFs are compliant, valid binary documents with text layer."""
    pdf_bytes = create_synthetic_pdf(
        "Commercial Invoice",
        [
            "Invoice Number: INV-TEST-001",
            "Seller: Acme Exports Ltd",
            "Buyer: Global Importers India",
            "Gross Weight: 5,000.00 KG",
        ],
    )
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 500

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) == 1
    text = doc[0].get_text()
    assert "INV-TEST-001" in text
    assert "Acme Exports Ltd" in text
    doc.close()


@pytest.mark.asyncio
async def test_simulation_provider_selection():
    """Verifies provider selection logic and missing Anthropic API key exception."""
    fixture_provider = SimulationEngine.get_provider("fixture")
    assert fixture_provider.provider_name == "development-fixture"
    assert fixture_provider.model_name == "fixture-v1"

    old_key = settings.ANTHROPIC_API_KEY
    settings.ANTHROPIC_API_KEY = None
    try:
        with pytest.raises(ProviderConfigurationError) as exc_info:
            SimulationEngine.get_provider("claude")
        assert "Anthropic API key is not configured" in str(exc_info.value)
    finally:
        settings.ANTHROPIC_API_KEY = old_key


@pytest.mark.asyncio
async def test_scenario_a_complete_workflow(db_session, simulation_users):
    """
    Verifies Scenario A executes end-to-end through real services:
    - Generates 3 synthetic PDFs (CI, PL, BL)
    - Queues and processes OCR jobs
    - Executes structured extraction
    - Executes cross-document validation (11/11 pass)
    - Strictly halts at REVIEW_REQUIRED, awaiting genuine human review
    - Does NOT automatically verify or export without real human interaction.
    """
    exec_user, mgr_user = simulation_users
    res = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="COMPLETE_WORKFLOW",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )

    assert res["scenario_type"] == "COMPLETE_WORKFLOW"
    assert res["shipment_number"] == "SHP-DEMO-001"
    assert res["status"] == "REVIEW_REQUIRED"
    assert len(res["documents"]) == 3
    assert res["validation"]["total_rules"] == 11
    assert res["validation"]["passed_count"] == 11
    assert res["validation"]["failed_count"] == 0
    assert res["validation"]["missing_data_count"] == 0
    assert res["validation"]["has_blocking_failures"] is False
    assert res["human_reviews_count"] == 0
    assert res["verification_ready"] is False
    assert res["export"] is None

    # Verify that human reviewer must genuinely confirm mandatory fields before verification
    from app.services.export.csv_exporter import CSVExportService, ExportTemplateType
    from app.models.field_review import DocumentFieldReview, FieldReviewActionType
    from app.api.v1.workflow import evaluate_readiness

    shipment_stmt = select(Shipment).where(Shipment.id == res["shipment_id"])
    shipment = (await db_session.execute(shipment_stmt)).scalar_one()

    # Before human review: evaluate_readiness reports unreviewed mandatory fields
    readiness_before = await evaluate_readiness(shipment, db_session)
    assert readiness_before.is_ready is False
    assert len(readiness_before.unreviewed_mandatory_fields) > 0
    assert readiness_before.all_mandatory_fields_reviewed is False

    # Human reviewer performs explicit confirmations on mandatory fields
    doc_ids = [d["id"] for d in res["documents"]]
    reviews_to_add = [
        (doc_ids[0], "invoice_number", "INV-2026-9011"),
        (doc_ids[0], "invoice_date", "2026-10-18"),
        (doc_ids[0], "seller_name", "Apex Solar Vietnam Ltd."),
        (doc_ids[0], "buyer_name", "Apex Solar Technologies India Pvt Ltd"),
        (doc_ids[0], "grand_total", "33600.00"),
        (doc_ids[0], "currency", "USD"),
        (doc_ids[1], "invoice_reference", "INV-2026-9011"),
        (doc_ids[1], "package_count", "60"),
        (doc_ids[1], "gross_weight_kg", "14400.00"),
        (doc_ids[2], "bl_number", "BL-2026-9011"),
        (doc_ids[2], "shipper_name", "Apex Solar Vietnam Ltd."),
        (doc_ids[2], "consignee_name", "Apex Solar Technologies India Pvt Ltd"),
        (doc_ids[2], "gross_weight_kg", "14400.00"),
    ]
    for doc_id, f_name, f_val in reviews_to_add:
        r = DocumentFieldReview(
            document_id=uuid.UUID(doc_id),
            shipment_id=shipment.id,
            field_name=f_name,
            action=FieldReviewActionType.CONFIRMED,
            original_value=f_val,
            reviewer_id=mgr_user.id,
        )
        db_session.add(r)
    await db_session.commit()

    # Now readiness re-check passes
    readiness_after = await evaluate_readiness(shipment, db_session)
    assert readiness_after.is_ready is True

    # Manager explicitly verifies shipment
    shipment.status = ShipmentStatus.VERIFIED
    await db_session.commit()

    # Manager explicitly exports shipment
    export_rec, _ = await CSVExportService.generate_export(
        session=db_session,
        shipment_id=shipment.id,
        current_user=mgr_user,
        template_name=ExportTemplateType.STANDARD_CUSTOMS_CLEARANCE.value,
    )
    assert export_rec.export_status.value == "COMPLETED"
    assert export_rec.sha256_checksum is not None


@pytest.mark.asyncio
async def test_scenario_b_weight_discrepancy(db_session, simulation_users):
    """
    Verifies Scenario B (SHP-24811):
    - CI Gross Weight: 3,120 kg
    - PL Gross Weight: 3,165 kg
    - Validation identifies 45.00 kg difference
    - Status is REVIEW_REQUIRED, verification is blocked.
    """
    exec_user, mgr_user = simulation_users
    res = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="WEIGHT_DISCREPANCY",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )

    assert res["scenario_type"] == "WEIGHT_DISCREPANCY"
    assert res["shipment_number"] == "SHP-24811"
    assert res["status"] == "REVIEW_REQUIRED"
    assert res["validation"]["failed_count"] >= 1
    assert res["validation"]["has_blocking_failures"] is True
    assert "45.00 kg" in res["validation"]["notable_discrepancy"]
    assert res["export"] is None


@pytest.mark.asyncio
async def test_scenario_c_missing_financial_information(db_session, simulation_users):
    """
    Verifies Scenario C (SHP-24812):
    - Invoice grand total omitted from document
    - Arithmetic sum (EUR 7,650) is protected and not fabricated as grand total
    - Grand total remains None in extraction
    - Status is REVIEW_REQUIRED.
    """
    exec_user, mgr_user = simulation_users
    res = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="MISSING_FINANCIAL",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )

    assert res["scenario_type"] == "MISSING_FINANCIAL"
    assert res["shipment_number"] == "SHP-24812"
    assert res["status"] == "REVIEW_REQUIRED"

    # Query extraction to confirm grand_total is null
    ci_doc_id = uuid.UUID(res["documents"][0]["id"])
    ext_stmt = select(StructuredExtraction).where(StructuredExtraction.document_id == ci_doc_id)
    ext = (await db_session.execute(ext_stmt)).scalar_one_or_none()
    assert ext is not None
    assert ext.extracted_data["grand_total"]["value"] is None


@pytest.mark.asyncio
async def test_scenario_d_low_confidence(db_session, simulation_users):
    """
    Verifies Scenario D (SHP-DEMO-LOWCONF):
    - Simulated optical noise triggers low confidence (< 0.70)
    - Review required for executive.
    """
    exec_user, mgr_user = simulation_users
    res = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="LOW_CONFIDENCE",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )

    assert res["scenario_type"] == "LOW_CONFIDENCE"
    assert res["status"] == "REVIEW_REQUIRED"
    assert res["extraction"] is not None
    assert len(res["extraction"]["low_confidence_fields"]) > 0


@pytest.mark.asyncio
async def test_scenario_e_incomplete_set(db_session, simulation_users):
    """
    Verifies Scenario E (SHP-DEMO-INCOMPLETE):
    - Only CI uploaded (PL and BL missing)
    - Status remains in DOCUMENTS_PENDING.
    """
    exec_user, mgr_user = simulation_users
    res = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="INCOMPLETE_SET",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )

    assert res["scenario_type"] == "INCOMPLETE_SET"
    assert res["status"] == "DOCUMENTS_PENDING"
    assert len(res["documents"]) == 1


@pytest.mark.asyncio
async def test_simulation_idempotency_and_reset(db_session, simulation_users):
    """Verifies that running simulation repeatedly cleans up previous runs cleanly."""
    exec_user, mgr_user = simulation_users

    # Run Scenario B twice
    res1 = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="WEIGHT_DISCREPANCY",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )
    res2 = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="WEIGHT_DISCREPANCY",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )
    assert res1["shipment_number"] == res2["shipment_number"]

    # Verify only 1 shipment with SHP-24811 exists in DB
    cnt_stmt = select(Shipment).where(Shipment.shipment_number == "SHP-24811")
    shipments = (await db_session.execute(cnt_stmt)).scalars().all()
    assert len(shipments) == 1

    # Reset
    cleaned = await SimulationEngine.clean_all_demo(db_session)
    assert cleaned >= 1

    cnt_after = (await db_session.execute(cnt_stmt)).scalars().all()
    assert len(cnt_after) == 0


@pytest.mark.asyncio
async def test_simulation_api_rbac_and_execution(async_client, simulation_users):
    """Verifies role-based authorization for simulation endpoints."""
    exec_user, mgr_user = simulation_users

    exec_token = create_access_token(exec_user.id, exec_user.role.value, exec_user.email)
    mgr_token = create_access_token(mgr_user.id, mgr_user.role.value, mgr_user.email)

    exec_headers = {"Authorization": f"Bearer {exec_token}"}
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # 1. Executive can list scenarios
    scenarios_resp = await async_client.get("/api/v1/simulation/scenarios", headers=exec_headers)
    assert scenarios_resp.status_code == 200
    data = scenarios_resp.json()
    assert len(data["scenarios"]) == 5

    # 2. Executive is rejected with 403 on run
    run_resp_exec = await async_client.post(
        "/api/v1/simulation/run",
        json={"scenario_type": "WEIGHT_DISCREPANCY", "provider_type": "fixture"},
        headers=exec_headers,
    )
    assert run_resp_exec.status_code == 403

    # 3. Manager succeeds on run
    run_resp_mgr = await async_client.post(
        "/api/v1/simulation/run",
        json={"scenario_type": "WEIGHT_DISCREPANCY", "provider_type": "fixture"},
        headers=mgr_headers,
    )
    assert run_resp_mgr.status_code == 200
    mgr_data = run_resp_mgr.json()
    assert mgr_data["success"] is True
    assert len(mgr_data["results"]) == 1
    assert mgr_data["results"][0]["shipment_number"] == "SHP-24811"

    # 4. Status endpoint lists demo shipment
    status_resp = await async_client.get("/api/v1/simulation/status", headers=mgr_headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["total_demo_shipments"] >= 1

    # 5. Reset endpoint
    reset_resp = await async_client.delete("/api/v1/simulation/reset", headers=mgr_headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_simulation_production_mode_refusal(async_client, simulation_users):
    """Verifies that simulation run and reset endpoints reject requests in production mode."""
    _, mgr_user = simulation_users
    mgr_token = create_access_token(mgr_user.id, mgr_user.role.value, mgr_user.email)
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    old_env = settings.ENVIRONMENT
    old_allow = settings.ALLOW_DEMO_SEEDING

    try:
        settings.ENVIRONMENT = "production"
        settings.ALLOW_DEMO_SEEDING = False

        run_resp = await async_client.post(
            "/api/v1/simulation/run",
            json={"scenario_type": "WEIGHT_DISCREPANCY"},
            headers=mgr_headers,
        )
        assert run_resp.status_code == 403
        assert "disabled in production" in run_resp.json()["detail"]

        reset_resp = await async_client.delete(
            "/api/v1/simulation/reset",
            headers=mgr_headers,
        )
        assert reset_resp.status_code == 403
        assert "disabled in production" in reset_resp.json()["detail"]
    finally:
        settings.ENVIRONMENT = old_env
        settings.ALLOW_DEMO_SEEDING = old_allow


@pytest.mark.asyncio
async def test_analytics_reflect_persisted_simulation_records(async_client, simulation_users):
    """
    Verifies that dashboard and analytics endpoints dynamically derive their data
    from database records populated during simulation without hardcoded metrics.
    """
    _, mgr_user = simulation_users
    mgr_token = create_access_token(mgr_user.id, mgr_user.role.value, mgr_user.email)
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # Run complete workflow scenario
    run_resp = await async_client.post(
        "/api/v1/simulation/run",
        json={"scenario_type": "COMPLETE_WORKFLOW", "provider_type": "fixture"},
        headers=mgr_headers,
    )
    assert run_resp.status_code == 200

    # Query analytics overview
    analytics_resp = await async_client.get("/api/v1/analytics/overview", headers=mgr_headers)
    assert analytics_resp.status_code == 200
    analytics_data = analytics_resp.json()

    assert analytics_data["total_shipments"] >= 1
    assert analytics_data["total_documents"] >= 3
    assert analytics_data["shipments_awaiting_human_review"] >= 1
    assert analytics_data["shipments_by_status"]["REVIEW_REQUIRED"] >= 1

    # Query dashboard stats
    dash_resp = await async_client.get("/api/v1/dashboard/stats", headers=mgr_headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["manager"]["total_shipments_count"] >= 1
    assert dash_data["manager"]["shipments_by_status"]["REVIEW_REQUIRED"] >= 1


@pytest.mark.asyncio
async def test_normal_shipment_with_demo_in_client_name_never_deleted(db_session, simulation_users):
    """
    Verifies that a normal user-created shipment with '[DEMO]' in its client name (is_demo=False)
    is never deleted by clean_all_demo or clean_shipment.
    """
    exec_user, _ = simulation_users
    from app.storage import get_storage_service
    storage = get_storage_service()

    async def _save_test_file(k: str, b: bytes):
        async def _gen():
            yield b
        await storage.save_file(_gen(), k)

    # 1. Create a normal shipment with [DEMO] in client_name
    normal_shipment = Shipment(
        shipment_number="SHP-USER-DEMO-001",
        client_name="Legit Customer [DEMO] Ltd",
        origin_country="Japan",
        product_description="Precision Tools",
        quantity=Decimal("100.00"),
        unit_price=Decimal("50.0000"),
        currency="USD",
        gross_weight_kg=Decimal("500.000"),
        status=ShipmentStatus.CREATED,
        created_by=exec_user.id,
        is_demo=False,
    )
    db_session.add(normal_shipment)
    await db_session.commit()
    await db_session.refresh(normal_shipment)

    # Attach a physical document to it
    dummy_pdf = b"%PDF-1.4 dummy user file"
    storage_key = storage.get_safe_storage_key("pdf")
    await _save_test_file(storage_key, dummy_pdf)
    assert await storage.file_exists(storage_key) is True

    doc = Document(
        shipment_id=normal_shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="user_invoice.pdf",
        storage_key=storage_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(dummy_pdf),
        sha256_checksum="d" * 64,
        uploaded_by=exec_user.id,
    )
    db_session.add(doc)
    await db_session.commit()

    # Try cleaning with clean_shipment
    await SimulationEngine.clean_shipment(db_session, normal_shipment.shipment_number)

    # Check shipment still exists
    stmt = select(Shipment).where(Shipment.id == normal_shipment.id)
    persisted = (await db_session.execute(stmt)).scalar_one_or_none()
    assert persisted is not None
    assert persisted.is_demo is False
    assert await storage.file_exists(storage_key) is True

    # Try cleaning with clean_all_demo
    await SimulationEngine.clean_all_demo(db_session)

    # Check shipment and physical file still exist
    persisted_after = (await db_session.execute(stmt)).scalar_one_or_none()
    assert persisted_after is not None
    assert await storage.file_exists(storage_key) is True

    # Clean up test artifact
    await storage.delete_file(storage_key)
    await db_session.delete(persisted_after)
    await db_session.commit()


@pytest.mark.asyncio
async def test_demo_shipment_without_demo_in_client_name_is_deleted(db_session, simulation_users):
    """
    Verifies that a synthetic demo shipment (is_demo=True) is deleted during cleanup
    even if its client_name does NOT contain '[DEMO]'.
    """
    exec_user, _ = simulation_users
    from app.storage import get_storage_service
    storage = get_storage_service()

    async def _save_test_file(k: str, b: bytes):
        async def _gen():
            yield b
        await storage.save_file(_gen(), k)

    demo_shipment = Shipment(
        shipment_number="SHP-SYNTHETIC-REALNAME-001",
        client_name="Ordinary Corporation International",  # No [DEMO] in client name
        origin_country="Germany",
        product_description="Test Turbine Parts",
        quantity=Decimal("10.00"),
        unit_price=Decimal("100.0000"),
        currency="EUR",
        gross_weight_kg=Decimal("120.000"),
        status=ShipmentStatus.CREATED,
        created_by=exec_user.id,
        is_demo=True,  # Ownership marker
    )
    db_session.add(demo_shipment)
    await db_session.commit()
    await db_session.refresh(demo_shipment)

    # Attach physical document
    dummy_pdf = b"%PDF-1.4 dummy demo file"
    storage_key = storage.get_safe_storage_key("pdf")
    await _save_test_file(storage_key, dummy_pdf)
    assert await storage.file_exists(storage_key) is True

    doc = Document(
        shipment_id=demo_shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="demo_invoice.pdf",
        storage_key=storage_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(dummy_pdf),
        sha256_checksum="e" * 64,
        uploaded_by=exec_user.id,
    )
    db_session.add(doc)
    await db_session.commit()

    # Clean demo data
    cleaned_count = await SimulationEngine.clean_all_demo(db_session)
    assert cleaned_count >= 1

    # Verify demo shipment is gone and file is deleted
    stmt = select(Shipment).where(Shipment.id == demo_shipment.id)
    assert (await db_session.execute(stmt)).scalar_one_or_none() is None
    assert await storage.file_exists(storage_key) is False


@pytest.mark.asyncio
async def test_non_demo_shipments_documents_jobs_reviews_exports_remain_intact(db_session, simulation_users):
    """
    Verifies that non-demo shipments, documents, jobs, reviews, and exports
    remain completely intact when clean_all_demo is executed.
    """
    exec_user, mgr_user = simulation_users
    from app.storage import get_storage_service
    storage = get_storage_service()

    async def _save_test_file(k: str, b: bytes):
        async def _gen():
            yield b
        await storage.save_file(_gen(), k)

    # 1. Non-demo shipment
    non_demo = Shipment(
        shipment_number="SHP-USER-PERM-777",
        client_name="Permanent Customer Ltd",
        origin_country="Italy",
        product_description="Marble Slabs",
        quantity=Decimal("40.00"),
        unit_price=Decimal("250.0000"),
        currency="EUR",
        gross_weight_kg=Decimal("8000.000"),
        status=ShipmentStatus.VERIFIED,
        created_by=exec_user.id,
        is_demo=False,
    )
    db_session.add(non_demo)
    await db_session.commit()
    await db_session.refresh(non_demo)

    # 2. Document + physical file
    doc_bytes = b"%PDF-1.4 non demo document"
    storage_key = storage.get_safe_storage_key("pdf")
    await _save_test_file(storage_key, doc_bytes)

    doc = Document(
        shipment_id=non_demo.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="perm_invoice.pdf",
        storage_key=storage_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(doc_bytes),
        sha256_checksum="f" * 64,
        uploaded_by=exec_user.id,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # 3. Processing Job
    job = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.COMPLETED,
    )
    db_session.add(job)

    # 4. Field Review
    review = DocumentFieldReview(
        document_id=doc.id,
        shipment_id=non_demo.id,
        field_name="grand_total",
        action="CONFIRMED",
        original_value="10000.00",
        reviewer_id=mgr_user.id,
    )
    db_session.add(review)

    # 5. Export Record
    export_rec = ShipmentExportRecord(
        shipment_id=non_demo.id,
        template_name="STANDARD_CUSTOMS_CSV",
        exported_by=mgr_user.id,
        filename="customs_export_perm.csv",
        sha256_checksum="c" * 64,
        row_count=1,
        snapshot_data={"rows": [{"Shipment": "SHP-USER-PERM-777", "Total": "10000.00"}]},
    )
    db_session.add(export_rec)
    await db_session.commit()

    # Execute demo cleanup
    await SimulationEngine.clean_all_demo(db_session)

    # Verify everything remains intact
    assert (await db_session.execute(select(Shipment).where(Shipment.id == non_demo.id))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(Document).where(Document.id == doc.id))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(ProcessingJob).where(ProcessingJob.document_id == doc.id))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(DocumentFieldReview).where(DocumentFieldReview.shipment_id == non_demo.id))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(ShipmentExportRecord).where(ShipmentExportRecord.shipment_id == non_demo.id))).scalar_one_or_none() is not None
    assert await storage.file_exists(storage_key) is True

    # Teardown
    await storage.delete_file(storage_key)
    await db_session.delete(non_demo)
    await db_session.commit()


@pytest.mark.asyncio
async def test_executive_cannot_access_simulation_reset(async_client, simulation_users):
    """Verifies that documentation executives are rejected with 403 on DELETE /api/v1/simulation/reset."""
    exec_user, _ = simulation_users
    exec_token = create_access_token(exec_user.id, exec_user.role.value, exec_user.email)
    exec_headers = {"Authorization": f"Bearer {exec_token}"}

    resp = await async_client.delete("/api/v1/simulation/reset", headers=exec_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_repeated_simulation_runs_idempotent_no_duplicates(db_session, simulation_users):
    """Verifies that running a scenario multiple times does not produce duplicate shipments or errors."""
    exec_user, mgr_user = simulation_users

    res1 = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="WEIGHT_DISCREPANCY",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )
    res2 = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="WEIGHT_DISCREPANCY",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )
    assert res1["shipment_number"] == res2["shipment_number"] == "SHP-24811"

    # Only 1 row in shipments table for SHP-24811
    stmt = select(Shipment).where(Shipment.shipment_number == "SHP-24811")
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_demo is True

    # Clean demo data
    await SimulationEngine.clean_all_demo(db_session)


@pytest.mark.asyncio
async def test_normal_shipment_creation_and_update_cannot_set_is_demo(async_client, simulation_users):
    """
    Verifies that normal shipment creation and update endpoints prohibit clients
    from setting or modifying the is_demo marker.
    """
    exec_user, _ = simulation_users
    exec_token = create_access_token(exec_user.id, exec_user.role.value, exec_user.email)
    exec_headers = {"Authorization": f"Bearer {exec_token}"}

    # 1. Attempt to create with is_demo: true -> rejected with 422 Unprocessable Entity
    create_with_demo = {
        "shipment_number": "SHP-FORBID-001",
        "client_name": "Tamper Test Corp",
        "origin_country": "China",
        "is_demo": True,
    }
    resp_forbid = await async_client.post("/api/v1/shipments", json=create_with_demo, headers=exec_headers)
    assert resp_forbid.status_code == 422

    # 2. Normal creation creates with is_demo=False
    valid_create = {
        "shipment_number": "SHP-VALID-001",
        "client_name": "Tamper Test Corp",
        "origin_country": "China",
    }
    resp_ok = await async_client.post("/api/v1/shipments", json=valid_create, headers=exec_headers)
    assert resp_ok.status_code == 201
    created_data = resp_ok.json()
    assert created_data["is_demo"] is False
    shipment_id = created_data["id"]

    # 3. Attempt to update with is_demo: true -> rejected with 422 Unprocessable Entity
    patch_with_demo = {
        "client_name": "Modified Tamper Corp",
        "is_demo": True,
    }
    resp_patch_forbid = await async_client.patch(f"/api/v1/shipments/{shipment_id}", json=patch_with_demo, headers=exec_headers)
    assert resp_patch_forbid.status_code == 422

    # Verify is_demo remains False in DB
    get_resp = await async_client.get(f"/api/v1/shipments/{shipment_id}", headers=exec_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["is_demo"] is False
