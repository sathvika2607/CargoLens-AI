import { apiClient } from './client'
import { HealthResponse, DatabaseHealthResponse } from '../types/api'

export const fetchApiHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>('/health')
  return response.data
}

export const fetchDbHealth = async (): Promise<DatabaseHealthResponse> => {
  const response = await apiClient.get<DatabaseHealthResponse>('/health/db')
  return response.data
}
