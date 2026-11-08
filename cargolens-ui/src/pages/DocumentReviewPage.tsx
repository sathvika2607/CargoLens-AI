import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Download,
  Check,
  Edit3,
  AlertTriangle,
  ArrowLeft,
  RefreshCw,
  ExternalLink,
  Loader2,
  Search,
  Sparkles,
  HelpCircle,
  FileText,
} from 'lucide-react'
import { getShipment, listShipments } from '../api/shipments'
import { listDocuments, fetchDocumentPageImage, downloadDocument } from '../api/documents'
import { getLatestStructuredExtraction } from '../api/structuredExtractions'
import { fetchShipmentReviews, submitFieldReview } from '../api/reviews'
import { runShipmentValidations } from '../api/validations'

interface DocumentPageItemProps {
  shipmentId: string
  documentId: string
  pageNumber: number
  totalPages: number
  zoomLevel: number
  docTag: string
  initialData?: { imageUrl: string; totalPages: number; currentPage: number }
}

const DocumentPageItem: React.FC<DocumentPageItemProps> = ({
  shipmentId,
  documentId,
  pageNumber,
  totalPages,
  zoomLevel,
  docTag,
  initialData,
}) => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['docPageImage', shipmentId, documentId, pageNumber, docTag],
    queryFn: () => fetchDocumentPageImage(shipmentId, documentId, pageNumber, docTag),
    enabled: !!shipmentId && !!documentId,
    initialData: pageNumber === 1 ? initialData : undefined,
    staleTime: 30000,
  })

  useEffect(() => {
    return () => {
      if (data?.imageUrl && !initialData && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(data.imageUrl)
      }
    }
  }, [data?.imageUrl, initialData])

  return (
    <div
      id={`pdf-page-${pageNumber}`}
      data-testid={`pdf-page-${pageNumber}`}
      data-page-number={pageNumber}
      style={{
        width: `${zoomLevel}%`,
        maxWidth: `${Math.round(zoomLevel * 8.5)}px`,
        minWidth: '320px',
        transition: 'width 0.15s ease-out',
      }}
      className="shadow-2xl rounded-sm bg-white overflow-hidden relative border border-slate-300 my-2.5 ring-1 ring-black/5 shrink-0"
    >
      {totalPages > 1 && (
        <div className="bg-slate-100/90 border-b border-slate-200 px-3 py-1 flex items-center justify-between text-[11px] text-slate-500 font-medium select-none">
          <span className="font-mono text-[10px] uppercase tracking-wider text-slate-600">Sheet {pageNumber} of {totalPages}</span>
          <span className="text-[10px] text-slate-400 font-mono">INNSA Customs Inspection</span>
        </div>
      )}

      {isLoading ? (
        <div className="min-h-[420px] flex flex-col items-center justify-center text-slate-400 bg-white">
          <Loader2 className="h-7 w-7 animate-spin text-brand-600 mb-2" />
          <span className="text-xs font-semibold">Rendering Page {pageNumber}...</span>
        </div>
      ) : isError || !data ? (
        <div className="min-h-[220px] flex flex-col items-center justify-center p-6 text-center text-slate-600 bg-white space-y-2">
          <AlertTriangle className="h-6 w-6 text-amber-500 mx-auto" />
          <p className="text-xs font-bold text-slate-800">Page {pageNumber} Render Unavailable</p>
          <p className="text-[11px] text-slate-500">
            Could not render page image. Ensure document OCR has completed or download the original file.
          </p>
          <button
            onClick={() => refetch()}
            className="px-3 py-1 bg-brand-600 hover:bg-brand-700 text-white rounded text-xs font-semibold transition"
          >
            Retry Render
          </button>
        </div>
      ) : (
        <img
          src={data.imageUrl}
          alt={`Document Page ${pageNumber}`}
          className="w-full h-auto block select-none pointer-events-none"
        />
      )}
    </div>
  )
}

