from typing import AsyncGenerator, Callable, List
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.user import User, UserRole
from app.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injecting an asynchronous database session."""
    async for session in get_async_session():
        yield session


async def get_current_user(
    request: Request,
    auth: HTTPAuthorizationCredentials = Depends(security_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates the bearer access token and retrieves the authenticated active user.
    Supports Authorization header and fallback to access_token cookie.
    """
    token: str | None = None
    if auth and auth.credentials:
        token = auth.credentials
    else:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload is invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = UUID(user_id_str)
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired access token: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*allowed_roles: UserRole) -> Callable[[User], User]:
    """
    Factory creating a dependency that verifies the user possesses one of the allowed roles.
    Rejects unauthorized roles strictly with HTTP 403 Forbidden.
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires one of roles: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker


# Role-specific dependency guards
require_executive_or_manager = require_role(
    UserRole.DOCUMENTATION_EXECUTIVE,
    UserRole.DOCUMENTATION_MANAGER,
)
require_manager = require_role(UserRole.DOCUMENTATION_MANAGER)
