import os
from decimal import Decimal
from uuid import uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.field_review import DocumentFieldReview, FieldReviewActionType, ReviewProvenance
from app.models.export import ShipmentExportRecord, ExportStatus
from app.security import hash_password, create_access_token


@pytest.fixture
async def shared_workspace_env(db_session):
    """
    Sets up a shared workspace environment containing:
    1. Existing Documentation Executive (creator of initial demo records)
    2. Existing Documentation Manager
    3. Seeded Consignments with documents, reviews, and a historical export
    """
    # 1. Existing Executive (Account 1)
    existing_exec = User(
        full_name="Rajesh Executive",
        email=f"exec.rajesh.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    # 2. Existing Manager (Account 2)
    existing_mgr = User(
        full_name="Pooja Manager",
        email=f"mgr.pooja.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([existing_exec, existing_mgr])
    await db_session.commit()
    await db_session.refresh(existing_exec)
    await db_session.refresh(existing_mgr)

    # 3. Create 3 distinct consignments in the workspace created by existing_exec
    s1 = Shipment(
        shipment_number=f"SHP-JNPT-01-{uuid4().hex[:4].upper()}",
        client_name="Tata AutoComp Systems Ltd",
        origin_country="IN",
        status=ShipmentStatus.REVIEW_REQUIRED,
        created_by=existing_exec.id,
        currency="USD",
        product_description="Automotive Brake Calipers",
        quantity=Decimal("500"),
        gross_weight_kg=Decimal("1250.00"),
        is_demo=True,
    )
    s2 = Shipment(
        shipment_number=f"SHP-JNPT-02-{uuid4().hex[:4].upper()}",
        client_name="Bharat Heavy Electricals Ltd",
        origin_country="IN",
        status=ShipmentStatus.VERIFIED,
        created_by=existing_exec.id,
        currency="EUR",
        product_description="High Voltage Switchgear",
        quantity=Decimal("50"),
        gross_weight_kg=Decimal("4200.00"),
        is_demo=True,
    )
    s3 = Shipment(
        shipment_number=f"SHP-JNPT-03-{uuid4().hex[:4].upper()}",
        client_name="Reliance Petrochemicals",
        origin_country="IN",
        status=ShipmentStatus.EXPORTED,
        created_by=existing_exec.id,
        currency="USD",
        product_description="Synthetic Polymer Resins",
        quantity=Decimal("1000"),
        gross_weight_kg=Decimal("25000.00"),
        is_demo=True,
    )
    db_session.add_all([s1, s2, s3])
    await db_session.commit()
    await db_session.refresh(s1)
    await db_session.refresh(s2)
    await db_session.refresh(s3)

    # 4. Attach Documents
    doc1 = Document(
        shipment_id=s1.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="CI_Invoice_01.pdf",
        storage_key=f"mock/ci_1_{uuid4().hex[:6]}.pdf",
        file_extension=".pdf",
        file_size_bytes=10240,
        mime_type="application/pdf",
        sha256_checksum="abc111" + "0" * 58,
        processing_status=DocumentProcessingStatus.COMPLETED,
        version=1,
        is_active=True,
        uploaded_by=existing_exec.id,
    )
    doc2 = Document(
        shipment_id=s2.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="PL_Packing_02.pdf",
        storage_key=f"mock/pl_2_{uuid4().hex[:6]}.pdf",
        file_extension=".pdf",
        file_size_bytes=10240,
        mime_type="application/pdf",
        sha256_checksum="abc222" + "0" * 58,
        processing_status=DocumentProcessingStatus.COMPLETED,
        version=1,
        is_active=True,
        uploaded_by=existing_exec.id,
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()
    await db_session.refresh(doc1)
    await db_session.refresh(doc2)

    # 5. Field review record
    review = DocumentFieldReview(
        shipment_id=s1.id,
        document_id=doc1.id,
        field_name="invoice_number",
        action=FieldReviewActionType.CONFIRMED,
        provenance=ReviewProvenance.USER_ACTION,
        original_value="INV-2026-001",
        corrected_value="INV-2026-001",
        reviewer_id=existing_exec.id,
    )
    db_session.add(review)

    # 6. Historical export record on s3
    export_rec = ShipmentExportRecord(
        shipment_id=s3.id,
        exported_by=existing_mgr.id,
        template_name="STANDARD_CUSTOMS_CLEARANCE",
        template_version="v1.0",
        filename=f"{s3.shipment_number}_customs.csv",
        sha256_checksum="deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678",
        export_status=ExportStatus.COMPLETED,
        row_count=1,
        file_size_bytes=512,
        snapshot_data={"csv_content": "ShipmentNumber,Status\nSHP-JNPT-03,EXPORTED"},
    )
    db_session.add(export_rec)
    await db_session.commit()

    return {
        "existing_exec": existing_exec,
        "existing_mgr": existing_mgr,
        "s1": s1,
        "s2": s2,
        "s3": s3,
        "doc1": doc1,
        "doc2": doc2,
        "exec_token": create_access_token(existing_exec.id, existing_exec.role.value, existing_exec.email),
        "mgr_token": create_access_token(existing_mgr.id, existing_mgr.role.value, existing_mgr.email),
    }


@pytest.mark.asyncio
async def test_all_three_accounts_access_identical_shared_shipment_registry(async_client: AsyncClient, shared_workspace_env):
    """
    Verifies that:
    1. Existing Executive sees all consignments.
    2. Existing Manager sees all consignments.
    3. Newly Registered Executive registers and immediately sees all consignments.
    """
    exec_headers = {"Authorization": f"Bearer {shared_workspace_env['exec_token']}"}
    mgr_headers = {"Authorization": f"Bearer {shared_workspace_env['mgr_token']}"}

    # 1. Existing Executive retrieves shipments
    exec_res = await async_client.get("/api/v1/shipments", headers=exec_headers)
    assert exec_res.status_code == 200
    exec_items = exec_res.json()["items"]
    assert len(exec_items) >= 3

    # 2. Existing Manager retrieves shipments
    mgr_res = await async_client.get("/api/v1/shipments", headers=mgr_headers)
    assert mgr_res.status_code == 200
    mgr_items = mgr_res.json()["items"]
    assert len(mgr_items) == len(exec_items)

    # 3. Register a brand new Executive account
    new_email = f"new.evaluator.{uuid4().hex[:6]}@cargolens.in"
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Isocode Evaluator",
            "email": new_email,
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        },
    )
    assert reg_res.status_code == 201
    reg_user = reg_res.json()
    assert reg_user["role"] == "DOCUMENTATION_EXECUTIVE"

    # Login with new account
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": new_email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    new_token = login_res.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 4. Newly registered Executive retrieves shipments -> must see the exact same 3+ shipments!
    new_res = await async_client.get("/api/v1/shipments", headers=new_headers)
    assert new_res.status_code == 200
    new_items = new_res.json()["items"]
    assert len(new_items) == len(exec_items)
    # Check that all IDs match
    assert {s["id"] for s in new_items} == {s["id"] for s in exec_items}


@pytest.mark.asyncio
async def test_all_three_accounts_consistent_dashboard_stats(async_client: AsyncClient, shared_workspace_env):
    """
    Verifies that dashboard KPI counters agree between existing executive, manager,
    and a newly registered executive.
    """
    exec_headers = {"Authorization": f"Bearer {shared_workspace_env['exec_token']}"}
    mgr_headers = {"Authorization": f"Bearer {shared_workspace_env['mgr_token']}"}

    # Register new executive
    new_email = f"evaluator.dash.{uuid4().hex[:6]}@cargolens.in"
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Audit Officer",
            "email": new_email,
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": new_email, "password": "Password123!"},
    )
    new_token = login_res.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # Get dashboard stats for all three
    exec_dash = (await async_client.get("/api/v1/dashboard/stats", headers=exec_headers)).json()
    mgr_dash = (await async_client.get("/api/v1/dashboard/stats", headers=mgr_headers)).json()
    new_dash = (await async_client.get("/api/v1/dashboard/stats", headers=new_headers)).json()

    # Executive view metrics
    exec_stats = exec_dash["executive"]
    new_stats = new_dash["executive"]
    mgr_stats = mgr_dash["manager"]

    # Both executives see identical workspace totals
    assert exec_stats["my_shipments_count"] >= 3
    assert new_stats["my_shipments_count"] == exec_stats["my_shipments_count"]
    assert mgr_stats["total_shipments_count"] == exec_stats["my_shipments_count"]

    assert exec_stats["documents_uploaded_count"] >= 2
    assert new_stats["documents_uploaded_count"] == exec_stats["documents_uploaded_count"]

    assert exec_stats["documents_awaiting_review_count"] == mgr_stats["documents_awaiting_review_count"]
    assert new_stats["documents_awaiting_review_count"] == exec_stats["documents_awaiting_review_count"]

    # Both executives see the recent shipments list
    assert len(new_stats["recent_shipments"]) == len(exec_stats["recent_shipments"])


