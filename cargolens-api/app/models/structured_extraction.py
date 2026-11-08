import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Dict, Any
from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.document import DocumentType
from app.models.extraction import ExtractionStatus

if TYPE_CHECKING:
    from app.models.document import Document


class StructuredExtraction(Base, TimestampMixin):
    """
    Stores an AI-powered structured extraction attempt for a document.
    Maintains historical attempts, provenance evidence, provider/model versions,
    and field confidence summaries.
    """
    __tablename__ = "structured_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    status: Mapped[ExtractionStatus] = mapped_column(
        SAEnum(ExtractionStatus, name="extraction_status_enum", native_enum=True),
        nullable=False,
        default=ExtractionStatus.PENDING,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="anthropic",
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="claude-sonnet-5-5",
    )
    extraction_mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="TEXT_FIRST",  # "TEXT_FIRST", "VISION", or "HYBRID"
    )
    total_page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    processed_page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    extracted_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    field_confidence_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    raw_response_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    error_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    document: Mapped["Document"] = relationship("Document", backref="structured_extractions")

    __table_args__ = (
        UniqueConstraint("document_id", "attempt_number", name="uq_structured_extraction_attempt"),
        Index("ix_structured_extractions_doc_attempt", "document_id", "attempt_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<StructuredExtraction id={self.id} doc={self.document_id} attempt={self.attempt_number} "
            f"type={self.document_type} status={self.status}>"
        )
