export type DocumentType =
  | 'COMMERCIAL_INVOICE'
  | 'PACKING_LIST'
  | 'BILL_OF_LADING'

export type DocumentProcessingStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'FAILED'

export type JobStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'FAILED'

export interface DocumentItem {
  id: string
  shipment_id: string
  document_type: DocumentType
  original_filename: string
  mime_type: string
  file_extension: string
  file_size_bytes: number
  sha256_checksum: string
  version: number
  uploaded_by: string
  processing_status: DocumentProcessingStatus
  is_active: boolean
  is_latest?: boolean | null
  created_at: string
  updated_at: string
}

export type Document = DocumentItem

export interface DocumentListResponse {
  items: DocumentItem[]
  total: number
}

export interface ProcessingJob {
  id: string
  document_id: string
  job_type: string
  status: JobStatus
  attempt_count: number
  max_attempts: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

export interface ProcessingJobListResponse {
  items: ProcessingJob[]
  total: number
}

export type ExtractionStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
export type ExtractionMethod = 'DIGITAL_TEXT' | 'OCR' | 'HYBRID' | 'EMPTY' | 'FAILED'
export type ExtractionQualityStatus = 'GOOD' | 'LOW_CONFIDENCE' | 'EMPTY' | 'PARTIAL' | 'FAILED'
export type PageExtractionMethod = 'DIGITAL_TEXT' | 'OCR' | 'EMPTY' | 'FAILED'
export type PageProcessingStatus = 'COMPLETED' | 'FAILED' | 'EMPTY'

export interface DocumentExtraction {
  id: string
  document_id: string
  attempt_number: number
  status: ExtractionStatus
  extraction_method: ExtractionMethod
  raw_text: string
  page_count: number
  processed_page_count: number
  failed_page_count: number
  avg_confidence: number | null
  character_count: number
  quality_status: ExtractionQualityStatus
  error_summary: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface DocumentExtractionPage {
  id: string
  extraction_id: string
  page_number: number
  extraction_method: PageExtractionMethod
  raw_text: string
  ocr_confidence: number | null
  character_count: number
  processing_status: PageProcessingStatus
  error_message: string | null
  created_at: string
}

export interface DocumentExtractionPagesListResponse {
  items: DocumentExtractionPage[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface DocumentExtractionHistoryItem {
  id: string
  document_id: string
  attempt_number: number
  status: ExtractionStatus
  extraction_method: ExtractionMethod
  quality_status: ExtractionQualityStatus
  page_count: number
  avg_confidence: number | null
  character_count: number
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface DocumentExtractionHistoryResponse {
  items: DocumentExtractionHistoryItem[]
  total: number
}

export interface DocumentProcessingStatusResponse {
  document_id: string
  document_processing_status: DocumentProcessingStatus
  active_job_id: string | null
  job_status: JobStatus | null
  attempt_count: number
  max_attempts: number
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  latest_extraction: DocumentExtraction | null
}
