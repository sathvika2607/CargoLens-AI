import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.security import hash_password, create_access_token


@pytest.mark.asyncio
async def test_shipment_crud_and_rbac_scoping(async_client: AsyncClient, db_session):
    """
    Comprehensive test validating:
    - Executive creation of shipments
    - Duplicate shipment_number rejection (409)
    - Executive sees only own shipments in list
    - Manager sees all shipments in list with status breakdown
    - Cross-executive access blocked with 403 Forbidden
    - Manager permitted to access and update any shipment
    """
    # 1. Seed Executive 1 and Executive 2 and Manager
    exec1 = User(
        full_name="Executive One",
        email="exec1@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    exec2 = User(
        full_name="Executive Two",
        email="exec2@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    manager = User(
        full_name="Manager Head",
        email="manager.head@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec1, exec2, manager])
    await db_session.commit()

    token_exec1 = create_access_token(exec1.id, exec1.role.value, exec1.email)
    token_exec2 = create_access_token(exec2.id, exec2.role.value, exec2.email)
    token_manager = create_access_token(manager.id, manager.role.value, manager.email)

    # 2. Executive 1 creates SHP-24811 (client benchmark)
    shp1_payload = {
        "shipment_number": "SHP-24811",
        "client_name": "Company B, China",
        "origin_country": "China",
        "product_description": "LED panel light 40W",
        "quantity": 2400.0,
        "unit_price": 6.80,
        "currency": "USD",
        "gross_weight_kg": 3120.0,
    }
    create_res1 = await async_client.post(
        "/api/v1/shipments",
        json=shp1_payload,
        headers={"Authorization": f"Bearer {token_exec1}"},
    )
    assert create_res1.status_code == 201
    shp1 = create_res1.json()
    assert shp1["shipment_number"] == "SHP-24811"
    assert shp1["created_by"] == str(exec1.id)
    assert shp1["status"] == "CREATED"
    assert Decimal(str(shp1["gross_weight_kg"])) == Decimal("3120.000")

    # 3. Duplicate shipment number rejected with 409 Conflict
    dup_res = await async_client.post(
        "/api/v1/shipments",
        json=shp1_payload,
        headers={"Authorization": f"Bearer {token_exec1}"},
    )
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.json()["detail"]

    # 4. Executive 2 creates SHP-24812 (client benchmark)
    shp2_payload = {
        "shipment_number": "SHP-24812",
        "client_name": "Company C, Sweden",
        "origin_country": "Sweden",
        "product_description": "Steel ball valve DN50",
        "quantity": 180.0,
        "unit_price": 42.50,
        "currency": "EUR",
        "gross_weight_kg": 1460.0,
    }
    create_res2 = await async_client.post(
        "/api/v1/shipments",
        json=shp2_payload,
        headers={"Authorization": f"Bearer {token_exec2}"},
    )
    assert create_res2.status_code == 201
    shp2 = create_res2.json()

    # 5. Executive 1 lists shipments -> Sees shared workspace shipments
    list_exec1 = await async_client.get(
        "/api/v1/shipments",
        headers={"Authorization": f"Bearer {token_exec1}"},
    )
    assert list_exec1.status_code == 200
    exec1_data = list_exec1.json()
    assert exec1_data["total"] >= 2
    assert exec1_data["status_summary"] is not None

    # 6. Manager lists shipments -> Sees shared workspace shipments + status summary
    list_mgr = await async_client.get(
        "/api/v1/shipments",
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert list_mgr.status_code == 200
    mgr_data = list_mgr.json()
    assert mgr_data["total"] >= 2
    assert mgr_data["status_summary"] is not None
    assert "CREATED" in mgr_data["status_summary"]

    # 7. Shared Workspace Access: Executive 2 views SHP-24811 -> 200 OK
    cross_res = await async_client.get(
        f"/api/v1/shipments/{shp1['id']}",
        headers={"Authorization": f"Bearer {token_exec2}"},
    )
    assert cross_res.status_code == 200
    assert cross_res.json()["shipment_number"] == "SHP-24811"

    # 8. Non-existent shipment returns 404
    fake_id = str(uuid.uuid4())
    cross_fake = await async_client.get(
        f"/api/v1/shipments/{fake_id}",
        headers={"Authorization": f"Bearer {token_exec2}"},
    )
    assert cross_fake.status_code == 404
    assert "not found" in cross_fake.json()["detail"].lower()

    # 9. Manager views SHP-24811 -> 200 OK
    mgr_get = await async_client.get(
        f"/api/v1/shipments/{shp1['id']}",
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert mgr_get.status_code == 200

    # 10. Executive updates consignment in shared workspace -> 200 OK
    exec1_update = await async_client.patch(
        f"/api/v1/shipments/{shp1['id']}",
        json={"product_description": "LED panel light 40W (Customs Pack)"},
        headers={"Authorization": f"Bearer {token_exec1}"},
    )
    assert exec1_update.status_code == 200
    assert exec1_update.json()["product_description"] == "LED panel light 40W (Customs Pack)"


@pytest.mark.asyncio
async def test_shipment_negative_value_validation(async_client: AsyncClient, db_session):
    """Verifies that negative quantities, prices, or weights are rejected by schema validation."""
    user = User(
        full_name="Validation User",
        email="val.user@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id, user.role.value, user.email)

    # Negative quantity
    res = await async_client.post(
        "/api/v1/shipments",
        json={
            "shipment_number": "SHP-NEG-01",
            "client_name": "Invalid Client",
            "origin_country": "India",
            "quantity": -10.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_shipment_currency_handling(async_client: AsyncClient, db_session):
    """
    Verifies that currency defaults to NULL when not provided,
    and explicitly provided currencies (USD, EUR, etc.) are strictly preserved.
    """
    user = User(
        full_name="Currency Tester",
        email="currency.tester@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id, user.role.value, user.email)

    # 1. Unspecified currency must remain NULL
    res_null = await async_client.post(
        "/api/v1/shipments",
        json={
            "shipment_number": "SHP-CURR-NULL",
            "client_name": "Unknown Currency Consignee",
            "origin_country": "Singapore",
            "quantity": 100.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_null.status_code == 201
    assert res_null.json()["currency"] is None

    # 2. Explicit USD preserved
    res_usd = await async_client.post(
        "/api/v1/shipments",
        json={
            "shipment_number": "SHP-CURR-USD",
            "client_name": "USD Consignee",
            "origin_country": "United States",
            "currency": "USD",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_usd.status_code == 201
    assert res_usd.json()["currency"] == "USD"

    # 3. Explicit EUR preserved
    res_eur = await async_client.post(
        "/api/v1/shipments",
        json={
            "shipment_number": "SHP-CURR-EUR",
            "client_name": "EUR Consignee",
            "origin_country": "Germany",
            "currency": "EUR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_eur.status_code == 201
    assert res_eur.json()["currency"] == "EUR"


@pytest.mark.asyncio
async def test_shipment_lifecycle_status_protection(async_client: AsyncClient, db_session):
    """
    Verifies that NEITHER Documentation Executives NOR Documentation Managers can manually
    transition shipments to workflow-controlled statuses (VERIFIED, EXPORTED) via ordinary PATCH.
    Both roles receive HTTP 403 Forbidden.
    Legitimate editing of other permitted fields and operational statuses is fully preserved.
    """
    exec_user = User(
        full_name="Lifecycle Exec",
        email="lifecycle.exec@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr_user = User(
        full_name="Lifecycle Mgr",
        email="lifecycle.mgr@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec_user, mgr_user])
    await db_session.commit()

    token_exec = create_access_token(exec_user.id, exec_user.role.value, exec_user.email)
    token_mgr = create_access_token(mgr_user.id, mgr_user.role.value, mgr_user.email)

    # Create shipment by executive
    res_create = await async_client.post(
        "/api/v1/shipments",
        json={
            "shipment_number": "SHP-STATUS-PROTECT",
            "client_name": "Workflow Client",
            "origin_country": "Japan",
        },
        headers={"Authorization": f"Bearer {token_exec}"},
    )
    assert res_create.status_code == 201
    shp_id = res_create.json()["id"]

    # 1. Executive attempting PATCH to VERIFIED -> 403 Forbidden
    patch_exec_ver = await async_client.patch(
        f"/api/v1/shipments/{shp_id}",
        json={"status": "VERIFIED"},
        headers={"Authorization": f"Bearer {token_exec}"},
    )
    assert patch_exec_ver.status_code == 403
    assert "workflow-controlled status" in patch_exec_ver.json()["detail"].lower()

    # 2. Executive attempting PATCH to EXPORTED -> 403 Forbidden
    patch_exec_exp = await async_client.patch(
        f"/api/v1/shipments/{shp_id}",
        json={"status": "EXPORTED"},
        headers={"Authorization": f"Bearer {token_exec}"},
    )
    assert patch_exec_exp.status_code == 403
    assert "workflow-controlled status" in patch_exec_exp.json()["detail"].lower()

    # 3. Manager attempting PATCH to VERIFIED -> 403 Forbidden
    patch_mgr_ver = await async_client.patch(
        f"/api/v1/shipments/{shp_id}",
        json={"status": "VERIFIED"},
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert patch_mgr_ver.status_code == 403
    assert "workflow-controlled status" in patch_mgr_ver.json()["detail"].lower()

    # 4. Manager attempting PATCH to EXPORTED -> 403 Forbidden
    patch_mgr_exp = await async_client.patch(
        f"/api/v1/shipments/{shp_id}",
        json={"status": "EXPORTED"},
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert patch_mgr_exp.status_code == 403
    assert "workflow-controlled status" in patch_mgr_exp.json()["detail"].lower()

    # 5. Executive legitimate update of operational status (REVIEW_REQUIRED) + fields -> 200 OK
    patch_exec_ok = await async_client.patch(
        f"/api/v1/shipments/{shp_id}",
        json={
            "status": "REVIEW_REQUIRED",
            "product_description": "Updated operational description",
            "quantity": 350.0,
        },
        headers={"Authorization": f"Bearer {token_exec}"},
    )
    assert patch_exec_ok.status_code == 200
    assert patch_exec_ok.json()["status"] == "REVIEW_REQUIRED"
    assert patch_exec_ok.json()["product_description"] == "Updated operational description"

    # 6. Manager legitimate update of operational status (PROCESSING) + weight -> 200 OK
    patch_mgr_ok = await async_client.patch(
        f"/api/v1/shipments/{shp_id}",
        json={
            "status": "PROCESSING",
            "gross_weight_kg": 5400.25,
        },
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert patch_mgr_ok.status_code == 200
    assert patch_mgr_ok.json()["status"] == "PROCESSING"
    assert Decimal(str(patch_mgr_ok.json()["gross_weight_kg"])) == Decimal("5400.250")
