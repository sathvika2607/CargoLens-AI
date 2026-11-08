import { apiClient } from './client'
import {
  Shipment,
  ShipmentCreatePayload,
  ShipmentUpdatePayload,
  ShipmentListResponse,
  ShipmentStatus,
} from '../types/shipment'

export interface ListShipmentParams {
  status?: ShipmentStatus
  search?: string
  page?: number
  limit?: number
}

export const listShipments = async (params: ListShipmentParams = {}): Promise<ShipmentListResponse> => {
  const response = await apiClient.get<ShipmentListResponse>('/api/v1/shipments', {
    params,
  })
  return response.data
}

export const getShipment = async (id: string): Promise<Shipment> => {
  const response = await apiClient.get<Shipment>(`/api/v1/shipments/${id}`)
  return response.data
}

export const createShipment = async (payload: ShipmentCreatePayload): Promise<Shipment> => {
  const response = await apiClient.post<Shipment>('/api/v1/shipments', payload)
  return response.data
}

export const updateShipment = async (id: string, payload: ShipmentUpdatePayload): Promise<Shipment> => {
  const response = await apiClient.patch<Shipment>(`/api/v1/shipments/${id}`, payload)
  return response.data
}
