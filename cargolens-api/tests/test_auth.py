import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from app.config import settings
from app.models.user import User, UserRole
from app.models.refresh_token import RefreshToken
from app.security import hash_password, create_access_token


@pytest.mark.asyncio
async def test_bootstrap_manager_success(async_client: AsyncClient, db_session):
    """Verifies that an initial manager can be bootstrapped using the correct secret."""
    payload = {
        "full_name": "Senior Documentation Manager",
        "email": "manager.bootstrap@cargolens.in",
        "password": "ManagerSecurePassword2026!",
        "bootstrap_secret": settings.BOOTSTRAP_SECRET,
    }
    response = await async_client.post("/api/v1/auth/bootstrap-manager", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "manager.bootstrap@cargolens.in"
    assert data["role"] == "DOCUMENTATION_MANAGER"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_bootstrap_manager_invalid_secret(async_client: AsyncClient):
    """Verifies that manager bootstrap fails with 403 Forbidden when using an invalid secret."""
    payload = {
        "full_name": "Unauthorized Attempt",
        "email": "hacker@test.com",
        "password": "Password123!",
        "bootstrap_secret": "wrong-secret",
    }
    response = await async_client.post("/api/v1/auth/bootstrap-manager", json=payload)
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


@pytest.mark.asyncio
async def test_bootstrap_manager_fails_if_manager_already_exists(async_client: AsyncClient):
    """
    Verifies manager bootstrap protection:
    Once an initial manager exists, subsequent bootstrap attempts must fail (400 Bad Request)
    even when the correct bootstrap secret is supplied.
    """
    # 1. First manager bootstrap succeeds
    payload1 = {
        "full_name": "Initial Manager",
        "email": "mgr1@cargolens.in",
        "password": "ManagerPassword2026!",
        "bootstrap_secret": settings.BOOTSTRAP_SECRET,
    }
    res1 = await async_client.post("/api/v1/auth/bootstrap-manager", json=payload1)
    assert res1.status_code == 201

    # 2. Second attempt with different email and valid secret fails
    payload2 = {
        "full_name": "Second Manager Attempt",
        "email": "mgr2@cargolens.in",
        "password": "ManagerPassword2026!",
        "bootstrap_secret": settings.BOOTSTRAP_SECRET,
    }
    res2 = await async_client.post("/api/v1/auth/bootstrap-manager", json=payload2)
    assert res2.status_code == 400
    assert "already been created" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_bootstrap_manager_concurrency(async_client: AsyncClient, db_session):
    """
    Verifies concurrency safety of POST /api/v1/auth/bootstrap-manager:
    When multiple simultaneous requests attempt to bootstrap a manager concurrently,
    PostgreSQL's transaction-level advisory lock serializes execution.
    Exactly ONE request succeeds (HTTP 201 Created), and all other concurrent attempts fail
    (HTTP 400 Bad Request), resulting in exactly one manager account in PostgreSQL.
    """
    payloads = [
        {
            "full_name": f"Concurrent Candidate {i}",
            "email": f"concurrent.mgr.{i}@cargolens.in",
            "password": "ConcurrentPassword2026!",
            "bootstrap_secret": settings.BOOTSTRAP_SECRET,
        }
        for i in range(5)
    ]

    responses = await asyncio.gather(
        *[async_client.post("/api/v1/auth/bootstrap-manager", json=p) for p in payloads]
    )

    successes = [r for r in responses if r.status_code == 201]
    failures = [r for r in responses if r.status_code == 400]

    # Exactly one succeeded
    assert len(successes) == 1
    # All others failed with 400
    assert len(failures) == len(payloads) - 1

    for r in failures:
        assert "already been created" in r.json()["detail"]

    # Verify directly against database that exactly one manager exists
    mgr_count = await db_session.scalar(
        select(func.count(User.id)).where(User.role == UserRole.DOCUMENTATION_MANAGER)
    )
    assert mgr_count == 1


@pytest.mark.asyncio
async def test_login_and_token_refresh_flow(async_client: AsyncClient, db_session):
    """Tests complete login, token issuance, and refresh token rotation."""
    # 1. Seed user
    test_email = "executive.flow@cargolens.in"
    test_password = "ExecutivePassword123!"
    user = User(
        full_name="Documentation Exec Flow",
        email=test_email,
        hashed_password=hash_password(test_password),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # 2. Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": test_password},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["email"] == test_email
    assert "refresh_token" in login_res.cookies
    initial_refresh_cookie = login_res.cookies["refresh_token"]

    # 3. Access protected /auth/me
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == test_email

    # 4. Refresh token rotation
    async_client.cookies.set("refresh_token", initial_refresh_cookie)
    refresh_res = await async_client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    new_token_data = refresh_res.json()
    assert "access_token" in new_token_data
    assert new_token_data["access_token"] != token_data["access_token"]
    assert "refresh_token" in refresh_res.cookies
    second_refresh_cookie = refresh_res.cookies["refresh_token"]
    assert second_refresh_cookie != initial_refresh_cookie

    # 5. Token reuse detection: Reusing old rotated refresh token must fail with 401
    async_client.cookies.set("refresh_token", initial_refresh_cookie)
    reuse_res = await async_client.post("/api/v1/auth/refresh")
    assert reuse_res.status_code == 401
    assert "reuse detected" in reuse_res.json()["detail"].lower()

    # 6. Logout
    async_client.cookies.set("refresh_token", second_refresh_cookie)
    logout_res = await async_client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    assert "Logged out" in logout_res.json()["message"]


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient, db_session):
    """Verifies that invalid password returns 401 without specific enumeration details."""
    user = User(
        full_name="Password Test",
        email="password.test@cargolens.in",
        hashed_password=hash_password("CorrectPassword1!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "password.test@cargolens.in", "password": "WrongPassword!"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_inactive_user(async_client: AsyncClient, db_session):
    """Verifies that deactivated users cannot log in."""
    user = User(
        full_name="Inactive User",
        email="inactive.user@cargolens.in",
        hashed_password=hash_password("InactivePass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "inactive.user@cargolens.in", "password": "InactivePass123!"},
    )
    assert res.status_code == 401
    assert "deactivated" in res.json()["detail"].lower()