@pytest.mark.asyncio
async def test_all_three_accounts_access_details_documents_and_analytics(async_client: AsyncClient, shared_workspace_env):
    """
    Verifies that all three accounts can access details, documents, and analytics.
    """
    s1_id = str(shared_workspace_env["s1"].id)
    doc1_id = str(shared_workspace_env["doc1"].id)

    # Register new executive
    new_email = f"evaluator.docs.{uuid4().hex[:6]}@cargolens.in"
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Compliance Inspector",
            "email": new_email,
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": new_email, "password": "Password123!"},
    )
    new_token = login_res.json()["access_token"]

    tokens = [
        shared_workspace_env["exec_token"],
        shared_workspace_env["mgr_token"],
        new_token,
    ]

    for token in tokens:
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Shipment details
        s_res = await async_client.get(f"/api/v1/shipments/{s1_id}", headers=headers)
        assert s_res.status_code == 200
        assert s_res.json()["id"] == s1_id

        # 2. Document listing
        docs_res = await async_client.get(f"/api/v1/shipments/{s1_id}/documents", headers=headers)
        assert docs_res.status_code == 200
        assert len(docs_res.json()["items"]) >= 1

        # 3. Analytics overview
        an_res = await async_client.get("/api/v1/analytics/overview", headers=headers)
        assert an_res.status_code == 200
        an_data = an_res.json()
        assert an_data["total_shipments"] >= 3


