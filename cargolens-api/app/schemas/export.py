from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ExportTemplateType(str, Enum):
    STANDARD_CUSTOMS_CLEARANCE = "STANDARD_CUSTOMS_CLEARANCE"
    LINE_ITEM_DECLARATION = "LINE_ITEM_DECLARATION"


class ExportTemplateInfo(BaseModel):
    template_id: str
    name: str
    description: str
    columns: List[str]


class ExportReadinessResponse(BaseModel):
    shipment_id: UUID
    shipment_number: str
    current_status: str
    is_verified: bool
    all_mandatory_fields_reviewed: bool
    has_blocking_failures: bool
    is_ready_to_export: bool
    missing_requirements: List[str] = Field(default_factory=list)
    available_templates: List[ExportTemplateInfo] = Field(default_factory=list)


class ShipmentExportRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shipment_id: UUID
    exported_by: UUID
    exporter_name: Optional[str] = None
    exporter_email: Optional[str] = None
    template_name: str
    template_version: str
    filename: str
    sha256_checksum: str
    export_status: str
    row_count: int
    file_size_bytes: int
    error_message: Optional[str] = None
    exported_at: str


class ShipmentExportListResponse(BaseModel):
    items: List[ShipmentExportRecordResponse]
    total: int
