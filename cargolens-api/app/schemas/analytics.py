from typing import List, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class TimeSeriesPoint(BaseModel):
    date: str
    count: int


class StatusDistributionItem(BaseModel):
    status: str
    count: int
    percentage: float


class ValidationRuleBreakdownItem(BaseModel):
    rule_id: str
    rule_name: str
    severity: str
    failure_count: int


class ValidationSeverityBreakdownItem(BaseModel):
    severity: str
    count: int


class ValidationDiscrepancyDetail(BaseModel):
    id: UUID
    shipment_id: UUID
    shipment_number: str
    client_name: str
    rule_id: str
    rule_name: str
    severity: str
    explanation: str
    created_at: str


class DocumentTypeBreakdownItem(BaseModel):
    document_type: str
    count: int


class ProcessingStatusBreakdownItem(BaseModel):
    status: str
    count: int


class RecentExportActivityItem(BaseModel):
    export_id: UUID
    shipment_id: UUID
    shipment_number: str
    template_name: str
    exporter_name: str
    filename: str
    row_count: int
    sha256_checksum: str
    export_status: str = "COMPLETED"
    is_demo: bool = True
    exported_at: str


class AnalyticsOverviewResponse(BaseModel):
    role: str
    total_shipments: int
    shipments_by_status: Dict[str, int]
    status_distribution: List[StatusDistributionItem]

    # Documents & Ingestion
    total_documents: int
    documents_uploaded_by_type: Dict[str, int]
    documents_by_type: List[DocumentTypeBreakdownItem]
    document_processing_status_breakdown: Dict[str, int]
    documents_awaiting_extraction: int
    extraction_failures: int

    # Quality & Governance
    shipments_awaiting_human_review: int
    validation_failures_count: int
    missing_data_issues_count: int
    validation_issues_by_rule: List[ValidationRuleBreakdownItem]
    validation_issues_by_severity: List[ValidationSeverityBreakdownItem] = Field(default_factory=list)
    validation_discrepancies: List[ValidationDiscrepancyDetail] = Field(default_factory=list)
    distinct_shipments_with_discrepancies: int = 0

    # Completion & Customs Release
    verified_shipments_count: int
    exported_shipments_count: int

    # Time series trends
    volume_over_time: List[TimeSeriesPoint]
    exports_over_time: List[TimeSeriesPoint]
    aggregation_interval: str = "daily"

    # Recent activity
    recent_exports: List[RecentExportActivityItem]

    # Date range echo
    start_date: Optional[str] = None
    end_date: Optional[str] = None
