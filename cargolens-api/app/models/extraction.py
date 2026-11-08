import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    String,
    Integer,
    Text,
    Numeric,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document


class ExtractionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ExtractionMethod(str, enum.Enum):
    DIGITAL_TEXT = "DIGITAL_TEXT"
    OCR = "OCR"
    HYBRID = "HYBRID"
    EMPTY = "EMPTY"
    FAILED = "FAILED"


class ExtractionQualityStatus(str, enum.Enum):
    GOOD = "GOOD"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class PageExtractionMethod(str, enum.Enum):
    DIGITAL_TEXT = "DIGITAL_TEXT"
    OCR = "OCR"
    EMPTY = "EMPTY"
    FAILED = "FAILED"


class PageProcessingStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EMPTY = "EMPTY"


class DocumentExtraction(Base, TimestampMixin):
    """
    Represents an extraction attempt on an uploaded document version.
    Preserves historical extractions per attempt and records overall quality metrics.
    """
    __tablename__ = "document_extractions"

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
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        SAEnum(ExtractionMethod, name="extraction_method_enum", native_enum=True),
        nullable=False,
        default=ExtractionMethod.DIGITAL_TEXT,
    )
    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    processed_page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    avg_confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    quality_status: Mapped[ExtractionQualityStatus] = mapped_column(
        SAEnum(ExtractionQualityStatus, name="extraction_quality_status_enum", native_enum=True),
        nullable=False,
        default=ExtractionQualityStatus.GOOD,
        index=True,
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

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extractions")
    pages: Mapped[List["DocumentExtractionPage"]] = relationship(
        "DocumentExtractionPage",
        back_populates="extraction",
        cascade="all, delete-orphan",
        order_by="DocumentExtractionPage.page_number.asc()",
    )

    __table_args__ = (
        UniqueConstraint("document_id", "attempt_number", name="uq_document_extraction_attempt"),
        Index("ix_document_extractions_document_attempt", "document_id", "attempt_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentExtraction id={self.id} doc={self.document_id} attempt={self.attempt_number} "
            f"method={self.extraction_method} quality={self.quality_status}>"
        )


class DocumentExtractionPage(Base):
    """
    Stores page-level extraction results, method (DIGITAL_TEXT vs OCR), confidence, and text.
    Enables paginated and responsive text preview on multi-page documents.
    """
    __tablename__ = "document_extraction_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_extractions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    extraction_method: Mapped[PageExtractionMethod] = mapped_column(
        SAEnum(PageExtractionMethod, name="page_extraction_method_enum", native_enum=True),
        nullable=False,
        default=PageExtractionMethod.DIGITAL_TEXT,
    )
    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    ocr_confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    processing_status: Mapped[PageProcessingStatus] = mapped_column(
        SAEnum(PageProcessingStatus, name="page_processing_status_enum", native_enum=True),
        nullable=False,
        default=PageProcessingStatus.COMPLETED,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    extraction: Mapped["DocumentExtraction"] = relationship("DocumentExtraction", back_populates="pages")

    __table_args__ = (
        UniqueConstraint("extraction_id", "page_number", name="uq_extraction_page_number"),
        Index("ix_document_extraction_pages_extraction_page", "extraction_id", "page_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentExtractionPage extraction={self.extraction_id} page={self.page_number} "
            f"method={self.extraction_method} chars={self.character_count}>"
        )
