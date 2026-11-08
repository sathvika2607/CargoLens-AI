import { apiClient } from './client'
import {
  VerificationReadinessResponse,
  VerifyShipmentResponse,
} from '../types/workflow'

export const getVerificationReadiness = async (
  shipmentId: string
): Promise<VerificationReadinessResponse> => {
  const response = await apiClient.get<VerificationReadinessResponse>(
    `/api/v1/shipments/${shipmentId}/verification-readiness`
  )
  return response.data
}

export const fetchVerificationReadiness = getVerificationReadiness

export const verifyShipment = async (
  shipmentId: string
): Promise<VerifyShipmentResponse> => {
  const response = await apiClient.post<VerifyShipmentResponse>(
    `/api/v1/shipments/${shipmentId}/verify`
  )
  return response.data
}
