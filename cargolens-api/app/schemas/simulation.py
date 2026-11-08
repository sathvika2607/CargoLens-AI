import uuid
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SimulationScenarioItem(BaseModel):
    id: str
    code: str
    name: str
    shipment_number: str
    client_name: str
    description: str
    expected_status: str
    expected_validation_outcome: str
    triad_documents: List[str]


class SimulationScenarioListResponse(BaseModel):
    scenarios: List[SimulationScenarioItem]
    environment: str
    allow_simulation: bool
    anthropic_configured: bool
    anthropic_model: str
    default_provider: str


class SimulationRunRequest(BaseModel):
    scenario_type: str = Field(
        default="ALL",
        description="Scenario code: 'ALL', 'COMPLETE_WORKFLOW', 'WEIGHT_DISCREPANCY', 'MISSING_FINANCIAL', 'LOW_CONFIDENCE', or 'INCOMPLETE_SET'",
    )
    provider_type: str = Field(
        default="fixture",
        description="AI extraction provider: 'fixture' (Deterministic Development Provider) or 'claude' (Anthropic Claude Vision)",
    )


class SimulationDocumentItem(BaseModel):
    id: uuid.UUID
    document_type: str
    filename: str
    file_size_bytes: int
    sha256_checksum: str
    status: str


class SimulationExtractionSummary(BaseModel):
    provider: str
    model: str
    status: str
    average_confidence: Optional[float] = None
    low_confidence_fields: List[str] = []
    missing_fields: List[str] = []


class SimulationValidationSummary(BaseModel):
    total_rules: int
    passed_count: int
    failed_count: int
    missing_data_count: int
    has_blocking_failures: bool
    notable_discrepancy: Optional[str] = None


class SimulationExportSummary(BaseModel):
    export_id: Optional[uuid.UUID] = None
    filename: Optional[str] = None
    sha256_checksum: Optional[str] = None
    row_count: Optional[int] = None
    download_url: Optional[str] = None


class SimulationRunResult(BaseModel):
    scenario_type: str
    shipment_id: uuid.UUID
    shipment_number: str
    client_name: str
    status: str
    documents: List[SimulationDocumentItem]
    extraction: Optional[SimulationExtractionSummary] = None
    validation: Optional[SimulationValidationSummary] = None
    human_reviews_count: int = 0
    verification_ready: bool = False
    export: Optional[SimulationExportSummary] = None
    workspace_url: str
    review_url: Optional[str] = None


class SimulationRunResponse(BaseModel):
    success: bool
    message: str
    provider_used: str
    model_used: str
    results: List[SimulationRunResult]
    duration_seconds: float


class SimulationStatusResponse(BaseModel):
    environment: str
    allow_simulation: bool
    anthropic_configured: bool
    anthropic_model: str
    total_demo_shipments: int
    demo_shipments: List[Dict[str, Any]]