export const DocumentReviewPage: React.FC = () => {
  const { shipmentId: paramShipmentId, documentId: paramDocId } = useParams<{
    shipmentId?: string
    documentId?: string
  }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Fallback selector state if params are missing
  const [selectedShipmentId, setSelectedShipmentId] = useState<string>(paramShipmentId || '')
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>(paramDocId || '')

  useEffect(() => {
    if (paramShipmentId) setSelectedShipmentId(paramShipmentId)
    if (paramDocId) setSelectedDocumentId(paramDocId)
  }, [paramShipmentId, paramDocId])

  // Viewer state
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [zoomLevel, setZoomLevel] = useState<number>(100) // Percentage
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedFieldName, setSelectedFieldName] = useState<string | null>(null)

  // Correction inline state
  const [correctingField, setCorrectingField] = useState<{
    fieldName: string
    originalValue: any
    extractionId: string
  } | null>(null)
  const [correctionValue, setCorrectionValue] = useState('')
  const [correctionReason, setCorrectionReason] = useState('')
  const [correctionError, setCorrectionError] = useState<string | null>(null)

  // 1. Fetch Shipment list if selecting
  const { data: shipmentsList } = useQuery({
    queryKey: ['reviewShipmentsSelect'],
    queryFn: () => listShipments({ limit: 50 }),
    enabled: !selectedShipmentId,
  })

  // 2. Fetch Active Shipment
  const { data: shipment } = useQuery({
    queryKey: ['shipment', selectedShipmentId],
    queryFn: () => getShipment(selectedShipmentId),
    enabled: !!selectedShipmentId,
  })

  // 3. Fetch Documents of current shipment
  const { data: documentsData } = useQuery({
    queryKey: ['shipmentDocuments', selectedShipmentId],
    queryFn: () => listDocuments(selectedShipmentId),
    enabled: !!selectedShipmentId,
  })

  const documents = documentsData?.items || []

  // Auto-select first document if not selected
  useEffect(() => {
    if (documents.length > 0 && !selectedDocumentId) {
      setSelectedDocumentId(documents[0].id)
      setCurrentPage(1)
    }
  }, [documents, selectedDocumentId])

  const activeDoc = documents.find((d) => d.id === selectedDocumentId)
  const docTag = activeDoc ? `${activeDoc.id}-${activeDoc.sha256_checksum || activeDoc.file_size_bytes}` : 'default'

  // 4. Fetch Structured Extraction for active document
  const {
    data: extraction,
    isLoading: isExtractionLoading,
    refetch: refetchExtraction,
  } = useQuery({
    queryKey: ['structuredExtraction', selectedShipmentId, selectedDocumentId],
    queryFn: () => getLatestStructuredExtraction(selectedShipmentId, selectedDocumentId),
    enabled: !!selectedShipmentId && !!selectedDocumentId,
    retry: false,
  })

  // 5. Fetch Human Reviews for active document
  const {
    data: reviewsData,
    refetch: refetchReviews,
  } = useQuery({
    queryKey: ['docReviews', selectedShipmentId, selectedDocumentId],
    queryFn: () => fetchShipmentReviews(selectedShipmentId, selectedDocumentId),
    enabled: !!selectedShipmentId && !!selectedDocumentId,
  })

  const reviews = reviewsData?.items || []

  // 6. Fetch Page 1 Image & Total Page Count Metadata
  const {
    data: pageImageData,
    isLoading: isImageLoading,
    isError: isImageError,
    refetch: refetchImage,
  } = useQuery({
    queryKey: ['docPageImage', selectedShipmentId, selectedDocumentId, 1, docTag],
    queryFn: () => fetchDocumentPageImage(selectedShipmentId, selectedDocumentId, 1, docTag),
    enabled: !!selectedShipmentId && !!selectedDocumentId,
    staleTime: 30000,
  })

  useEffect(() => {
    return () => {
      if (pageImageData?.imageUrl && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(pageImageData.imageUrl)
      }
    }
  }, [pageImageData?.imageUrl])

  const totalPages = pageImageData?.totalPages || extraction?.total_page_count || 1
  const pagesList = Array.from({ length: totalPages }, (_, i) => i + 1)

  // Mutation: Submit Review Action (Confirm or Correct)
  const submitReviewMutation = useMutation({
    mutationFn: (payload: {
      shipmentId: string
      docId: string
      data: {
        extraction_id: string
        field_name: string
        action: 'CONFIRMED' | 'CORRECTED'
        original_value?: any
        corrected_value?: any
        reason?: string
      }
    }) => submitFieldReview(payload.shipmentId, payload.docId, payload.data),
    onSuccess: () => {
      setCorrectingField(null)
      setCorrectionValue('')
      setCorrectionReason('')
      setCorrectionError(null)
      refetchReviews()
      // Auto trigger cross-document validation run in background
      const sId = selectedShipmentId || paramShipmentId || ''
      if (sId) {
        runShipmentValidations(sId).catch(() => {})
        queryClient.invalidateQueries({ queryKey: ['shipmentValidations', sId] })
        queryClient.invalidateQueries({ queryKey: ['verificationReadiness', sId] })
      }
    },
    onError: (err: any) => {
      setCorrectionError(err.response?.data?.detail || err.message || 'Failed to submit review.')
    },
  })

  // Quick Confirm handler
  const handleConfirm = (fieldName: string, originalValue: any, extractionId: string) => {
    submitReviewMutation.mutate({
      shipmentId: selectedShipmentId || paramShipmentId || '',
      docId: selectedDocumentId || paramDocId || '',
      data: {
        extraction_id: extractionId,
        field_name: fieldName,
        action: 'CONFIRMED',
        original_value: originalValue,
        reason: 'Confirmed by human reviewer',
      },
    })
  }

  // Open Correction form
  const handleOpenCorrect = (fieldName: string, originalValue: any, extractionId: string) => {
    setCorrectingField({
      fieldName,
      originalValue,
      extractionId,
    })
    setCorrectionValue(originalValue !== null && originalValue !== undefined ? String(originalValue) : '')
    setCorrectionReason('')
    setCorrectionError(null)
  }

  // Submit Correction form
  const handleSaveCorrection = (e: React.FormEvent) => {
    e.preventDefault()
    if (!correctingField) return
    if (!correctionReason.trim()) {
      setCorrectionError('A rationale or reason is required when correcting extracted data.')
      return
    }

    const numericFields = [
      'gross_weight_kg',
      'grand_total',
      'subtotal',
      'tax_amount',
      'net_weight_kg',
      'package_count',
      'quantity',
    ]
    if (numericFields.includes(correctingField.fieldName)) {
      const num = Number(correctionValue)
      if (isNaN(num) || num < 0) {
        setCorrectionError(`Field '${correctingField.fieldName}' must be a valid non-negative number.`)
        return
      }
    }

    submitReviewMutation.mutate({
      shipmentId: selectedShipmentId || paramShipmentId || '',
      docId: selectedDocumentId || paramDocId || '',
      data: {
        extraction_id: correctingField.extractionId,
        field_name: correctingField.fieldName,
        action: 'CORRECTED',
        original_value: correctingField.originalValue,
        corrected_value: correctionValue,
        reason: correctionReason.trim(),
      },
    })
  }

  const viewerContainerRef = useRef<HTMLDivElement>(null)

  // Smooth scroll viewer to specific target page element
  const scrollToPage = (targetPage: number) => {
    if (targetPage < 1 || targetPage > totalPages) return
    setCurrentPage(targetPage)
    const pageEl = document.getElementById(`pdf-page-${targetPage}`)
    if (pageEl && viewerContainerRef.current) {
      pageEl.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  // Jump viewer to source page of a field
  const handleJumpToPage = (targetPage?: number | null) => {
    if (targetPage && targetPage > 0 && targetPage <= totalPages) {
      scrollToPage(targetPage)
    }
  }

  // Detect which page is actively in focal view as user scrolls
  const handleViewerScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (totalPages <= 1) return
    const container = e.currentTarget
    const containerTop = container.scrollTop
    const focalPoint = containerTop + container.clientHeight / 3

    for (let p = 1; p <= totalPages; p++) {
      const pageEl = document.getElementById(`pdf-page-${p}`)
      if (pageEl) {
        const pageTop = pageEl.offsetTop
        const pageBottom = pageTop + pageEl.offsetHeight
        if (pageTop <= focalPoint && pageBottom > focalPoint) {
          if (currentPage !== p) {
            setCurrentPage(p)
          }
          break
        }
      }
    }
  }

  // Download document
  const handleDownloadOriginal = () => {
    if (activeDoc) {
      downloadDocument(selectedShipmentId, activeDoc.id, activeDoc.original_filename)
    }
  }

  // If no shipment selected, render intuitive shipment & document selection screen
  if (!selectedShipmentId) {
    return (
      <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200">
          <h1 className="text-2xl font-bold text-slate-900">Document Review Workspace</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Select a consignment and uploaded document to begin split-screen document intelligence review.
          </p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs max-w-2xl space-y-4">
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
            Select Shipment for Review
          </label>
          <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
            {shipmentsList?.items.map((shp) => (
              <div
                key={shp.id}
                onClick={() => {
                  setSelectedShipmentId(shp.id)
                  navigate(`/review/${shp.id}`)
                }}
                className="py-3 px-3 flex items-center justify-between hover:bg-slate-50 cursor-pointer rounded-lg transition"
              >
                <div>
                  <span className="font-mono font-bold text-brand-600">{shp.shipment_number}</span>
                  <p className="text-xs text-slate-500">{shp.client_name} • {shp.origin_country || 'Origin N/A'}</p>
                </div>
                <ChevronRight className="h-4 w-4 text-slate-400" />
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // Parse extracted fields dictionary
  const rawData = extraction?.extracted_data || {}
  const fieldsList = Object.entries(rawData)
  const filteredFields = fieldsList.filter(([name, data]) => {
    if (!searchTerm.trim()) return true
    const term = searchTerm.toLowerCase()
    const valStr = typeof data === 'object' && data !== null && 'value' in data ? String(data.value || '') : String(data || '')
    const evidenceStr = typeof data === 'object' && data !== null && 'evidence_text' in data ? String(data.evidence_text || '') : ''
    return (
      name.toLowerCase().includes(term) ||
      valStr.toLowerCase().includes(term) ||
      evidenceStr.toLowerCase().includes(term)
    )
  })

  return (
    <div className="h-auto lg:h-[calc(100vh-6.5rem)] lg:max-h-[calc(100vh-6.5rem)] flex flex-col space-y-3 -m-4 sm:-m-6 lg:-m-8 p-4 bg-slate-100">
      {/* Workspace Top Toolbar */}
      <div className="bg-white px-4 py-2.5 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <Link
            to={`/shipments/${selectedShipmentId}`}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
            title="Return to Consignment Workspace"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold text-slate-900">
                {shipment?.shipment_number || 'Loading...'}
              </span>
              <span className="text-slate-300">•</span>
              <span className="text-xs font-semibold text-slate-600 truncate max-w-[180px]">
                {shipment?.client_name}
              </span>
            </div>
          </div>

          {/* Document Switcher Dropdown */}
          <div className="flex items-center gap-1.5 pl-3 border-l border-slate-200">
            <span className="text-[11px] font-semibold text-slate-500 uppercase">Doc:</span>
            <select
              value={selectedDocumentId}
              onChange={(e) => {
                const nextId = e.target.value
                setSelectedDocumentId(nextId)
                setCurrentPage(1)
                navigate(`/review/${selectedShipmentId}/${nextId}`)
              }}
              className="text-xs font-semibold px-2 py-1 rounded-lg border border-slate-300 bg-slate-50 text-slate-800 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.document_type.replace(/_/g, ' ')} (v{doc.version})
                </option>
              ))}
            </select>
          </div>

          {/* Quick-Switch Triad Pill Tabs */}
          <div className="hidden sm:flex items-center gap-1 pl-2 border-l border-slate-200">
            {documents.map((doc) => {
              const isDocActive = doc.id === selectedDocumentId
              const docShortName =
                doc.document_type === 'COMMERCIAL_INVOICE'
                  ? 'Invoice'
                  : doc.document_type === 'PACKING_LIST'
                  ? 'Packing List'
                  : doc.document_type === 'BILL_OF_LADING'
                  ? 'Bill of Lading'
                  : String(doc.document_type).replace(/_/g, ' ')
              return (
                <button
                  key={doc.id}
                  onClick={() => {
                    setSelectedDocumentId(doc.id)
                    setCurrentPage(1)
                    navigate(`/review/${selectedShipmentId}/${doc.id}`)
                  }}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition ${
                    isDocActive
                      ? 'bg-brand-600 text-white shadow-xs'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  {docShortName}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              refetchExtraction()
              refetchReviews()
              refetchImage()
              queryClient.invalidateQueries({
                queryKey: ['docPageImage', selectedShipmentId, selectedDocumentId],
              })
            }}
            title="Refresh Extracted Data & Image"
            className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100"
          >
            <RefreshCw className="h-4 w-4" />
          </button>

          <button
            onClick={handleDownloadOriginal}
            title="Download Original File"
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold"
          >
            <Download className="h-3.5 w-3.5 text-slate-500" /> Original
          </button>

          <Link
            to={`/shipments/${selectedShipmentId}`}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold"
          >
            Consignment Workspace <ExternalLink className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      {/* Split-Screen Main Container */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0 lg:overflow-hidden">
        {/* LEFT PANE: High-Performance Document Viewer (Cols 7 of 12) */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col min-h-0 h-[600px] lg:h-full overflow-hidden">
          {/* Document Viewer Navigation Toolbar */}
          <div className="px-4 py-2 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between text-xs shrink-0">
            {/* Page Navigation */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => scrollToPage(Math.max(1, currentPage - 1))}
                disabled={currentPage <= 1}
                className="p-1 rounded border border-slate-200 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
                title="Previous Page"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>

              <span className="font-semibold text-slate-700 px-1">
                Page {currentPage} of {totalPages}
              </span>

              <button
                onClick={() => scrollToPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage >= totalPages}
                className="p-1 rounded border border-slate-200 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
                title="Next Page"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setZoomLevel((z) => Math.max(50, z - 15))}
                className="p-1 rounded hover:bg-slate-200 text-slate-600"
                title="Zoom Out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <span className="font-mono text-[11px] font-bold text-slate-700 w-12 text-center">
                {zoomLevel}%
              </span>
              <button
                onClick={() => setZoomLevel((z) => Math.min(250, z + 15))}
                className="p-1 rounded hover:bg-slate-200 text-slate-600"
                title="Zoom In"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setZoomLevel(100)}
                className="px-1.5 py-0.5 rounded hover:bg-slate-200 text-slate-600 text-[10px] font-semibold"
                title="Fit Width (100%)"
              >
                Fit Width
              </button>
              <button
                onClick={() => setZoomLevel(75)}
                className="px-1.5 py-0.5 rounded hover:bg-slate-200 text-slate-600 text-[10px] font-semibold"
                title="Fit Page (75%)"
              >
                Fit Page
              </button>
              <button
                onClick={() => setZoomLevel(100)}
                className="p-1 rounded hover:bg-slate-200 text-slate-600 ml-0.5"
                title="Reset Zoom 100%"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Rendered Document Viewport with continuous vertical scrolling */}
          <div
            ref={viewerContainerRef}
            id="pdf-viewer-scroll-container"
            data-testid="pdf-viewer-scroll-container"
            tabIndex={0}
            onScroll={handleViewerScroll}
            style={{
              scrollbarWidth: 'thin',
              scrollbarColor: '#94a3b8 #f1f5f9',
            }}
            className="flex-1 min-h-0 bg-slate-300/60 overflow-y-auto overflow-x-auto p-4 sm:p-6 flex flex-col items-center justify-start relative select-none pdf-viewer-scroller focus:outline-none"
          >
            {isImageLoading && !pageImageData ? (
              <div className="my-auto flex flex-col items-center justify-center text-slate-500">
                <Loader2 className="h-8 w-8 animate-spin text-brand-600 mb-2" />
                <span className="text-xs font-semibold">Rendering Document Preview...</span>
              </div>
            ) : isImageError && !pageImageData ? (
              <div className="my-auto p-6 bg-white rounded-xl border border-slate-300 text-center max-w-sm space-y-2">
                <AlertTriangle className="h-6 w-6 text-amber-500 mx-auto" />
                <p className="text-xs font-bold text-slate-800">Document Render Unavailable</p>
                <p className="text-[11px] text-slate-500">
                  Could not render page image. Ensure document OCR has completed or download the original file.
                </p>
                <button
                  onClick={() => refetchImage()}
                  className="px-3 py-1 bg-brand-600 text-white rounded text-xs font-semibold hover:bg-brand-700 transition"
                >
                  Retry Render
                </button>
              </div>
            ) : (
              pagesList.map((pageNum) => (
                <DocumentPageItem
                  key={`${selectedDocumentId}-p${pageNum}`}
                  shipmentId={selectedShipmentId}
                  documentId={selectedDocumentId}
                  pageNumber={pageNum}
                  totalPages={totalPages}
                  zoomLevel={zoomLevel}
                  docTag={docTag}
                  initialData={pageNum === 1 ? pageImageData : undefined}
                />
              ))
            )}
          </div>
        </div>

        {/* RIGHT PANE: Extracted Fields & Controlled Review Workspace (Cols 5 of 12) */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col min-h-0 h-[500px] lg:h-full overflow-hidden">
          {/* Review Header & Filter */}
          <div className="p-3.5 border-b border-slate-200 bg-slate-50/80 space-y-2 shrink-0">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-brand-600" />
                  Extracted Intelligence & Review Form
                </h3>
                <span className="text-[11px] text-slate-500">
                  {reviews.length} reviewed • {fieldsList.length - reviews.length} awaiting human review
                </span>
              </div>
            </div>

            {/* Field Search Input */}
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Filter extracted fields..."
                className="w-full pl-8 pr-3 py-1 text-xs rounded-md border border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
          </div>

          {/* Fields Scrollable List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0 pdf-viewer-scroller">
            {isExtractionLoading ? (
              <div className="py-12 flex flex-col items-center justify-center text-slate-500">
                <Loader2 className="h-6 w-6 animate-spin text-brand-600 mb-2" />
                <span className="text-xs font-medium">Loading field extractions...</span>
              </div>
            ) : filteredFields.length === 0 ? (
              <div className="py-12 text-center text-slate-400 text-xs">
                {searchTerm ? 'No fields match your search term.' : 'No extracted fields found for this document.'}
              </div>
            ) : (
              filteredFields.map(([fieldName, fieldData]) => {
                const isObj = typeof fieldData === 'object' && fieldData !== null
                const rawValue = isObj && 'value' in fieldData ? fieldData.value : fieldData
                const confidence = isObj && 'confidence' in fieldData ? fieldData.confidence : null
                const sourcePage = isObj && 'source_page_number' in fieldData ? fieldData.source_page_number : null
                const evidenceText = isObj && 'evidence_text' in fieldData ? fieldData.evidence_text : null

                const humanReview = reviews.find((r) => r.field_name === fieldName)
                const isConfirmed = humanReview?.action === 'CONFIRMED'
                const isCorrected = humanReview?.action === 'CORRECTED'
                const isSelected = selectedFieldName === fieldName
                const isUnstated = rawValue === null || rawValue === undefined

                return (
                  <div
                    key={fieldName}
                    onClick={() => {
                      setSelectedFieldName(fieldName)
                      if (sourcePage && sourcePage !== currentPage) {
                        handleJumpToPage(sourcePage)
                      }
                    }}
                    className={`p-3.5 rounded-xl border text-xs space-y-2.5 transition-all cursor-pointer ${
                      isSelected
                        ? 'ring-2 ring-brand-500 border-brand-500 shadow-sm'
                        : isCorrected
                        ? 'bg-indigo-50/40 border-indigo-200'
                        : isConfirmed
                        ? 'bg-emerald-50/40 border-emerald-200'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    {/* Field Header: Name, Page Pill, Status Pill */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-slate-900">{fieldName}</span>
                        {sourcePage && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleJumpToPage(sourcePage)
                            }}
                            title={`Jump viewer to Page ${sourcePage}`}
                            className="px-1.5 py-0.5 rounded bg-slate-100 hover:bg-brand-100 hover:text-brand-700 font-mono text-[10px] text-slate-600 transition"
                          >
                            P.{sourcePage} ↗
                          </button>
                        )}
                      </div>

                      {/* Status Badges */}
                      <div className="flex items-center gap-1.5">
                        {confidence !== null && !isConfirmed && !isCorrected && (
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
                              confidence >= 0.85
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : 'bg-amber-50 text-amber-700 border border-amber-200'
                            }`}
                          >
                            {Math.round(confidence * 100)}%
                          </span>
                        )}

                        {isCorrected ? (
                          <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 text-[10px] font-bold">
                            Corrected
                          </span>
                        ) : isConfirmed ? (
                          humanReview?.provenance === 'DEMO_SEED' ? (
                            <span
                              data-testid="demo-fixture-badge"
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 text-amber-900 border border-amber-300 text-[9px] font-bold shadow-2xs"
                              title="Seeded demonstration fixture — not an authentic human verification"
                            >
                              <AlertTriangle className="h-2.5 w-2.5 text-amber-600 flex-shrink-0" />
                              DEMO FIXTURE — NOT A REAL HUMAN APPROVAL
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                              Confirmed
                            </span>
                          )
                        ) : isUnstated ? (
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200 text-[10px] font-medium">
                            Unstated Field
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-medium">
                            AI Extracted
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Field Values */}
                    <div>
                      {isCorrected ? (
                        <div className="space-y-0.5">
                          <div className="text-[11px]">
                            <span className="line-through text-slate-400 mr-2">
                              {String(humanReview.original_value)}
                            </span>
                            <span className="font-bold text-indigo-900">
                              {String(humanReview.corrected_value)}
                            </span>
                          </div>
                          <p className="text-[10px] text-indigo-700 italic">
                            Correction Reason: "{humanReview.reason}"
                          </p>
                        </div>
                      ) : !isUnstated ? (
                        <div className="font-semibold text-slate-800 text-[12px] break-words">
                          {String(rawValue)}
                        </div>
                      ) : (
                        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 text-[10.5px] font-medium">
                          <HelpCircle className="h-3 w-3 text-slate-400 shrink-0" />
                          <span>Not provided in source declaration</span>
                        </div>
                      )}
                    </div>

                    {/* Evidence Quote if present */}
                    {evidenceText && (
                      <div
                        className={`p-2.5 rounded-lg border text-[11px] space-y-1 transition ${
                          isSelected
                            ? 'bg-brand-50/70 border-brand-200 text-brand-900'
                            : 'bg-slate-50 border-slate-100 text-slate-600'
                        }`}
                      >
                        <div className="flex items-center gap-1 text-[9.5px] font-bold text-slate-400 uppercase tracking-wider">
                          <FileText className="h-3 w-3 text-brand-600" />
                          <span>Source Evidence Quote</span>
                        </div>
                        <p className="italic font-mono text-[10.5px]">"{evidenceText}"</p>
                      </div>
                    )}

                    {/* Review Actions Bar */}
                    <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-[11px]">
                      <span className="text-slate-400">
                        {humanReview ? (
                          humanReview.provenance === 'DEMO_SEED' ? (
                            <span className="text-amber-800 font-medium">
                              Demo fixture (attributed to {humanReview.reviewer_email || 'manager@cargolens.in'})
                            </span>
                          ) : (
                            `Reviewed by ${humanReview.reviewer_name || 'Officer'}`
                          )
                        ) : (
                          'Requires verification'
                        )}
                      </span>

                      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        {!isConfirmed && !isCorrected && (
                          <button
                            onClick={() =>
                              handleConfirm(
                                fieldName,
                                rawValue,
                                extraction?.id || ''
                              )
                            }
                            disabled={submitReviewMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-semibold border border-emerald-200 transition"
                          >
                            <Check className="h-3 w-3" /> Confirm
                          </button>
                        )}
                        <button
                          onClick={() =>
                            handleOpenCorrect(
                              fieldName,
                              rawValue,
                              extraction?.id || ''
                            )
                          }
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-amber-50 hover:bg-amber-100 text-amber-700 font-semibold border border-amber-200 transition"
                        >
                          <Edit3 className="h-3 w-3" /> Correct
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })
            )}

            {/* Inline Correction Form Modal / Drawer */}
            {correctingField && (
              <div className="sticky bottom-0 bg-white p-4 rounded-xl border-2 border-amber-400 shadow-xl space-y-3 z-10 text-xs animate-in slide-in-from-bottom duration-150">
                <div className="flex items-center justify-between font-bold text-amber-900">
                  <span>
                    Field Correction:{' '}
                    <strong className="font-mono text-slate-900">{correctingField.fieldName}</strong>
                  </span>
                  <button
                    onClick={() => setCorrectingField(null)}
                    className="text-slate-400 hover:text-slate-700 text-sm"
                  >
                    ×
                  </button>
                </div>

                {correctionError && (
                  <div className="p-2 rounded bg-red-100 border border-red-300 text-red-800 text-xs">
                    {correctionError}
                  </div>
                )}

                <form onSubmit={handleSaveCorrection} className="space-y-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      Correct Value
                    </label>
                    <input
                      type="text"
                      value={correctionValue}
                      onChange={(e) => setCorrectionValue(e.target.value)}
                      placeholder="Enter verified correct value"
                      className="w-full px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      Reason / Justification <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={correctionReason}
                      onChange={(e) => setCorrectionReason(e.target.value)}
                      placeholder="e.g. Scanned stamp obscured character, verified from packing slip"
                      className="w-full px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setCorrectingField(null)}
                      className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={submitReviewMutation.isPending}
                      className="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-semibold"
                    >
                      {submitReviewMutation.isPending ? 'Saving...' : 'Apply Correction'}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
