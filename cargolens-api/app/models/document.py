import enum
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    String,
    BigInteger,
    Integer,
    Boolean,
    Enum as SAEnum,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.shipment import Shipment
    from app.models.user import User
    from app.models.processing_job import ProcessingJob
    from app.models.extraction import DocumentExtraction


class DocumentType(str, enum.Enum):
    COMMERCIAL_INVOICE = "COMMERCIAL_INVOICE"
    PACKING_LIST = "PACKING_LIST"
    BILL_OF_LADING = "BILL_OF_LADING"


class DocumentProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Document(Base, TimestampMixin):
    """
    Represents an uploaded customs document linked to a specific shipment consignment.
    Preserves all versions and associates with processing background jobs.
    """
    __tablename__ = "documents"

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
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    file_extension: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    sha256_checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        SAEnum(DocumentProcessingStatus, name="document_processing_status_enum", native_enum=True),
        nullable=False,
        default=DocumentProcessingStatus.PENDING,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="documents")
    uploader: Mapped["User"] = relationship("User")
    processing_jobs: Mapped[List["ProcessingJob"]] = relationship(
        "ProcessingJob",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ProcessingJob.created_at.desc()",
    )
    extractions: Mapped[List["DocumentExtraction"]] = relationship(
        "DocumentExtraction",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentExtraction.attempt_number.desc()",
    )

    __table_args__ = (
        CheckConstraint("file_size_bytes > 0", name="chk_positive_file_size"),
        CheckConstraint("version >= 1", name="chk_positive_document_version"),
        UniqueConstraint("shipment_id", "sha256_checksum", name="uq_documents_shipment_checksum"),
        UniqueConstraint("shipment_id", "document_type", "version", name="uq_documents_shipment_type_version"),
        Index("ix_documents_shipment_type_version", "shipment_id", "document_type", "version"),
        Index("ix_documents_shipment_checksum", "shipment_id", "sha256_checksum"),
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} type={self.document_type} "
            f"version={self.version} status={self.processing_status}>"
        )
