import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.cli.seed_demo import seed_users, DEMO_USERS
from app.models.user import User, UserRole
from app.security import hash_password, verify_password


@pytest.mark.asyncio
async def test_seed_demo_users_creates_accounts(db_session):
    """
    Verifies that seed_users creates both required demo accounts with correct
    roles, active state, and verifiable Argon2id passwords.
    """
    users = await seed_users(db_session)
    assert len(users) == 2

    # Verify Documentation Executive
    exec_user = users.get("executive@cargolens.in")
    assert exec_user is not None
    assert exec_user.email == "executive@cargolens.in"
    assert exec_user.role == UserRole.DOCUMENTATION_EXECUTIVE
    assert exec_user.is_active is True
    assert verify_password("DemoExecutive2026!", exec_user.hashed_password) is True

    # Verify Documentation Manager
    mgr_user = users.get("manager@cargolens.in")
    assert mgr_user is not None
    assert mgr_user.email == "manager@cargolens.in"
    assert mgr_user.role == UserRole.DOCUMENTATION_MANAGER
    assert mgr_user.is_active is True
    assert verify_password("DemoManager2026!", mgr_user.hashed_password) is True


@pytest.mark.asyncio
async def test_demo_users_authentication_and_profile(async_client: AsyncClient, db_session):
    """
    Verifies that both demo accounts can authenticate via POST /api/v1/auth/login
    and retrieve their profile with proper roles from GET /api/v1/auth/me.
    """
    await seed_users(db_session)

    # 1. Login as Documentation Executive
    exec_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "executive@cargolens.in", "password": "DemoExecutive2026!"},
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["user"]["email"] == "executive@cargolens.in"
    assert exec_data["user"]["role"] == "DOCUMENTATION_EXECUTIVE"
    exec_token = exec_data["access_token"]

    # Verify Executive /auth/me
    exec_me = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert exec_me.status_code == 200
    assert exec_me.json()["email"] == "executive@cargolens.in"
    assert exec_me.json()["role"] == "DOCUMENTATION_EXECUTIVE"

    # 2. Login as Documentation Manager
    mgr_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "manager@cargolens.in", "password": "DemoManager2026!"},
    )
    assert mgr_res.status_code == 200
    mgr_data = mgr_res.json()
    assert mgr_data["user"]["email"] == "manager@cargolens.in"
    assert mgr_data["user"]["role"] == "DOCUMENTATION_MANAGER"
    mgr_token = mgr_data["access_token"]

    # Verify Manager /auth/me
    mgr_me = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_me.status_code == 200
    assert mgr_me.json()["email"] == "manager@cargolens.in"
    assert mgr_me.json()["role"] == "DOCUMENTATION_MANAGER"


@pytest.mark.asyncio
async def test_seed_demo_users_idempotency_no_duplicates(db_session):
    """
    Verifies that running seed_users multiple times is completely idempotent
    and does not create duplicate user rows.
    """
    await seed_users(db_session)
    await seed_users(db_session)
    await seed_users(db_session)

    # Verify total user count remains exactly 2
    total_users = await db_session.scalar(select(func.count(User.id)))
    assert total_users == 2

    # Verify exactly one record per email
    exec_count = await db_session.scalar(
        select(func.count(User.id)).where(User.email == "executive@cargolens.in")
    )
    assert exec_count == 1

    mgr_count = await db_session.scalar(
        select(func.count(User.id)).where(User.email == "manager@cargolens.in")
    )
    assert mgr_count == 1


@pytest.mark.asyncio
async def test_seed_demo_users_does_not_overwrite_passwords(db_session):
    """
    Verifies that seed_users preserves existing user passwords on repeated runs
    and does not overwrite custom passwords unless overwrite_passwords=True.
    """
    await seed_users(db_session)

    # Simulate an account having a custom password
    user_stmt = select(User).where(User.email == "executive@cargolens.in")
    exec_user = (await db_session.execute(user_stmt)).scalar_one()
    custom_hash = hash_password("UserModifiedPassword2026!")
    exec_user.hashed_password = custom_hash
    await db_session.commit()

    # Re-run default seed_users (overwrite_passwords=False)
    await seed_users(db_session, overwrite_passwords=False)

    # Password hash must remain the customized hash
    refreshed_user = (await db_session.execute(user_stmt)).scalar_one()
    assert refreshed_user.hashed_password == custom_hash
    assert verify_password("UserModifiedPassword2026!", refreshed_user.hashed_password) is True
    assert verify_password("DemoExecutive2026!", refreshed_user.hashed_password) is False


