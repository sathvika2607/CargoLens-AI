import { apiClient } from './client'
import { DashboardStatsResponse } from '../types/dashboard'

export const fetchDashboardStats = async (): Promise<DashboardStatsResponse> => {
  const response = await apiClient.get<DashboardStatsResponse>('/api/v1/dashboard/stats')
  return response.data
}
