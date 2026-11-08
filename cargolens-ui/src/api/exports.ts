import { apiClient } from './client'
import {
  ExportReadinessResponse,
  ShipmentExportListResponse,
} from '../types/export'

export const getExportReadiness = async (
  shipmentId: string
): Promise<ExportReadinessResponse> => {
  const response = await apiClient.get<ExportReadinessResponse>(
    `/api/v1/shipments/${shipmentId}/export-readiness`
  )
  return response.data
}

export const fetchExportReadiness = getExportReadiness

export const exportShipmentCsv = async (
  shipmentId: string,
  template: string = 'STANDARD_CUSTOMS_CLEARANCE'
): Promise<{ filename: string; checksum: string }> => {
  const response = await apiClient.post(
    `/api/v1/shipments/${shipmentId}/export`,
    null,
    {
      params: { template },
      responseType: 'blob',
    }
  )

  // Extract filename from Content-Disposition header if available
  let filename = `cargolens_export_${shipmentId}.csv`
  const disposition = response.headers['content-disposition']
  if (disposition) {
    const filenameMatch = disposition.match(/filename="?([^"]+)"?/)
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1]
    }
  }

  const checksum = response.headers['x-export-checksum'] || ''

  // Create blob and trigger browser download
  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)

  return { filename, checksum }
}

export const listShipmentExports = async (
  shipmentId: string
): Promise<ShipmentExportListResponse> => {
  const response = await apiClient.get<ShipmentExportListResponse>(
    `/api/v1/shipments/${shipmentId}/exports`
  )
  return response.data
}

export const fetchShipmentExports = listShipmentExports

export const downloadExportSnapshot = async (
  shipmentId: string,
  exportId: string,
  defaultFilename: string = 'export_snapshot.csv'
): Promise<void> => {
  const response = await apiClient.get(
    `/api/v1/shipments/${shipmentId}/exports/${exportId}/download`,
    { responseType: 'blob' }
  )

  let filename = defaultFilename
  const disposition = response.headers['content-disposition']
  if (disposition) {
    const filenameMatch = disposition.match(/filename="?([^"]+)"?/)
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1]
    }
  }

  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}
