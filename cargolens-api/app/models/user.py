import enum
import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken
    from app.models.shipment import Shipment


class UserRole(str, enum.Enum):
    DOCUMENTATION_EXECUTIVE = "DOCUMENTATION_EXECUTIVE"
    DOCUMENTATION_MANAGER = "DOCUMENTATION_MANAGER"


class User(Base, TimestampMixin):
    """
    User entity representing personnel operating CargoLens AI.
    Roles are enforced backend-wide for RBAC authorization.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role_enum", native_enum=True),
        nullable=False,
        default=UserRole.DOCUMENTATION_EXECUTIVE,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    shipments: Mapped[List["Shipment"]] = relationship(
        "Shipment",
        back_populates="creator",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
