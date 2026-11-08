import { apiClient } from './client'
import { AnalyticsOverviewResponse } from '../types/analytics'

export const getAnalyticsOverview = async (
  startDate?: string,
  endDate?: string,
  interval?: string
): Promise<AnalyticsOverviewResponse> => {
  const params: Record<string, string> = {}
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  if (interval) params.interval = interval

  const response = await apiClient.get<AnalyticsOverviewResponse>(
    '/api/v1/analytics/overview',
    { params }
  )
  return response.data
}

export const fetchAnalyticsOverview = getAnalyticsOverview
