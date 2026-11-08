export interface SimulationScenarioItem {
  id: string
  code: string
  name: string
  shipment_number: string
  client_name: string
  description: string
  expected_status: string
  expected_validation_outcome: string
  triad_documents: string[]
}

export interface SimulationScenarioListResponse {
  scenarios: SimulationScenarioItem[]
  environment: string
  allow_simulation: boolean
  anthropic_configured: boolean
  anthropic_model: string
  default_provider: string
}

export interface SimulationRunRequest {
  scenario_type: string
  provider_type: string
}

export interface SimulationDocumentItem {
  id: string
  document_type: string
  filename: string
  file_size_bytes: number
  sha256_checksum: string
  status: string
}

export interface SimulationExtractionSummary {
  provider: string
  model: string
  status: string
  average_confidence?: number | null
  low_confidence_fields: string[]
  missing_fields: string[]
}

export interface SimulationValidationSummary {
  total_rules: number
  passed_count: number
  failed_count: number
  missing_data_count: number
  has_blocking_failures: boolean
  notable_discrepancy?: string | null
}

export interface SimulationExportSummary {
  export_id?: string | null
  filename?: string | null
  sha256_checksum?: string | null
  row_count?: number | null
  download_url?: string | null
}

export interface SimulationRunResult {
  scenario_type: string
  shipment_id: string
  shipment_number: string
  client_name: string
  status: string
  documents: SimulationDocumentItem[]
  extraction?: SimulationExtractionSummary | null
  validation?: SimulationValidationSummary | null
  human_reviews_count: number
  verification_ready: boolean
  export?: SimulationExportSummary | null
  workspace_url: string
  review_url?: string | null
}

export interface SimulationRunResponse {
  success: boolean
  message: string
  provider_used: string
  model_used: string
  results: SimulationRunResult[]
  duration_seconds: number
}

export interface ActiveDemoShipment {
  id: string
  shipment_number: string
  client_name: string
  status: string
  origin_country: string
  product_description?: string | null
  gross_weight_kg?: number | null
  currency?: string | null
  documents_count: number
  exported: boolean
  export_sha256?: string | null
  created_at?: string | null
}

export interface SimulationStatusResponse {
  environment: string
  allow_simulation: boolean
  anthropic_configured: boolean
  anthropic_model: string
  total_demo_shipments: number
  demo_shipments: ActiveDemoShipment[]
}
