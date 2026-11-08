export type ValidationOutcome =
  | 'PASS'
  | 'FAIL'
  | 'MISSING_DATA'
  | 'NOT_APPLICABLE'
  | 'INFO'

export type ValidationSeverity = 'ERROR' | 'WARNING' | 'INFO'

export interface ValidationResultItem {
  id: string
  shipment_id: string
  run_id: string
  rule_id: string
  rule_name: string
  severity: ValidationSeverity
  outcome: ValidationOutcome
  explanation: string
  compared_values?: Record<string, unknown> | null
  source_document_ids?: string[] | null
  created_at: string
}

export interface ShipmentValidationsSummaryResponse {
  shipment_id: string
  run_id?: string | null
  total_rules: number
  passed_count: number
  failed_count: number
  missing_data_count: number
  not_applicable_count: number
  info_count: number
  has_blocking_failures: boolean
  results: ValidationResultItem[]
}

export interface ValidationIssueItem {
  id: string
  shipment_id: string
  shipment_number: string
  client_name: string
  run_id: string
  rule_id: string
  rule_name: string
  severity: ValidationSeverity
  outcome: ValidationOutcome
  explanation: string
  compared_values?: Record<string, unknown> | null
  source_document_ids?: string[] | null
  created_at: string
}

export interface ValidationIssuesListResponse {
  items: ValidationIssueItem[]
  total: number
}
