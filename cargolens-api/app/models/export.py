import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, Any
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Integer,
    Enum as SAEnum,
    ForeignKey,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.shipment import Shipment
    from app.models.user import User


class ExportStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ShipmentExportRecord(Base):
    """
    Immutable audit record and data snapshot of a customs declaration export event.
    Stores the template used, exported filename, SHA-256 checksum of generated CSV bytes,
    row counts, and a frozen snapshot of exported data.
    """
    __tablename__ = "shipment_export_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exported_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    template_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="STANDARD_CUSTOMS_CLEARANCE",
    )
    template_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    sha256_checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    export_status: Mapped[ExportStatus] = mapped_column(
        SAEnum(ExportStatus, name="export_status_enum", native_enum=True),
        nullable=False,
        default=ExportStatus.COMPLETED,
        index=True,
    )
    row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    snapshot_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="exports")
    exporter: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_shipment_exports_shipment_at", "shipment_id", "exported_at"),
        Index(
            "uq_completed_export_per_shipment",
            "shipment_id",
            unique=True,
            postgresql_where=text("export_status = 'COMPLETED'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ShipmentExportRecord id={self.id} shipment={self.shipment_id} "
            f"template={self.template_name} status={self.export_status}>"
        )
