from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentProcessingStatus
from app.models.processing_job import JobStatus
from app.models.extraction import (
    ExtractionStatus,
    ExtractionMethod,
    ExtractionQualityStatus,
    PageExtractionMethod,
    PageProcessingStatus,
)


class DocumentExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    attempt_number: int
    status: ExtractionStatus
    extraction_method: ExtractionMethod
    raw_text: str
    page_count: int
    processed_page_count: int
    failed_page_count: int
    avg_confidence: Optional[float] = None
    character_count: int
    quality_status: ExtractionQualityStatus
    error_summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class DocumentExtractionPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    extraction_id: UUID
    page_number: int
    extraction_method: PageExtractionMethod
    raw_text: str
    ocr_confidence: Optional[float] = None
    character_count: int
    processing_status: PageProcessingStatus
    error_message: Optional[str] = None
    created_at: datetime


class DocumentExtractionPagesListResponse(BaseModel):
    items: List[DocumentExtractionPageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentExtractionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    attempt_number: int
    status: ExtractionStatus
    extraction_method: ExtractionMethod
    quality_status: ExtractionQualityStatus
    page_count: int
    avg_confidence: Optional[float] = None
    character_count: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class DocumentExtractionHistoryResponse(BaseModel):
    items: List[DocumentExtractionHistoryItem]
    total: int


class DocumentProcessingStatusResponse(BaseModel):
    document_id: UUID
    document_processing_status: DocumentProcessingStatus
    active_job_id: Optional[UUID] = None
    job_status: Optional[JobStatus] = None
    attempt_count: int = 0
    max_attempts: int = 3
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    latest_extraction: Optional[DocumentExtractionResponse] = None
