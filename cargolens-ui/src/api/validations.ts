import { apiClient } from './client'
import {
  ShipmentValidationsSummaryResponse,
  ValidationIssuesListResponse,
  ValidationSeverity,
  ValidationOutcome,
} from '../types/validation'

export const getShipmentValidations = async (
  shipmentId: string
): Promise<ShipmentValidationsSummaryResponse> => {
  const response = await apiClient.get<ShipmentValidationsSummaryResponse>(
    `/api/v1/shipments/${shipmentId}/validations`
  )
  return response.data
}

export const runShipmentValidations = async (
  shipmentId: string
): Promise<ShipmentValidationsSummaryResponse> => {
  const response = await apiClient.post<ShipmentValidationsSummaryResponse>(
    `/api/v1/shipments/${shipmentId}/validations/run`
  )
  return response.data
}

export interface ValidationIssuesParams {
  shipment_id?: string
  severity?: ValidationSeverity
  outcome?: ValidationOutcome
  limit?: number
  offset?: number
}

export const listValidationIssues = async (
  params?: ValidationIssuesParams
): Promise<ValidationIssuesListResponse> => {
  const response = await apiClient.get<ValidationIssuesListResponse>(
    '/api/v1/validations/issues',
    { params }
  )
  return response.data
}
