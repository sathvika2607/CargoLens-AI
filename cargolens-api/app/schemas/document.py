from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentType, DocumentProcessingStatus


class DocumentResponse(BaseModel):
    id: UUID
    shipment_id: UUID
    document_type: DocumentType
    original_filename: str
    mime_type: str
    file_extension: str
    file_size_bytes: int
    sha256_checksum: str
    version: int
    uploaded_by: UUID
    processing_status: DocumentProcessingStatus
    is_active: bool
    is_latest: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
