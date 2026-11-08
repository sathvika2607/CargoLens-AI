export type ShipmentStatus =
  | 'CREATED'
  | 'DOCUMENTS_PENDING'
  | 'PROCESSING'
  | 'REVIEW_REQUIRED'
  | 'VERIFIED'
  | 'EXPORTED'
  | 'FAILED'

export interface Shipment {
  id: string
  shipment_number: string
  client_name: string
  origin_country: string
  product_description: string | null
  quantity: number | null
  unit_price: number | null
  currency: string | null
  gross_weight_kg: number | null
  status: ShipmentStatus
  is_demo?: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface ShipmentCreatePayload {
  shipment_number: string
  client_name: string
  origin_country: string
  product_description?: string
  quantity?: number
  unit_price?: number
  currency?: string
  gross_weight_kg?: number
}

export interface ShipmentUpdatePayload {
  client_name?: string
  origin_country?: string
  product_description?: string
  quantity?: number
  unit_price?: number
  currency?: string
  gross_weight_kg?: number
  status?: ShipmentStatus
}

export interface ShipmentListResponse {
  items: Shipment[]
  total: number
  page: number
  limit: number
  total_pages: number
  status_summary?: Record<string, number>
}
