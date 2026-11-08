from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, require_manager
from app.models.user import User
from app.schemas.auth import UserCreate, UserResponse
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User Profile",
)
async def get_my_profile(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision New User (Manager Only)",
    description="Allows Documentation Managers to provision Documentation Executives or fellow Managers.",
)
async def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_manager),
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    # Check duplicate email
    stmt = select(User).where(User.email == user_in.email)
    existing = await session.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{user_in.email}' already exists",
        )

    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_active=True,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List Team Users (Manager Only)",
)
async def list_users(
    current_user: User = Depends(require_manager),
    session: AsyncSession = Depends(get_db),
) -> List[UserResponse]:
    stmt = select(User).order_by(User.created_at.desc())
    result = await session.execute(stmt)
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]