@pytest.mark.asyncio
async def test_rbac_manager_versus_executive_privilege_boundary(async_client: AsyncClient, shared_workspace_env):
    """
    Verifies that while visibility is shared, executive accounts CANNOT perform
    manager-only operations (e.g. user management, simulation controls).
    """
    # Register new executive
    new_email = f"evaluator.rbac.{uuid4().hex[:6]}@cargolens.in"
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Field Officer",
            "email": new_email,
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": new_email, "password": "Password123!"},
    )
    new_token = login_res.json()["access_token"]

    exec_tokens = [shared_workspace_env["exec_token"], new_token]

    for token in exec_tokens:
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Executive attempting manager-only user creation -> 403 Forbidden
        user_create_res = await async_client.post(
            "/api/v1/users",
            json={
                "full_name": "Attacker",
                "email": f"attacker.{uuid4().hex[:6]}@cargolens.in",
                "password": "Password123!",
                "role": "DOCUMENTATION_MANAGER",
            },
            headers=headers,
        )
        assert user_create_res.status_code == 403

        # 2. Executive attempting manager-only user listing -> 403 Forbidden
        user_list_res = await async_client.get(
            "/api/v1/users",
            headers=headers,
        )
        assert user_list_res.status_code == 403

        # 3. Executive attempting simulation run -> 403 Forbidden
        sim_res = await async_client.post(
            "/api/v1/simulation/run",
            json={"scenario": "CLEAN_PASS"},
            headers=headers,
        )
        assert sim_res.status_code == 403

    # Verify manager CAN access manager-only user listing
    mgr_headers = {"Authorization": f"Bearer {shared_workspace_env['mgr_token']}"}
    mgr_users_res = await async_client.get("/api/v1/users", headers=mgr_headers)
    assert mgr_users_res.status_code == 200


@pytest.mark.asyncio
async def test_audit_action_attributes_real_authenticated_user(async_client: AsyncClient, shared_workspace_env):
    """
    Verifies that when a newly registered user performs an action (e.g. confirming a field),
    the review record is attributed to their user ID, and is visible across the workspace.
    """
    s1_id = str(shared_workspace_env["s1"].id)
    doc1_id = str(shared_workspace_env["doc1"].id)

    # Register new executive
    new_email = f"evaluator.audit.{uuid4().hex[:6]}@cargolens.in"
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Audit Verification Specialist",
            "email": new_email,
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    new_user_id = reg_res.json()["id"]

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": new_email, "password": "Password123!"},
    )
    new_token = login_res.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # Perform field correction
    rev_res = await async_client.post(
        f"/api/v1/shipments/{s1_id}/documents/{doc1_id}/reviews",
        json={
            "field_name": "gross_weight_kg",
            "action": "CORRECTED",
            "corrected_value": "1250.00",
            "reason": "Verified against tare weight scale receipt",
        },
        headers=new_headers,
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()
    assert rev_data["reviewer_id"] == new_user_id
    assert rev_data["reviewer_name"] == "Audit Verification Specialist"

    # Verify that existing manager also sees this audit trail entry
    mgr_headers = {"Authorization": f"Bearer {shared_workspace_env['mgr_token']}"}
    audit_res = await async_client.get("/api/v1/review/audit-history", headers=mgr_headers)
    assert audit_res.status_code == 200
    all_reviews = audit_res.json()["items"]
    matching = [r for r in all_reviews if r["reviewer_id"] == new_user_id]
    assert len(matching) >= 1
    assert matching[0]["field_name"] == "gross_weight_kg"
