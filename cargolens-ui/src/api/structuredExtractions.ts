import { apiClient } from './client'
import {
  StructuredExtractionResponse,
  StructuredExtractionHistoryResponse,
  FieldEvidenceResponse,
} from '../types/structured_extraction'

export const getLatestStructuredExtraction = async (
  shipmentId: string,
  documentId: string
): Promise<StructuredExtractionResponse> => {
  const response = await apiClient.get<StructuredExtractionResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/structured-extraction`
  )
  return response.data
}

export const triggerStructuredExtraction = async (
  shipmentId: string,
  documentId: string
): Promise<StructuredExtractionResponse> => {
  const response = await apiClient.post<StructuredExtractionResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/structured-extraction`
  )
  return response.data
}

export const getStructuredExtractionHistory = async (
  shipmentId: string,
  documentId: string
): Promise<StructuredExtractionHistoryResponse> => {
  const response = await apiClient.get<StructuredExtractionHistoryResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/structured-extraction/history`
  )
  return response.data
}

export const getFieldEvidence = async (
  shipmentId: string,
  documentId: string,
  extractionId: string,
  fieldName: string
): Promise<FieldEvidenceResponse> => {
  const response = await apiClient.get<FieldEvidenceResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/structured-extraction/${extractionId}/fields/${fieldName}/evidence`
  )
  return response.data
}
