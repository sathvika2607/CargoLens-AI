import pytest
from httpx import AsyncClient
from app.models.user import User, UserRole
from app.security import hash_password, create_access_token


@pytest.mark.asyncio
async def test_manager_can_create_executive(async_client: AsyncClient, db_session):
    """Verifies that a Documentation Manager can provision a new Documentation Executive."""
    # Seed manager
    manager = User(
        full_name="Manager Admin",
        email="manager.admin@cargolens.in",
        hashed_password=hash_password("ManagerPass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add(manager)
    await db_session.commit()
    token = create_access_token(manager.id, manager.role.value, manager.email)

    # Provision Executive
    payload = {
        "full_name": "New Executive",
        "email": "new.exec@cargolens.in",
        "password": "ExecPassword123!",
        "role": "DOCUMENTATION_EXECUTIVE",
    }
    res = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "new.exec@cargolens.in"
    assert data["role"] == "DOCUMENTATION_EXECUTIVE"


@pytest.mark.asyncio
async def test_executive_cannot_create_user(async_client: AsyncClient, db_session):
    """Verifies that a Documentation Executive is blocked from creating users (403 Forbidden)."""
    exec_user = User(
        full_name="Standard Exec",
        email="standard.exec@cargolens.in",
        hashed_password=hash_password("ExecPass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(exec_user)
    await db_session.commit()
    token = create_access_token(exec_user.id, exec_user.role.value, exec_user.email)

    payload = {
        "full_name": "Privilege Escalation Attempt",
        "email": "escalation@cargolens.in",
        "password": "Password123!",
        "role": "DOCUMENTATION_MANAGER",
    }
    res = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]


@pytest.mark.asyncio
async def test_unauthenticated_user_access_blocked(async_client: AsyncClient):
    """Verifies that requests without a token are rejected with 401 Unauthorized."""
    res = await async_client.get("/api/v1/users/me")
    assert res.status_code == 401
    assert "credentials were not provided" in res.json()["detail"].lower()
