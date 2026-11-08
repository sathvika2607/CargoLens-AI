import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.validation import ValidationOutcome, ValidationSeverity


class ValidationResultResponse(BaseModel):
    id: uuid.UUID
    shipment_id: uuid.UUID
    run_id: uuid.UUID
    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    outcome: ValidationOutcome
    explanation: str
    compared_values: Optional[Dict[str, Any]] = None
    source_document_ids: Optional[List[str]] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class ShipmentValidationsSummaryResponse(BaseModel):
    shipment_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    total_rules: int
    passed_count: int
    failed_count: int
    missing_data_count: int
    not_applicable_count: int
    info_count: int
    has_blocking_failures: bool
    results: List[ValidationResultResponse]


class ValidationIssueItem(BaseModel):
    id: uuid.UUID
    shipment_id: uuid.UUID
    shipment_number: str
    client_name: str
    run_id: uuid.UUID
    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    outcome: ValidationOutcome
    explanation: str
    compared_values: Optional[Dict[str, Any]] = None
    source_document_ids: Optional[List[str]] = None
    created_at: str


class ValidationIssuesListResponse(BaseModel):
    items: List[ValidationIssueItem]
    total: int
