import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import (
    String,
    Text,
    Numeric,
    Enum as SAEnum,
    ForeignKey,
    CheckConstraint,
    Index,
    Boolean,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document import Document
    from app.models.export import ShipmentExportRecord


class ShipmentStatus(str, enum.Enum):
    CREATED = "CREATED"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    VERIFIED = "VERIFIED"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"


class Shipment(Base, TimestampMixin):
    """
    Core shipment entity representing a consignment undergoing document verification.
    Financial and weight fields use strict Decimal / Numeric types to prevent float inaccuracies.
    """
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    shipment_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    client_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    origin_country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    product_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )
    unit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4),
        nullable=True,
    )
    # Currency: ISO 4217 code (e.g. USD, EUR, INR). Nullable; unknown currency remains NULL.
    currency: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    # Gross Weight (KG): Numeric(12, 3) providing 0.001 kg (one gram) precision.
    gross_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True,
    )
    status: Mapped[ShipmentStatus] = mapped_column(
        SAEnum(ShipmentStatus, name="shipment_status_enum", native_enum=True),
        nullable=False,
        default=ShipmentStatus.CREATED,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="shipments",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="Document.created_at.desc()",
    )
    exports: Mapped[List["ShipmentExportRecord"]] = relationship(
        "ShipmentExportRecord",
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="ShipmentExportRecord.exported_at.desc()",
    )

    __table_args__ = (
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="chk_positive_quantity"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="chk_positive_unit_price"),
        CheckConstraint("gross_weight_kg IS NULL OR gross_weight_kg >= 0", name="chk_positive_gross_weight"),
        Index("ix_shipments_status_created_at", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Shipment id={self.id} number={self.shipment_number} status={self.status}>"
