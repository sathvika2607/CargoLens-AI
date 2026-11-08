export interface TimeSeriesPoint {
  date: string
  count: number
}

export interface StatusDistributionItem {
  status: string
  count: number
  percentage: number
}

export interface ValidationRuleBreakdownItem {
  rule_id: string
  rule_name: string
  severity: string
  failure_count: number
}

export interface ValidationSeverityBreakdownItem {
  severity: string
  count: number
}

export interface ValidationDiscrepancyDetail {
  id: string
  shipment_id: string
  shipment_number: string
  client_name: string
  rule_id: string
  rule_name: string
  severity: string
  explanation: string
  created_at: string
}

export interface DocumentTypeBreakdownItem {
  document_type: string
  count: number
}

export interface RecentExportActivityItem {
  export_id: string
  shipment_id: string
  shipment_number: string
  template_name: string
  exporter_name: string
  filename: string
  row_count: number
  sha256_checksum: string
  export_status?: string
  is_demo?: boolean
  exported_at: string
}

export interface AnalyticsOverviewResponse {
  role: string
  total_shipments: number
  shipments_by_status: Record<string, number>
  status_distribution: StatusDistributionItem[]

  // Documents & Ingestion
  total_documents: number
  documents_uploaded_by_type: Record<string, number>
  documents_by_type: DocumentTypeBreakdownItem[]
  document_processing_status_breakdown: Record<string, number>
  documents_awaiting_extraction: number
  extraction_failures: number

  // Quality & Governance
  shipments_awaiting_human_review: number
  validation_failures_count: number
  missing_data_issues_count: number
  validation_issues_by_rule: ValidationRuleBreakdownItem[]
  validation_issues_by_severity?: ValidationSeverityBreakdownItem[]
  validation_discrepancies?: ValidationDiscrepancyDetail[]
  distinct_shipments_with_discrepancies?: number

  // Completion & Customs Release
  verified_shipments_count: number
  exported_shipments_count: number

  // Time series trends
  volume_over_time: TimeSeriesPoint[]
  exports_over_time: TimeSeriesPoint[]
  aggregation_interval?: string

  // Recent activity
  recent_exports: RecentExportActivityItem[]

  // Date range echo
  start_date?: string | null
  end_date?: string | null
}
