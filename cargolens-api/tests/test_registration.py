import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.user import User, UserRole
from app.security import verify_password, hash_password


@pytest.mark.asyncio
async def test_successful_registration(async_client: AsyncClient, db_session):
    """Verifies that a new user can register with valid details, receiving 201 Created and DOCUMENTATION_EXECUTIVE role."""
    payload = {
        "full_name": "Priya Nair",
        "email": "priya.nair@cargolens.in",
        "password": "SecurePass2026!",
        "confirm_password": "SecurePass2026!",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "priya.nair@cargolens.in"
    assert data["full_name"] == "Priya Nair"
    assert data["role"] == "DOCUMENTATION_EXECUTIVE"
    assert data["is_active"] is True
    assert "id" in data
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_duplicate_email_rejection(async_client: AsyncClient, db_session):
    """Verifies that registering an already-registered email is rejected with 409 Conflict."""
    payload = {
        "full_name": "First User",
        "email": "duplicate.test@cargolens.in",
        "password": "SecurePass2026!",
        "confirm_password": "SecurePass2026!",
    }
    res1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Exact duplicate
    res2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()

    # Case-insensitive duplicate (e.g. UPPERCASE)
    res3 = await async_client.post(
        "/api/v1/auth/register",
        json={**payload, "email": "DUPLICATE.TEST@cargolens.in"},
    )
    assert res3.status_code == 409
    assert "already exists" in res3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_email_rejection(async_client: AsyncClient):
    """Verifies that malformed or non-email strings are rejected with 422 Unprocessable Entity."""
    invalid_emails = [
        "not-an-email",
        "user@",
        "@cargolens.in",
        "user@.com",
        "plainaddress",
    ]
    for bad_email in invalid_emails:
        payload = {
            "full_name": "Test User",
            "email": bad_email,
            "password": "SecurePass2026!",
            "confirm_password": "SecurePass2026!",
        }
        res = await async_client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422, f"Expected 422 for email '{bad_email}', got {res.status_code}"


@pytest.mark.asyncio
async def test_password_mismatch_rejection(async_client: AsyncClient):
    """Verifies that mismatched confirm_password is rejected with 422 Unprocessable Entity."""
    payload = {
        "full_name": "Mismatch Tester",
        "email": "mismatch@cargolens.in",
        "password": "SecurePass2026!",
        "confirm_password": "DifferentPassword2026!",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert "match" in str(response.json()).lower()


@pytest.mark.asyncio
async def test_weak_password_requirements_rejection(async_client: AsyncClient):
    """Verifies that passwords lacking required complexity (8+ chars, uppercase, lowercase, digit, special char) are rejected."""
    weak_passwords = [
        ("short1!", "at least 8 characters"),
        ("nouppercase123!", "uppercase"),
        ("NOLOWERCASE123!", "lowercase"),
        ("NoDigitsHere!", "digit"),
        ("NoSpecial12345", "special character"),
    ]
    for pwd, error_hint in weak_passwords:
        payload = {
            "full_name": "Weak Pass User",
            "email": f"weak_{pwd[:5]}@cargolens.in",
            "password": pwd,
            "confirm_password": pwd,
        }
        res = await async_client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422, f"Expected 422 for password '{pwd}', got {res.status_code}"
        assert error_hint.lower() in str(res.json()).lower()


@pytest.mark.asyncio
async def test_password_hashing_verification(async_client: AsyncClient, db_session):
    """Verifies that passwords are stored as salted Argon2id hashes, never in plaintext."""
    raw_password = "Argon2idSecretPassword2026!"
    payload = {
        "full_name": "Hash Verification User",
        "email": "hash.verify@cargolens.in",
        "password": raw_password,
        "confirm_password": raw_password,
    }
    res = await async_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201

    # Inspect directly from PostgreSQL
    user_stmt = select(User).where(User.email == "hash.verify@cargolens.in")
    user = (await db_session.execute(user_stmt)).scalar_one()

    # Invariants:
    assert user.hashed_password != raw_password
    assert raw_password not in user.hashed_password
    # Argon2id signature prefix:
    assert user.hashed_password.startswith("$argon2id$")
    # Verify using security module:
    assert verify_password(raw_password, user.hashed_password) is True
    assert verify_password("WrongPassword!", user.hashed_password) is False


@pytest.mark.asyncio
async def test_successful_login_after_registration(async_client: AsyncClient, db_session):
    """Verifies that a freshly registered user can immediately log in with their credentials."""
    email = "new.login.user@cargolens.in"
    password = "ValidLoginPassword2026!"
    reg_payload = {
        "full_name": "New Login User",
        "email": email,
        "password": password,
        "confirm_password": password,
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # Attempt login
    login_payload = {"email": email, "password": password}
    login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["email"] == email
    assert token_data["user"]["role"] == "DOCUMENTATION_EXECUTIVE"


@pytest.mark.asyncio
async def test_registration_cannot_create_manager_or_admin(async_client: AsyncClient, db_session):
    """Verifies privilege escalation defense: attempts to register with Manager or Admin roles are strictly rejected."""
    forbidden_roles = [
        "DOCUMENTATION_MANAGER",
        "MANAGER",
        "ADMIN",
        "SUPERUSER",
        "ADMINISTRATOR",
    ]
    for bad_role in forbidden_roles:
        payload = {
            "full_name": f"Escalation Attempt {bad_role}",
            "email": f"hacker.{bad_role.lower()}@test.com",
            "password": "HackerPassword2026!",
            "confirm_password": "HackerPassword2026!",
            "role": bad_role,
        }
        res = await async_client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422
        assert "forbidden" in str(res.json()).lower()

    # Verify no users were created with forbidden roles
    user_stmt = select(User).where(User.email.like("hacker.%"))
    users = (await db_session.execute(user_stmt)).scalars().all()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_existing_login_and_protected_route_authorization(async_client: AsyncClient, db_session):
    """Verifies existing login flow works, and new executive cannot access manager-only export authorizations."""
    # 1. Existing seeded executive logs in
    exec_user = User(
        full_name="Existing Executive",
        email="existing.exec@cargolens.in",
        hashed_password=hash_password("ExistingExecPass2026!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(exec_user)
    await db_session.commit()

    exec_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "existing.exec@cargolens.in", "password": "ExistingExecPass2026!"},
    )
    assert exec_login.status_code == 200
    exec_token = exec_login.json()["access_token"]

    # 2. Executive can access /auth/me
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "DOCUMENTATION_EXECUTIVE"

    # 3. Manager authorization barrier: Executive CANNOT access manager-only endpoints
    create_user_res = await async_client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {exec_token}"},
        json={"full_name": "Rogue User", "email": "rogue@test.com", "password": "Password123!"},
    )
    # Manager endpoint requires require_manager -> HTTP 403 Forbidden
    assert create_user_res.status_code == 403
    assert "Documentation Manager" in create_user_res.json()["detail"] or "Forbidden" in create_user_res.json()["detail"]
