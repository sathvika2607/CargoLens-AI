import { Shipment } from './shipment'

export interface VerificationReadinessResponse {
  shipment_id: string
  current_status: string
  is_ready: boolean
  documents_present: Record<string, boolean>
  documents_missing: string[]
  all_documents_present: boolean
  all_extractions_completed: boolean
  blocking_validation_failures_count: number
  has_blocking_failures: boolean
  human_reviews_count: number
  unreviewed_mandatory_fields?: string[]
  all_mandatory_fields_reviewed?: boolean
  missing_requirements: string[]
}

export interface VerifyShipmentResponse {
  success: boolean
  message: string
  shipment: Shipment
}
