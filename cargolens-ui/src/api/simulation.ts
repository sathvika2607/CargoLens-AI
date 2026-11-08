import { apiClient } from './client'
import type {
  SimulationScenarioListResponse,
  SimulationStatusResponse,
  SimulationRunRequest,
  SimulationRunResponse,
} from '../types/simulation'

export const getSimulationScenarios = async (): Promise<SimulationScenarioListResponse> => {
  const response = await apiClient.get<SimulationScenarioListResponse>('/api/v1/simulation/scenarios')
  return response.data
}

export const getSimulationStatus = async (): Promise<SimulationStatusResponse> => {
  const response = await apiClient.get<SimulationStatusResponse>('/api/v1/simulation/status')
  return response.data
}

export const runSimulation = async (payload: SimulationRunRequest): Promise<SimulationRunResponse> => {
  const response = await apiClient.post<SimulationRunResponse>('/api/v1/simulation/run', payload)
  return response.data
}

export const resetSimulation = async (): Promise<{ success: boolean; cleaned_count: number; message: string }> => {
  const response = await apiClient.delete<{ success: boolean; cleaned_count: number; message: string }>('/api/v1/simulation/reset')
  return response.data
}
