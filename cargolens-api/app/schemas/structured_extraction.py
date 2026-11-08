import uuid
from decimal import Decimal
from typing import Dict, Generic, List, Optional, TypeVar, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from app.models.document import DocumentType

T = TypeVar("T")


class BoundingBox(BaseModel):
    """Normalized bounding box coordinates (0.0 to 1.0) on the source page."""
    x: float
    y: float
    width: float
    height: float


class ExtractedField(BaseModel, Generic[T]):
    """
    Standard container for an extracted field value.
    Preserves raw extracted value, normalized value, source provenance,
    evidence snippet, and confidence score.
    """
    value: Optional[T] = None
    normalized_value: Optional[T] = None
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score between 0.0 and 1.0. None if unavailable. Never fabricated.",
    )
    source_document_id: Optional[uuid.UUID] = None
    source_page_number: Optional[int] = None
    evidence_text: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    extraction_method: Optional[str] = None  # e.g., 'claude_vision', 'claude_text'

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        # Strict validation: confidence must be between 0.0 and 1.0
        # If upstream gave 0-100%, normalize to 0.0-1.0
        val = float(v)
        if 1.0 < val <= 100.0:
            val = val / 100.0
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {v}")
        return round(val, 4)

    @property
    def is_present(self) -> bool:
        """Returns True if a non-null, non-empty value was extracted."""
        if self.value is None:
            return False
        if isinstance(self.value, str) and not self.value.strip():
            return False
        return True


# ==============================================================================
# Line Item Schemas
# ==============================================================================

class InvoiceLineItem(BaseModel):
    """Individual product line item on a Commercial Invoice."""
    item_number: Optional[int] = None
    description: ExtractedField[str] = Field(default_factory=ExtractedField)
    hsn_code: ExtractedField[str] = Field(default_factory=ExtractedField)  # If explicitly present
    quantity: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    unit_of_measure: ExtractedField[str] = Field(default_factory=ExtractedField)
    unit_price: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    line_total: ExtractedField[Decimal] = Field(default_factory=ExtractedField)


class PackingLineItem(BaseModel):
    """Individual cargo package/item entry on a Packing List."""
    item_number: Optional[int] = None
    description: ExtractedField[str] = Field(default_factory=ExtractedField)
    quantity: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    unit_of_measure: ExtractedField[str] = Field(default_factory=ExtractedField)
    package_count: ExtractedField[int] = Field(default_factory=ExtractedField)
    package_type: ExtractedField[str] = Field(default_factory=ExtractedField)  # e.g., CARTONS, PALLETS, DRUMS


# ==============================================================================
# Document-Specific Structured Extraction Schemas
# ==============================================================================

class CommercialInvoiceExtraction(BaseModel):
    """
    Structured extraction schema for Commercial Invoices.
    All fields default to null when absent from the source document.
    """
    invoice_number: ExtractedField[str] = Field(default_factory=ExtractedField)
    invoice_date: ExtractedField[str] = Field(default_factory=ExtractedField)
    seller_name: ExtractedField[str] = Field(default_factory=ExtractedField)
    seller_address: ExtractedField[str] = Field(default_factory=ExtractedField)
    buyer_name: ExtractedField[str] = Field(default_factory=ExtractedField)
    buyer_address: ExtractedField[str] = Field(default_factory=ExtractedField)
    currency: ExtractedField[str] = Field(default_factory=ExtractedField)
    incoterm: ExtractedField[str] = Field(default_factory=ExtractedField)  # e.g. FOB, CIF, CFR
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    subtotal: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    freight_charges: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    insurance_charges: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    other_charges: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    grand_total: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    gross_weight_kg: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    net_weight_kg: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    package_count: ExtractedField[int] = Field(default_factory=ExtractedField)


class PackingListExtraction(BaseModel):
    """
    Structured extraction schema for Packing Lists.
    All fields default to null when absent from the source document.
    """
    exporter_name: ExtractedField[str] = Field(default_factory=ExtractedField)
    importer_name: ExtractedField[str] = Field(default_factory=ExtractedField)
    invoice_reference: ExtractedField[str] = Field(default_factory=ExtractedField)
    line_items: List[PackingLineItem] = Field(default_factory=list)
    package_count: ExtractedField[int] = Field(default_factory=ExtractedField)
    package_type: ExtractedField[str] = Field(default_factory=ExtractedField)
    gross_weight_kg: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    net_weight_kg: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    dimensions: ExtractedField[str] = Field(default_factory=ExtractedField)
    container_numbers: List[ExtractedField[str]] = Field(default_factory=list)
    marks_and_numbers: ExtractedField[str] = Field(default_factory=ExtractedField)


class BillOfLadingExtraction(BaseModel):
    """
    Structured extraction schema for Bills of Lading (Ocean/Sea Waybill).
    All fields default to null when absent from the source document.
    """
    bl_number: ExtractedField[str] = Field(default_factory=ExtractedField)
    shipper_name: ExtractedField[str] = Field(default_factory=ExtractedField)
    consignee_name: ExtractedField[str] = Field(default_factory=ExtractedField)
    notify_party: ExtractedField[str] = Field(default_factory=ExtractedField)
    vessel_name: ExtractedField[str] = Field(default_factory=ExtractedField)
    voyage_number: ExtractedField[str] = Field(default_factory=ExtractedField)
    port_of_loading: ExtractedField[str] = Field(default_factory=ExtractedField)
    port_of_discharge: ExtractedField[str] = Field(default_factory=ExtractedField)
    place_of_receipt: ExtractedField[str] = Field(default_factory=ExtractedField)
    place_of_delivery: ExtractedField[str] = Field(default_factory=ExtractedField)
    container_numbers: List[ExtractedField[str]] = Field(default_factory=list)
    seal_numbers: List[ExtractedField[str]] = Field(default_factory=list)
    package_count: ExtractedField[int] = Field(default_factory=ExtractedField)
    goods_description: ExtractedField[str] = Field(default_factory=ExtractedField)
    gross_weight_kg: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    measurement_volume_cbm: ExtractedField[Decimal] = Field(default_factory=ExtractedField)
    issue_date: ExtractedField[str] = Field(default_factory=ExtractedField)


# Union / generic type for any document structured extraction
AnyStructuredDocument = Union[
    CommercialInvoiceExtraction,
    PackingListExtraction,
    BillOfLadingExtraction,
]


class StructuredExtractionResponse(BaseModel):
    """Response DTO for structured document extraction endpoint."""
    id: uuid.UUID
    document_id: uuid.UUID
    document_type: DocumentType
    attempt_number: int
    status: str
    provider: str
    model: str
    extraction_mode: str
    total_page_count: int = 0
    processed_page_count: int = 0
    extracted_data: Optional[Dict[str, Any]] = None
    field_confidence_summary: Optional[Dict[str, Any]] = None
    error_summary: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class StructuredExtractionHistoryItem(BaseModel):
    """Summary item for extraction history listing."""
    id: uuid.UUID
    attempt_number: int
    status: str
    provider: str
    model: str
    extraction_mode: str
    total_page_count: int = 0
    processed_page_count: int = 0
    error_summary: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class StructuredExtractionHistoryResponse(BaseModel):
    document_id: uuid.UUID
    total_attempts: int
    history: List[StructuredExtractionHistoryItem]


class FieldEvidenceResponse(BaseModel):
    field_name: str
    value: Any = None
    normalized_value: Any = None
    confidence: Optional[float] = None
    source_document_id: Optional[uuid.UUID] = None
    source_page_number: Optional[int] = None
    evidence_text: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    extraction_method: Optional[str] = None
