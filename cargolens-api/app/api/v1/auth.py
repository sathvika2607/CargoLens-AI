from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select, update, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models.user import User, UserRole
from app.models.refresh_token import RefreshToken
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    UserResponse,
    ManagerBootstrapRequest,
    RegisterRequest,
)
from app.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    hash_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
    description="Registers a new corporate user with default DOCUMENTATION_EXECUTIVE privileges.",
)
async def register(
    req: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    # 1. Normalize email
    normalized_email = req.email.strip().lower()

    # 2. Check for duplicate email (case-insensitive)
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    existing_user = (await session.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{normalized_email}' already exists",
        )

    # 3. Create user with Argon2id hashed password and enforced DOCUMENTATION_EXECUTIVE role
    # Defense against privilege escalation: Role is strictly set to DOCUMENTATION_EXECUTIVE
    new_user = User(
        full_name=req.full_name.strip(),
        email=normalized_email,
        hashed_password=hash_password(req.password),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="Authenticates corporate credentials, returns JWT access token, and sets secure refresh token.",
)
async def login(
    login_data: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Query user by normalized email
    stmt = select(User).where(User.email == login_data.email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    # Generic error message to prevent email enumeration
    invalid_creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise invalid_creds_exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated. Contact Documentation Manager.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate token pair
    access_token = create_access_token(user.id, user.role.value, user.email)
    raw_refresh_token, token_hash, expires_at = create_refresh_token()

    # Persist refresh token hash
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False,
    )
    session.add(refresh_record)
    await session.commit()

    # Set HttpOnly refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate Refresh Token",
    description="Rotates refresh token pair, revoking previous token. Detects token reuse attacks.",
)
async def refresh_token_endpoint(
    response: Response,
    body: Optional[TokenRefreshRequest] = None,
    refresh_token: Optional[str] = Cookie(None),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    raw_token = (body and body.refresh_token) or refresh_token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required in cookie or request body",
        )

    token_hash = hash_token(raw_token)

    # Locate token by hash
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    result = await session.execute(stmt)
    token_record = result.scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Token Reuse Detection: If an already-revoked token is submitted, revoke all tokens for this user
    if token_record.is_revoked:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == token_record.user_id)
            .values(is_revoked=True)
        )
        await session.commit()
        response.delete_cookie(key="refresh_token", path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security violation: Refresh token reuse detected. All sessions revoked.",
        )

    # Check expiration
    if token_record.expires_at < datetime.now(timezone.utc):
        token_record.is_revoked = True
        await session.commit()
        response.delete_cookie(key="refresh_token", path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    # Fetch active user
    user_stmt = select(User).where(User.id == token_record.user_id)
    user_res = await session.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or not found",
        )

    # Revoke old token (rotation)
    token_record.is_revoked = True

    # Issue new token pair
    new_access_token = create_access_token(user.id, user.role.value, user.email)
    new_raw_refresh, new_token_hash, new_expires_at = create_refresh_token()

    new_token_record = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=new_expires_at,
        is_revoked=False,
    )
    session.add(new_token_record)
    await session.commit()

    # Update cookie
    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Revokes active refresh token and clears session cookies.",
)
async def logout(
    response: Response,
    body: Optional[TokenRefreshRequest] = None,
    refresh_token: Optional[str] = Cookie(None),
    session: AsyncSession = Depends(get_db),
):
    raw_token = (body and body.refresh_token) or refresh_token
    if raw_token:
        token_hash = hash_token(raw_token)
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(is_revoked=True)
        )
        await session.commit()

    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"status": "success", "message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current User Profile",
    description="Returns the profile and verified role of the currently authenticated user.",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


BOOTSTRAP_ADVISORY_LOCK_ID: int = 84821001


@router.post(
    "/bootstrap-manager",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bootstrap Initial Documentation Manager",
    description="Controlled initial provisioning of the primary manager account using BOOTSTRAP_SECRET.",
)
async def bootstrap_manager(
    req: ManagerBootstrapRequest,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    # Verify bootstrap secret
    if not settings.BOOTSTRAP_SECRET or req.bootstrap_secret != settings.BOOTSTRAP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid bootstrap authorization secret",
        )

    # Concurrency protection: Acquire PostgreSQL transaction-level advisory lock
    # to serialize bootstrap requests across concurrent worker threads or processes.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": BOOTSTRAP_ADVISORY_LOCK_ID},
    )

    # Protection: Ensure bootstrap-manager only works when no manager account exists
    mgr_count_stmt = select(func.count(User.id)).where(User.role == UserRole.DOCUMENTATION_MANAGER)
    mgr_count_res = await session.execute(mgr_count_stmt)
    if (mgr_count_res.scalar() or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Documentation Manager account has already been created. Bootstrap provisioning is disabled.",
        )

    # Check for existing email collision
    stmt = select(User).where(User.email == req.email)
    existing = await session.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{req.email}' already exists",
        )

    # Create Documentation Manager
    manager = User(
        full_name=req.full_name,
        email=req.email,
        hashed_password=hash_password(req.password),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    session.add(manager)
    await session.commit()
    await session.refresh(manager)

    return UserResponse.model_validate(manager)
