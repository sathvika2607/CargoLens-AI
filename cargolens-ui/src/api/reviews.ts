import { apiClient } from './client'
import {
  FieldReviewItem,
  FieldReviewListResponse,
  FieldReviewCreatePayload,
} from '../types/review'

export const listDocumentReviews = async (
  shipmentId: string,
  documentId: string
): Promise<FieldReviewListResponse> => {
  const response = await apiClient.get<FieldReviewListResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/reviews`
  )
  return response.data
}

export const createFieldReview = async (
  shipmentId: string,
  documentId: string,
  payload: FieldReviewCreatePayload
): Promise<FieldReviewItem> => {
  const response = await apiClient.post<FieldReviewItem>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/reviews`,
    payload
  )
  return response.data
}

export const getShipmentReviewHistory = async (
  shipmentId: string
): Promise<FieldReviewListResponse> => {
  const response = await apiClient.get<FieldReviewListResponse>(
    `/api/v1/shipments/${shipmentId}/review-history`
  )
  return response.data
}

export const getGlobalAuditHistory = async (
  limit = 50
): Promise<FieldReviewListResponse> => {
  const response = await apiClient.get<FieldReviewListResponse>(
    '/api/v1/review/audit-history',
    { params: { limit } }
  )
  return response.data
}

// Aliases for unified naming
export const fetchShipmentReviews = listDocumentReviews
export const submitFieldReview = createFieldReview
export const fetchShipmentReviewHistory = getShipmentReviewHistory
export const fetchGlobalAuditHistory = getGlobalAuditHistory
