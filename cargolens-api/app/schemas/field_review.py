from decimal import Decimal, InvalidOperation
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.field_review import FieldReviewActionType, ReviewProvenance

DECIMAL_FIELDS = {
    "gross_weight_kg",
    "net_weight_kg",
    "grand_total",
    "subtotal",
    "freight_charges",
    "insurance_charges",
    "other_charges",
    "quantity",
    "unit_price",
}

INTEGER_FIELDS = {
    "package_count",
}


class FieldReviewCreate(BaseModel):
    """Payload for human confirmation or correction of an extracted field."""
    field_name: str = Field(..., min_length=1, max_length=100)
    action: FieldReviewActionType = Field(...)
    corrected_value: Optional[str] = Field(None, description="Human-corrected value (required if action is CORRECTED)")
    reason: Optional[str] = Field(None, max_length=500, description="Explanation for the human correction (mandatory when action is CORRECTED)")

    @model_validator(mode="after")
    def validate_corrections(self) -> "FieldReviewCreate":
        if self.action == FieldReviewActionType.CORRECTED:
            if not self.reason or not self.reason.strip():
                raise ValueError("reason must be provided when action is CORRECTED")
            self.reason = self.reason.strip()

            if not self.corrected_value or not self.corrected_value.strip():
                raise ValueError("corrected_value must be provided when action is CORRECTED")
            cleaned = self.corrected_value.strip()

            # Type validation for known numeric fields
            if self.field_name in DECIMAL_FIELDS:
                try:
                    num = Decimal(cleaned.replace(",", ""))
                    if num < 0:
                        raise ValueError(f"{self.field_name} must be a non-negative decimal value")
                except (InvalidOperation, ValueError) as e:
                    raise ValueError(f"Invalid decimal value '{cleaned}' for numeric field {self.field_name}") from e
            elif self.field_name in INTEGER_FIELDS:
                try:
                    num_int = int(cleaned.replace(",", ""))
                    if num_int < 0:
                        raise ValueError(f"{self.field_name} must be a non-negative integer")
                except ValueError as e:
                    raise ValueError(f"Invalid integer value '{cleaned}' for integer field {self.field_name}") from e

            self.corrected_value = cleaned
        return self


class FieldReviewResponse(BaseModel):
    """Response representing an individual human review audit record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shipment_id: UUID
    document_id: UUID
    extraction_id: Optional[UUID]
    field_name: str
    action: FieldReviewActionType
    provenance: ReviewProvenance = ReviewProvenance.USER_ACTION
    original_value: Optional[str]
    corrected_value: Optional[str]
    reason: Optional[str]
    reviewer_id: UUID
    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    created_at: str


class FieldReviewListResponse(BaseModel):
    items: List[FieldReviewResponse]
    total: int