@pytest.mark.asyncio
async def test_seed_demo_users_does_not_modify_unrelated_users(db_session):
    """
    Verifies that seed_users touches only demo accounts and never modifies
    or deletes unrelated existing users in the database.
    """
    # Create an unrelated staff user
    unrelated_user = User(
        full_name="Custom Field Officer",
        email="officer.patil@customs-agent.in",
        hashed_password=hash_password("OfficerSecret2026!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(unrelated_user)
    await db_session.commit()
    unrelated_id = unrelated_user.id
    original_hash = unrelated_user.hashed_password

    # Run demo seed
    await seed_users(db_session)

    # Check unrelated user is untouched
    stmt = select(User).where(User.id == unrelated_id)
    rechecked = (await db_session.execute(stmt)).scalar_one()
    assert rechecked.email == "officer.patil@customs-agent.in"
    assert rechecked.full_name == "Custom Field Officer"
    assert rechecked.hashed_password == original_hash
    assert rechecked.role == UserRole.DOCUMENTATION_EXECUTIVE
    assert rechecked.is_active is True

    # Total users: 1 unrelated + 2 demo = 3
    total = await db_session.scalar(select(func.count(User.id)))
    assert total == 3


@pytest.mark.asyncio
async def test_demo_users_rbac_enforcement(async_client: AsyncClient, db_session):
    """
    Verifies RBAC enforcement:
    - Documentation Executive cannot access manager-only endpoints (e.g. POST /api/v1/users).
    - Documentation Manager can access manager-only endpoints.
    """
    await seed_users(db_session)

    # 1. Login as Documentation Executive
    exec_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "executive@cargolens.in", "password": "DemoExecutive2026!"},
    )
    exec_token = exec_login.json()["access_token"]

    # Executive attempts to access manager-only endpoint POST /api/v1/users
    exec_attempt = await async_client.post(
        "/api/v1/users",
        json={
            "full_name": "Unauthorized Staff",
            "email": "unauth@cargolens.in",
            "password": "Password123!",
            "role": "DOCUMENTATION_EXECUTIVE",
        },
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert exec_attempt.status_code == 403
    assert "DOCUMENTATION_MANAGER" in exec_attempt.json()["detail"]

    # 2. Login as Documentation Manager
    mgr_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "manager@cargolens.in", "password": "DemoManager2026!"},
    )
    mgr_token = mgr_login.json()["access_token"]

    # Manager accesses manager-only endpoint POST /api/v1/users
    mgr_attempt = await async_client.post(
        "/api/v1/users",
        json={
            "full_name": "New Executive",
            "email": "new.exec@cargolens.in",
            "password": "NewExecPassword123!",
            "role": "DOCUMENTATION_EXECUTIVE",
        },
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_attempt.status_code == 201
    assert mgr_attempt.json()["email"] == "new.exec@cargolens.in"


@pytest.mark.asyncio
async def test_cli_seed_users_only_does_not_create_shipments(db_session):
    """
    Verifies that run_seed(users_only=True) seeds demo users without creating
    any synthetic shipments or documents.
    """
    from app.cli.seed_demo import run_seed
    from app.models.shipment import Shipment
    from app.models.document import Document

    # Execute seed in users-only mode
    await run_seed(force=True, users_only=True)

    # Verify users exist
    user_count = await db_session.scalar(select(func.count(User.id)))
    assert user_count == 2

    # Verify no shipments or documents created
    shipment_count = await db_session.scalar(select(func.count(Shipment.id)))
    assert shipment_count == 0

    doc_count = await db_session.scalar(select(func.count(Document.id)))
    assert doc_count == 0
