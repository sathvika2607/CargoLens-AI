import os
import uuid
from decimal import Decimal
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
async def multi_user_workspace_fixture(db_session):
    """
    Sets up a shared operational workspace containing:
    1. An existing Documentation Manager
    2. An existing Documentation Executive
    3. Multiple active consignments with documents, validations, and exports
    """
    # Existing manager
    mgr_email = f"lead.manager.{uuid.uuid4().hex[:6]}@cargolens.in"
    manager = User(
        full_name="Lead Operations Manager",
        email=mgr_email,
        hashed_password=hash_password("ManagerSecure2026!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    # Existing executive
    exec_email = f"senior.exec.{uuid.uuid4().hex[:6]}@cargolens.in"
    executive = User(
        full_name="Senior Documentation Executive",
        email=exec_email,
        hashed_password=hash_password("ExecSecure2026!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add_all([manager, executive])
    await db_session.commit()
    await db_session.refresh(manager)
    await db_session.refresh(executive)

    # Consignments
    s1 = Shipment(
        shipment_number=f"SHP-PERM-01-{uuid.uuid4().hex[:4].upper()}",
        client_name="Lumileds Global Trading [DEMO]",
        origin_country="CN",
        status=ShipmentStatus.REVIEW_REQUIRED,
        created_by=executive.id,
        currency="USD",
        product_description="LED lighting components",
        quantity=Decimal("1500"),
        gross_weight_kg=Decimal("3120.00"),
        is_demo=True,
    )
    s2 = Shipment(
        shipment_number=f"SHP-PERM-02-{uuid.uuid4().hex[:4].upper()}",
        client_name="Siemens Energy Global [DEMO]",
        origin_country="DE",
        status=ShipmentStatus.VERIFIED,
        created_by=executive.id,
        currency="EUR",
        product_description="Turbine Pressure Transducers",
        quantity=Decimal("300"),
        gross_weight_kg=Decimal("890.00"),
        is_demo=True,
    )
    s3 = Shipment(
        shipment_number=f"SHP-PERM-03-{uuid.uuid4().hex[:4].upper()}",
        client_name="Schneider Electric Pacific [DEMO]",
        origin_country="SG",
        status=ShipmentStatus.EXPORTED,
        created_by=executive.id,
        currency="USD",
        product_description="Circuit Protection Assemblies",
        quantity=Decimal("4500"),
        gross_weight_kg=Decimal("5400.00"),
        is_demo=True,
    )
    db_session.add_all([s1, s2, s3])
    await db_session.commit()
    await db_session.refresh(s1)
    await db_session.refresh(s2)
    await db_session.refresh(s3)

    # Documents for s1
    doc_ci = Document(
        shipment_id=s1.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="CI_Invoice_Lumileds.pdf",
        storage_key=f"mock/ci_{uuid.uuid4().hex[:6]}.pdf",
        file_extension=".pdf",
        file_size_bytes=14200,
        mime_type="application/pdf",
        sha256_checksum="1" * 64,
        processing_status=DocumentProcessingStatus.COMPLETED,
        version=1,
        is_active=True,
        uploaded_by=executive.id,
    )
    doc_pl = Document(
        shipment_id=s1.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="PL_Packing_Lumileds.pdf",
        storage_key=f"mock/pl_{uuid.uuid4().hex[:6]}.pdf",
        file_extension=".pdf",
        file_size_bytes=12500,
        mime_type="application/pdf",
        sha256_checksum="2" * 64,
        processing_status=DocumentProcessingStatus.COMPLETED,
        version=1,
        is_active=True,
        uploaded_by=executive.id,
    )
    db_session.add_all([doc_ci, doc_pl])
    await db_session.commit()
    await db_session.refresh(doc_ci)
    await db_session.refresh(doc_pl)

    # Human review
    review = DocumentFieldReview(
        shipment_id=s1.id,
        document_id=doc_ci.id,
        field_name="grand_total",
        action=FieldReviewActionType.CONFIRMED,
        provenance=ReviewProvenance.USER_ACTION,
        original_value="16320.00",
        corrected_value="16320.00",
        reviewer_id=executive.id,
    )
    db_session.add(review)

    # Export record for s3
    exp = ShipmentExportRecord(
        shipment_id=s3.id,
        exported_by=manager.id,
        template_name="STANDARD_CUSTOMS_CLEARANCE",
        template_version="1.0",
        filename=f"{s3.shipment_number}_customs_declaration.csv",
        sha256_checksum="3" * 64,
        export_status=ExportStatus.COMPLETED,
        row_count=1,
        file_size_bytes=640,
        snapshot_data={"status": "CLEARED"},
    )
    db_session.add(exp)
    await db_session.commit()

    return {
        "manager": manager,
        "executive": executive,
        "mgr_token": create_access_token(manager.id, manager.role.value, manager.email),
        "s1": s1,
        "s2": s2,
        "s3": s3,
        "doc_ci": doc_ci,
        "doc_pl": doc_pl,
    }


@pytest.mark.asyncio
async def test_multiple_independently_registered_users_access_shared_workspace(
    async_client: AsyncClient, multi_user_workspace_fixture
):
    """
    Simulates multiple independently registered users across different corporate domains.
    For EACH user:
    1. Registration succeeds with HTTP 201.
    2. Role is automatically DOCUMENTATION_EXECUTIVE.
    3. Login succeeds with HTTP 200.
    4. Valid JWT authentication received; /auth/me returns their profile with DOCUMENTATION_EXECUTIVE.
    5. Shared workspace displays all existing consignments.
    6. All existing documents and metadata are visible.
    7. Analytics return the shared workspace figures.
    8. Discrepancy inspection & review information are accessible.
    9. Manager-only endpoints reject access with HTTP 403 Forbidden.
    10. Logging out and logging back in retains all shared workspace data (never empty).
    """
    env = multi_user_workspace_fixture
    s1_id = str(env["s1"].id)
    doc_ci_id = str(env["doc_ci"].id)

    # Diverse independent users across different corporate email domains
    evaluator_profiles = [
        {"name": "Ananya Deshmukh", "domain": "mumbai-customs-brokerage.in"},
        {"name": "Vikramaditya Rao", "domain": "jnpt-logistics-alliance.com"},
        {"name": "Sunita Kulkarni", "domain": "global-ocean-freight.org"},
        {"name": "Devendra Singhania", "domain": "isocode-customs-audit.net"},
    ]

    for profile in evaluator_profiles:
        unique_suffix = uuid.uuid4().hex[:6]
        email = f"user.{unique_suffix}@{profile['domain']}"
        password = f"SecurePass{unique_suffix.capitalize()}123!"

        # 1. Registration
        reg_res = await async_client.post(
            "/api/v1/auth/register",
            json={
                "full_name": profile["name"],
                "email": email,
                "password": password,
                "confirm_password": password,
            },
        )
        assert reg_res.status_code == 201, f"Registration failed for {email}: {reg_res.text}"
        reg_data = reg_res.json()

        # 2. Automatically assigned DOCUMENTATION_EXECUTIVE
        assert reg_data["role"] == "DOCUMENTATION_EXECUTIVE"
        assert reg_data["is_active"] is True
        assert reg_data["email"] == email.lower()
        user_id = reg_data["id"]

        # 3. Login
        login_res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 200, f"Login failed for {email}: {login_res.text}"
        token_data = login_res.json()
        token = token_data["access_token"]
        assert token_data["user"]["role"] == "DOCUMENTATION_EXECUTIVE"
        headers = {"Authorization": f"Bearer {token}"}

        # 4. Identity profile verification
        me_res = await async_client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["id"] == user_id
        assert me_res.json()["role"] == "DOCUMENTATION_EXECUTIVE"

        # 5. Shared workspace: Displays all existing consignments
        shipments_res = await async_client.get("/api/v1/shipments", headers=headers)
        assert shipments_res.status_code == 200
        shipment_items = shipments_res.json()["items"]
        assert len(shipment_items) >= 3, "New user saw an empty or incomplete shipment list!"
        returned_ids = {s["id"] for s in shipment_items}
        assert str(env["s1"].id) in returned_ids
        assert str(env["s2"].id) in returned_ids
        assert str(env["s3"].id) in returned_ids

        # 6. Associated documents and details visible
        s1_detail = await async_client.get(f"/api/v1/shipments/{s1_id}", headers=headers)
        assert s1_detail.status_code == 200
        assert s1_detail.json()["shipment_number"] == env["s1"].shipment_number

        docs_res = await async_client.get(f"/api/v1/shipments/{s1_id}/documents", headers=headers)
        assert docs_res.status_code == 200
        doc_items = docs_res.json()["items"]
        assert len(doc_items) >= 2
        assert any(d["id"] == doc_ci_id for d in doc_items)

        # 7. Analytics return shared workspace figures
        analytics_res = await async_client.get("/api/v1/analytics/overview", headers=headers)
        assert analytics_res.status_code == 200
        an_data = analytics_res.json()
        assert an_data["total_shipments"] >= 3
        assert an_data["total_documents"] >= 2

        # 8. Permitted review information & validation
        reviews_res = await async_client.get(
            f"/api/v1/shipments/{s1_id}/documents/{doc_ci_id}/reviews", headers=headers
        )
        assert reviews_res.status_code == 200
        assert len(reviews_res.json()["items"]) >= 1

        val_res = await async_client.get("/api/v1/validations/issues", headers=headers)
        assert val_res.status_code == 200

        # 9. Manager-only endpoints reject access with HTTP 403 Forbidden
        # - User provisioning
        u_create = await async_client.post(
            "/api/v1/users",
            json={
                "full_name": "Rogue User",
                "email": f"rogue.{uuid.uuid4().hex[:6]}@test.com",
                "password": "Password123!",
                "role": "DOCUMENTATION_MANAGER",
            },
            headers=headers,
        )
        assert u_create.status_code == 403

        # - Team user listing
        u_list = await async_client.get("/api/v1/users", headers=headers)
        assert u_list.status_code == 403

        # - Simulation execution
        sim_run = await async_client.post(
            "/api/v1/simulation/run",
            json={"scenario_type": "CLEAN_PASS", "provider_type": "fixture"},
            headers=headers,
        )
        assert sim_run.status_code == 403

        # - Simulation reset
        sim_reset = await async_client.delete("/api/v1/simulation/reset", headers=headers)
        assert sim_reset.status_code == 403

        # 10. Logging out and re-logging in keeps workspace intact
        logout_res = await async_client.post("/api/v1/auth/logout", headers=headers)
        assert logout_res.status_code == 200

        relogin_res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert relogin_res.status_code == 200
        re_token = relogin_res.json()["access_token"]
        re_headers = {"Authorization": f"Bearer {re_token}"}

        # Verify shipments still visible
        re_shipments = await async_client.get("/api/v1/shipments", headers=re_headers)
        assert re_shipments.status_code == 200
        assert len(re_shipments.json()["items"]) >= 3


@pytest.mark.asyncio
async def test_security_unauthenticated_and_privilege_escalation_defenses(
    async_client: AsyncClient, multi_user_workspace_fixture
):
    """
    Verifies that:
    1. Unauthenticated requests to protected endpoints return HTTP 401.
    2. Users cannot submit or select privileged roles during registration.
    3. Existing manager retains all authorized manager capabilities.
    4. Bootstrap manager endpoint cannot be used when manager already exists.
    """
    env = multi_user_workspace_fixture

    # 1. Unauthenticated endpoints return 401
    unauth_endpoints = [
        ("GET", "/api/v1/shipments"),
        ("GET", "/api/v1/dashboard/stats"),
        ("GET", "/api/v1/analytics/overview"),
        ("GET", "/api/v1/users"),
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/simulation/run"),
    ]
    for method, endpoint in unauth_endpoints:
        if method == "GET":
            res = await async_client.get(endpoint)
        else:
            res = await async_client.post(endpoint, json={})
        assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {endpoint}, got {res.status_code}"

    # 2. Registration cannot grant elevated roles (Pydantic validator + server-side enforcement)
    for bad_role in ["DOCUMENTATION_MANAGER", "MANAGER", "ADMIN", "SUPERUSER"]:
        res = await async_client.post(
            "/api/v1/auth/register",
            json={
                "full_name": f"Attacker {bad_role}",
                "email": f"attacker.{uuid.uuid4().hex[:6]}@test.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "role": bad_role,
            },
        )
        assert res.status_code == 422, f"Expected 422 rejection for role {bad_role}, got {res.status_code}"

    # 3. Existing manager retains full manager capabilities
    mgr_headers = {"Authorization": f"Bearer {env['mgr_token']}"}
    users_res = await async_client.get("/api/v1/users", headers=mgr_headers)
    assert users_res.status_code == 200
    assert len(users_res.json()) >= 2

    dash_res = await async_client.get("/api/v1/dashboard/stats", headers=mgr_headers)
    assert dash_res.status_code == 200
    assert "manager" in dash_res.json()
    assert dash_res.json()["manager"]["total_shipments_count"] >= 3

    # 4. Bootstrap manager endpoint fails because manager already exists
    bootstrap_res = await async_client.post(
        "/api/v1/auth/bootstrap-manager",
        json={
            "full_name": "Rival Manager",
            "email": f"rival.{uuid.uuid4().hex[:6]}@cargolens.in",
            "password": "Password123!",
            "bootstrap_secret": "bootstrap-super-secret-key-prod-2026",
        },
    )
    # Returns 400 Bad Request (if manager exists) or 403 Forbidden (if secret invalid/unauthorized)
    assert bootstrap_res.status_code in (400, 403)


@pytest.mark.asyncio
async def test_profile_updates_cannot_change_user_role(
    async_client: AsyncClient, multi_user_workspace_fixture
):
    """
    Verifies that:
    1. Newly registered executive attempts to elevate role via profile update methods (PUT/PATCH /auth/me or /users/me).
    2. Endpoint strictly rejects unpermitted modification (405, 404, or 403).
    3. User profile role in /auth/me strictly remains DOCUMENTATION_EXECUTIVE.
    """
    env = multi_user_workspace_fixture
    exec_user = env["executive"]
    exec_token = create_access_token(exec_user.id, exec_user.role.value, exec_user.email)
    headers = {"Authorization": f"Bearer {exec_token}"}

    # Attempt role modification via various HTTP methods
    malicious_payloads = [
        {"role": "DOCUMENTATION_MANAGER"},
        {"role": UserRole.DOCUMENTATION_MANAGER.value},
        {"is_active": True, "role": "DOCUMENTATION_MANAGER"},
    ]

    target_routes = [
        "/api/v1/auth/me",
        "/api/v1/users/me",
        f"/api/v1/users/{exec_user.id}",
    ]

    for route in target_routes:
        for payload in malicious_payloads:
            for method in ("PATCH", "PUT", "POST"):
                if method == "PATCH":
                    res = await async_client.patch(route, json=payload, headers=headers)
                elif method == "PUT":
                    res = await async_client.put(route, json=payload, headers=headers)
                else:
                    res = await async_client.post(route, json=payload, headers=headers)

                # Route must either be 405 Method Not Allowed, 404 Not Found, 403 Forbidden, or 422
                assert res.status_code in (403, 404, 405, 422), (
                    f"Unexpected status {res.status_code} for {method} {route}"
                )

    # Verify role was not modified
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["role"] == UserRole.DOCUMENTATION_EXECUTIVE.value
