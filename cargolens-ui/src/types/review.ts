export type FieldReviewActionType = 'CONFIRMED' | 'CORRECTED'
export type ReviewProvenance = 'USER_ACTION' | 'DEMO_SEED'

export interface FieldReviewItem {
  id: string
  shipment_id: string
  document_id: string
  extraction_id: string | null
  field_name: string
  action: FieldReviewActionType
  provenance?: ReviewProvenance
  original_value: any
  corrected_value: any
  reason: string | null
  reviewer_id: string
  reviewer_name?: string | null
  reviewer_email?: string | null
  reviewer_role?: string | null
  created_at: string
}

export interface FieldReviewListResponse {
  items: FieldReviewItem[]
  total: number
}

export interface FieldReviewCreatePayload {
  extraction_id?: string | null
  field_name: string
  action: FieldReviewActionType
  original_value?: any
  corrected_value?: any
  reason?: string | null
}
