import { Shipment } from './shipment'

export interface RecentActivityItem {
  id: string
  action_type: string
  description: string
  actor_name?: string | null
  shipment_id?: string | null
  shipment_number?: string | null
  created_at: string
}

export interface ExecutiveDashboardStats {
  my_shipments_count: number
  documents_uploaded_count: number
  processing_in_progress_count: number
  documents_awaiting_review_count: number
  validation_failures_count: number
  recent_shipments: Shipment[]
  recent_activity: RecentActivityItem[]
}

export interface ManagerDashboardStats {
  total_shipments_count: number
  shipments_by_status: Record<string, number>
  documents_awaiting_review_count: number
  validation_failures_count: number
  processing_failures_count: number
  recent_shipments: Shipment[]
  recent_activity: RecentActivityItem[]
}

export interface DashboardStatsResponse {
  role: string
  executive?: ExecutiveDashboardStats | null
  manager?: ManagerDashboardStats | null
}
