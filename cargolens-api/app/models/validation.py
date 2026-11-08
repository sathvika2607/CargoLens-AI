import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.shipment import Shipment


class ValidationOutcome(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MISSING_DATA = "MISSING_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INFO = "INFO"


class ValidationSeverity(str, enum.Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ShipmentValidationResult(Base):
    """
    Stores individual rule outcomes for deterministic cross-document validation runs.
    Each row captures a compared field, outcome, discrepancy explanation, and source evidence references.
    """
    __tablename__ = "shipment_validation_results"

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
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    rule_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    severity: Mapped[ValidationSeverity] = mapped_column(
        SAEnum(ValidationSeverity, name="validation_severity_enum", native_enum=True),
        nullable=False,
        default=ValidationSeverity.ERROR,
    )
    outcome: Mapped[ValidationOutcome] = mapped_column(
        SAEnum(ValidationOutcome, name="validation_outcome_enum", native_enum=True),
        nullable=False,
        default=ValidationOutcome.INFO,
        index=True,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    compared_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    source_document_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationship
    shipment: Mapped["Shipment"] = relationship("Shipment", backref="validation_results")

    __table_args__ = (
        Index("ix_validation_results_shipment_run", "shipment_id", "run_id"),
        Index("ix_validation_results_shipment_created", "shipment_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ShipmentValidationResult id={self.id} shipment={self.shipment_id} "
            f"rule={self.rule_id} outcome={self.outcome}>"
        )
