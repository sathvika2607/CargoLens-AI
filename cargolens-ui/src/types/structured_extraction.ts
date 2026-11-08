import { DocumentType } from './document'

export interface ExtractedFieldData<T = string | number> {
  value: T | null
  normalized_value?: T | null
  confidence?: number | null
  source_document_id?: string | null
  source_page_number?: number | null
  evidence_text?: string | null
  bounding_box?: {
    x_min: number
    y_min: number
    x_max: number
    y_max: number
  } | null
  extraction_method?: string | null
}

export interface StructuredExtractionResponse {
  id: string
  document_id: string
  document_type: DocumentType
  attempt_number: number
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'PARTIAL' | 'FAILED'
  provider: string
  model: string
  extraction_mode: string
  total_page_count: number
  processed_page_count: number
  extracted_data: Record<string, any> | null
  field_confidence_summary?: {
    average_confidence?: number | null
    field_count?: number
    high_confidence_count?: number
    low_confidence_count?: number
  } | null
  error_summary?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
}

export interface StructuredExtractionHistoryItem {
  id: string
  attempt_number: number
  status: string
  provider: string
  model: string
  extraction_mode: string
  total_page_count: number
  processed_page_count: number
  error_summary?: string | null
  completed_at?: string | null
  created_at: string
}

export interface StructuredExtractionHistoryResponse {
  document_id: string
  total_attempts: number
  history: StructuredExtractionHistoryItem[]
}

export interface FieldEvidenceResponse {
  field_name: string
  value: any
  normalized_value?: any
  confidence?: number | null
  source_document_id: string
  source_page_number?: number | null
  evidence_text?: string | null
  bounding_box?: {
    x_min: number
    y_min: number
    x_max: number
    y_max: number
  } | null
  extraction_method: string
}
