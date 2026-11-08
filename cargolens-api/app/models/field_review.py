import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.shipment import Shipment
    from app.models.document import Document
    from app.models.structured_extraction import StructuredExtraction
    from app.models.user import User


class FieldReviewActionType(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"


class ReviewProvenance(str, enum.Enum):
    """
    Distinguishes genuine human reviews executed via UI/API from synthetic demonstration seed fixtures.
    """
    USER_ACTION = "USER_ACTION"
    DEMO_SEED = "DEMO_SEED"


class DocumentFieldReview(Base):
    """
    Immutable audit log of human review actions (confirmations and corrections)
    on extracted document fields. Preserves the original AI-extracted value,
    records human-corrected values, reviewer identity, timestamp, and optional reasons.
    """
    __tablename__ = "document_field_reviews"

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
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structured_extractions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    action: Mapped[FieldReviewActionType] = mapped_column(
        SAEnum(FieldReviewActionType, name="field_review_action_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    provenance: Mapped[ReviewProvenance] = mapped_column(
        SAEnum(ReviewProvenance, name="review_provenance_enum", native_enum=True),
        default=ReviewProvenance.USER_ACTION,
        server_default=text("'USER_ACTION'"),
        nullable=False,
        index=True,
    )
    original_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    corrected_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment")
    document: Mapped["Document"] = relationship("Document")
    extraction: Mapped[Optional["StructuredExtraction"]] = relationship("StructuredExtraction")
    reviewer: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_field_reviews_doc_field_created", "document_id", "field_name", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentFieldReview id={self.id} doc={self.document_id} field={self.field_name} "
            f"action={self.action} provenance={self.provenance} reviewer={self.reviewer_id}>"
        )
