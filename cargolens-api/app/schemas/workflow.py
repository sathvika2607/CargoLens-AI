from typing import List, Dict
from uuid import UUID
from pydantic import BaseModel
from app.schemas.shipment import ShipmentResponse


class VerificationReadinessResponse(BaseModel):
    shipment_id: UUID
    current_status: str
    is_ready: bool
    documents_present: Dict[str, bool]
    documents_missing: List[str]
    all_documents_present: bool
    all_extractions_completed: bool
    blocking_validation_failures_count: int
    has_blocking_failures: bool
    human_reviews_count: int
    unreviewed_mandatory_fields: List[str] = []
    all_mandatory_fields_reviewed: bool = True
    missing_requirements: List[str]


class VerifyShipmentResponse(BaseModel):
    success: bool
    message: str
    shipment: ShipmentResponse
