import { apiClient } from './client'
import {
  DocumentItem,
  DocumentListResponse,
  DocumentType,
  ProcessingJobListResponse,
  DocumentExtraction,
  DocumentExtractionPagesListResponse,
  DocumentExtractionHistoryResponse,
  DocumentProcessingStatusResponse,
  ProcessingJob,
} from '../types/document'

export const uploadDocument = async (
  shipmentId: string,
  documentType: DocumentType,
  file: File,
  onProgress?: (progressPercent: number) => void
): Promise<DocumentItem> => {
  const formData = new FormData()
  formData.append('document_type', documentType)
  formData.append('file', file)

  const response = await apiClient.post<DocumentItem>(
    `/api/v1/shipments/${shipmentId}/documents`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percent)
        }
      },
    }
  )
  return response.data
}

export const listShipmentDocuments = async (shipmentId: string): Promise<DocumentListResponse> => {
  const response = await apiClient.get<DocumentListResponse>(
    `/api/v1/shipments/${shipmentId}/documents`
  )
  return response.data
}

export const listDocuments = listShipmentDocuments

export const getDocument = async (
  shipmentId: string,
  documentId: string
): Promise<DocumentItem> => {
  const response = await apiClient.get<DocumentItem>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}`
  )
  return response.data
}

export const downloadDocument = async (
  shipmentId: string,
  documentId: string,
  fallbackFilename: string
): Promise<void> => {
  const response = await apiClient.get(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/download`,
    {
      responseType: 'blob',
    }
  )

  // Extract filename from Content-Disposition header if available
  let downloadFilename = fallbackFilename
  const rawDisposition = response.headers['content-disposition']
  const disposition = typeof rawDisposition === 'string' ? rawDisposition : ''
  if (disposition && disposition.includes('filename=')) {
    const filenameMatch = disposition.match(/filename="?([^";]+)"?/)
    if (filenameMatch && filenameMatch[1]) {
      downloadFilename = filenameMatch[1]
    }
  }

  // Create temporary URL and trigger download
  const rawContentType = response.headers['content-type']
  const mimeType = typeof rawContentType === 'string' ? rawContentType : 'application/octet-stream'
  const blob = new Blob([response.data], {
    type: mimeType,
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', downloadFilename)
  document.body.appendChild(link)
  link.click()
  link.parentNode?.removeChild(link)
  window.URL.revokeObjectURL(url)
}

export const listDocumentVersions = async (
  shipmentId: string,
  documentId: string
): Promise<DocumentListResponse> => {
  const response = await apiClient.get<DocumentListResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/versions`
  )
  return response.data
}

export const listDocumentJobs = async (
  documentId: string
): Promise<ProcessingJobListResponse> => {
  const response = await apiClient.get<ProcessingJobListResponse>(
    `/api/v1/documents/${documentId}/jobs`
  )
  return response.data
}

export const getDocumentExtraction = async (
  shipmentId: string,
  documentId: string
): Promise<DocumentExtraction> => {
  const response = await apiClient.get<DocumentExtraction>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/extraction`
  )
  return response.data
}

export const getDocumentExtractionPages = async (
  shipmentId: string,
  documentId: string,
  page: number = 1,
  pageSize: number = 50,
  attemptNumber?: number
): Promise<DocumentExtractionPagesListResponse> => {
  const params: Record<string, string | number> = { page, page_size: pageSize }
  if (attemptNumber) {
    params.attempt_number = attemptNumber
  }
  const response = await apiClient.get<DocumentExtractionPagesListResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/extraction/pages`,
    { params }
  )
  return response.data
}

export const getDocumentExtractionHistory = async (
  shipmentId: string,
  documentId: string
): Promise<DocumentExtractionHistoryResponse> => {
  const response = await apiClient.get<DocumentExtractionHistoryResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/extraction/history`
  )
  return response.data
}

export const getDocumentProcessingStatus = async (
  shipmentId: string,
  documentId: string
): Promise<DocumentProcessingStatusResponse> => {
  const response = await apiClient.get<DocumentProcessingStatusResponse>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/processing-status`
  )
  return response.data
}

export const triggerDocumentProcessing = async (
  shipmentId: string,
  documentId: string
): Promise<ProcessingJob> => {
  const response = await apiClient.post<ProcessingJob>(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/process`
  )
  return response.data
}

export const fetchDocumentPageImage = async (
  shipmentId: string,
  documentId: string,
  pageNumber: number,
  cacheBuster?: string
): Promise<{ imageUrl: string; totalPages: number; currentPage: number }> => {
  const params: Record<string, string> = {}
  if (cacheBuster) {
    params.v = cacheBuster
  }
  const response = await apiClient.get(
    `/api/v1/shipments/${shipmentId}/documents/${documentId}/pages/${pageNumber}/image`,
    { params, responseType: 'blob' }
  )
  const totalPages = parseInt(response.headers['x-total-pages'] || '1', 10)
  const currentPage = parseInt(response.headers['x-current-page'] || String(pageNumber), 10)
  const imageUrl = URL.createObjectURL(response.data)
  return { imageUrl, totalPages, currentPage }
}
