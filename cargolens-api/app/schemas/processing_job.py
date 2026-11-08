from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.processing_job import JobStatus


class ProcessingJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    job_type: str
    status: JobStatus
    attempt_count: int
    max_attempts: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProcessingJobListResponse(BaseModel):
    items: List[ProcessingJobResponse]
    total: int
