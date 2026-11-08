import React, { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  X,
  Box,
  Calendar,
  User,
  Globe,
  Tag,
  Layers,
  FileText,
  Upload,
  Download,
  History,
  Cpu,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import { Shipment, ShipmentStatus } from '../types/shipment'
import { DocumentItem, DocumentType, DocumentProcessingStatus } from '../types/document'
import { listShipmentDocuments, downloadDocument } from '../api/documents'
import { UploadDocumentModal } from './UploadDocumentModal'
import { DocumentVersionModal } from './DocumentVersionModal'
import { ProcessingJobsModal } from './ProcessingJobsModal'
import { ExtractedTextModal } from './ExtractedTextModal'

interface ShipmentDetailModalProps {
  shipment: Shipment | null
  isOpen: boolean
  onClose: () => void
  onEdit?: (shipment: Shipment) => void
}

const STATUS_CONFIG: Record<ShipmentStatus, { label: string; badgeClass: string }> = {
  CREATED: { label: 'Created', badgeClass: 'bg-slate-100 text-slate-700 border-slate-300' },
  DOCUMENTS_PENDING: { label: 'Documents Pending', badgeClass: 'bg-amber-50 text-amber-700 border-amber-300' },
  PROCESSING: { label: 'Processing', badgeClass: 'bg-sky-50 text-sky-700 border-sky-300' },
  REVIEW_REQUIRED: { label: 'Review Required', badgeClass: 'bg-rose-50 text-rose-700 border-rose-300' },
  VERIFIED: { label: 'Verified', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
  EXPORTED: { label: 'Exported', badgeClass: 'bg-purple-50 text-purple-700 border-purple-300' },
  FAILED: { label: 'Failed', badgeClass: 'bg-red-100 text-red-800 border-red-300' },
}

const DOC_TYPE_CONFIG: Record<DocumentType, { label: string; badgeClass: string }> = {
  COMMERCIAL_INVOICE: { label: 'Commercial Invoice', badgeClass: 'bg-brand-50 text-brand-700 border-brand-200' },
  PACKING_LIST: { label: 'Packing List', badgeClass: 'bg-amber-50 text-amber-700 border-amber-200' },
  BILL_OF_LADING: { label: 'Bill of Lading', badgeClass: 'bg-purple-50 text-purple-700 border-purple-200' },
}

const PROCESSING_STATUS_CONFIG: Record<DocumentProcessingStatus, { label: string; badgeClass: string; icon: React.ReactNode }> = {
  PENDING: {
    label: 'Pending',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: <Clock className="h-3 w-3 text-amber-600" />,
  },
  PROCESSING: {
    label: 'Processing',
    badgeClass: 'bg-sky-50 text-sky-700 border-sky-200',
    icon: <Loader2 className="h-3 w-3 text-sky-600 animate-spin" />,
  },
  COMPLETED: {
    label: 'Completed',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: <CheckCircle2 className="h-3 w-3 text-emerald-600" />,
  },
  FAILED: {
    label: 'Failed',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    icon: <AlertCircle className="h-3 w-3 text-rose-600" />,
  },
}

export const ShipmentDetailModal: React.FC<ShipmentDetailModalProps> = ({
  shipment,
  isOpen,
  onClose,
  onEdit,
}) => {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'overview' | 'documents'>('overview')

  // Sub-modals state
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [versionTarget, setVersionTarget] = useState<DocumentItem | null>(null)
  const [jobsTarget, setJobsTarget] = useState<DocumentItem | null>(null)
  const [extractionTargetDoc, setExtractionTargetDoc] = useState<DocumentItem | null>(null)

  // Fetch documents for this shipment
  const {
    data: docsData,
    isLoading: isDocsLoading,
    isError: isDocsError,
    error: docsError,
    refetch: refetchDocs,
    isFetching: isDocsFetching,
  } = useQuery({
    queryKey: ['shipmentDocuments', shipment?.id],
    queryFn: () => (shipment ? listShipmentDocuments(shipment.id) : Promise.resolve({ items: [], total: 0 })),
    enabled: isOpen && !!shipment?.id,
  })

  if (!isOpen || !shipment) return null

  const documents = docsData?.items || []
  const docCount = documents.length

  const statusInfo = STATUS_CONFIG[shipment.status] || {
    label: shipment.status,
    badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
  }

  const totalValue =
    shipment.quantity !== null &&
    shipment.quantity !== undefined &&
    shipment.unit_price !== null &&
    shipment.unit_price !== undefined
      ? Number(shipment.quantity) * Number(shipment.unit_price)
      : null

  const formatDate = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString('en-IN', {
        dateStyle: 'medium',
        timeStyle: 'short',
      })
    } catch {
      return isoString
    }
  }

  const handleDownload = async (doc: DocumentItem) => {
    try {
      await downloadDocument(shipment.id, doc.id, doc.original_filename)
    } catch {
      alert('Failed to download document file payload.')
    }
  }

  const handleUploadSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['shipmentDocuments', shipment.id] })
    queryClient.invalidateQueries({ queryKey: ['shipments'] })
    refetchDocs()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-50 text-brand-600">
              <Box className="h-6 w-6 stroke-[2]" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h3 className="text-lg font-bold text-slate-900 font-mono tracking-tight">
                  {shipment.shipment_number}
                </h3>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusInfo.badgeClass}`}
                >
                  {statusInfo.label}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Nhava Sheva Customs Entry Verification • Consignee: <strong className="text-slate-700">{shipment.client_name}</strong>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 px-6 pt-3 border-b border-slate-200 bg-white">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-3 px-3 text-xs font-semibold uppercase tracking-wider transition-all border-b-2 flex items-center gap-2 ${
              activeTab === 'overview'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <Layers className="h-4 w-4" /> Consignment Specifications
          </button>

          <button
            onClick={() => setActiveTab('documents')}
            className={`pb-3 px-3 text-xs font-semibold uppercase tracking-wider transition-all border-b-2 flex items-center gap-2 ${
              activeTab === 'documents'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <FileText className="h-4 w-4" /> Shipment Documents
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                docCount > 0 ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-500'
              }`}
            >
              {docCount}
            </span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6">
          {activeTab === 'overview' ? (
            <div className="space-y-6">
              {/* Core Consignment Info */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block mb-1">
                    Client / Importer
                  </span>
                  <span className="text-base font-semibold text-slate-900 block">
                    {shipment.client_name}
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
                    <Globe className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">
                      Origin Country
                    </span>
                    <span className="text-base font-semibold text-slate-900 block mt-0.5">
                      {shipment.origin_country}
                    </span>
                  </div>
                </div>
              </div>

              {/* Goods & Cargo Specifications */}
              <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-700">
                  <Layers className="h-4 w-4 text-brand-600" /> Declared Cargo Specifications
                </div>

                <div className="text-sm text-slate-800 bg-slate-50 p-3 rounded-lg border border-slate-100">
                  <span className="font-medium text-slate-600 block text-xs mb-0.5">Product Description:</span>
                  {shipment.product_description || (
                    <span className="text-slate-400 italic">No description provided</span>
                  )}
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <span className="text-[11px] font-medium text-slate-500 uppercase block">Quantity</span>
                    <span className="text-sm font-semibold font-mono text-slate-900">
                      {shipment.quantity !== null && shipment.quantity !== undefined
                        ? shipment.quantity.toLocaleString()
                        : '—'}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <span className="text-[11px] font-medium text-slate-500 uppercase block">Unit Price</span>
                    <span className="text-sm font-semibold font-mono text-slate-900">
                      {shipment.unit_price !== null && shipment.unit_price !== undefined
                        ? `${shipment.unit_price.toLocaleString()}${shipment.currency ? ' ' + shipment.currency : ''}`
                        : '—'}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <span className="text-[11px] font-medium text-slate-500 uppercase block">Total Value</span>
                    <span className="text-sm font-semibold font-mono text-slate-900">
                      {totalValue !== null
                        ? `${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${shipment.currency ? ' ' + shipment.currency : ''}`
                        : '—'}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <span className="text-[11px] font-medium text-slate-500 uppercase block">Gross Weight</span>
                    <span className="text-sm font-semibold font-mono text-slate-900">
                      {shipment.gross_weight_kg !== null && shipment.gross_weight_kg !== undefined
                        ? `${Number(shipment.gross_weight_kg).toLocaleString(undefined, { maximumFractionDigits: 3 })} kg`
                        : '—'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Audit & Metadata */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs text-slate-600 border-t border-slate-100 pt-4">
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-slate-400" />
                  <span>Created by User ID: <code className="font-mono text-slate-800">{shipment.created_by.slice(0, 8)}...</code></span>
                </div>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-slate-400" />
                  <span>Created: {formatDate(shipment.created_at)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Tag className="h-4 w-4 text-slate-400" />
                  <span>Record ID: <code className="font-mono text-slate-800">{shipment.id}</code></span>
                </div>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-slate-400" />
                  <span>Last Modified: {formatDate(shipment.updated_at)}</span>
                </div>
              </div>
            </div>
          ) : (
            /* Documents Workspace Tab */
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <h4 className="text-sm font-bold text-slate-900">Associated Customs Documents</h4>
                  <p className="text-xs text-slate-500">Commercial Invoices, Packing Lists, and Bills of Lading</p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => refetchDocs()}
                    title="Refresh Documents"
                    className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 transition-colors"
                  >
                    <RefreshCw className={`h-4 w-4 ${isDocsFetching ? 'animate-spin' : ''}`} />
                  </button>
                  <button
                    onClick={() => setIsUploadOpen(true)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs shadow-sm transition-colors"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    <span>Upload Document</span>
                  </button>
                </div>
              </div>

              {isDocsLoading ? (
                <div className="py-16 flex flex-col items-center justify-center text-slate-500">
                  <Loader2 className="h-7 w-7 animate-spin text-brand-600 mb-2" />
                  <span className="text-xs font-medium">Loading documents...</span>
                </div>
              ) : isDocsError ? (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{(docsError as Error)?.message || 'Failed to retrieve documents.'}</span>
                </div>
              ) : documents.length === 0 ? (
                <div className="py-12 border-2 border-dashed border-slate-200 rounded-xl text-center p-6 space-y-3">
                  <div className="p-3 rounded-full bg-slate-100 text-slate-400 inline-flex">
                    <FileText className="h-6 w-6" />
                  </div>
                  <div>
                    <h5 className="text-sm font-semibold text-slate-900">No documents uploaded yet</h5>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto mt-0.5">
                      Upload the Commercial Invoice, Packing List, or Bill of Lading to begin pre-clearance verification.
                    </p>
                  </div>
                  <button
                    onClick={() => setIsUploadOpen(true)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs shadow-sm transition-colors"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    <span>Upload Initial Document</span>
                  </button>
                </div>
              ) : (
                <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
                  {documents.map((doc) => {
                    const typeConfig = DOC_TYPE_CONFIG[doc.document_type] || {
                      label: doc.document_type,
                      badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
                    }
                    const procStatus = PROCESSING_STATUS_CONFIG[doc.processing_status] || {
                      label: doc.processing_status,
                      badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
                      icon: <Clock className="h-3 w-3 text-slate-500" />,
                    }

                    return (
                      <div
                        key={doc.id}
                        className="p-4 hover:bg-slate-50/80 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                      >
                        <div className="flex items-start gap-3">
                          <div className="p-2 rounded-lg bg-slate-100 text-slate-700 mt-0.5 shrink-0">
                            <FileText className="h-5 w-5" />
                          </div>
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold border ${typeConfig.badgeClass}`}
                              >
                                {typeConfig.label}
                              </span>
                              <span className="font-mono text-xs font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                                v{doc.version}
                              </span>
                              {doc.is_latest && (
                                <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                                  Latest
                                </span>
                              )}
                              <span
                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${procStatus.badgeClass}`}
                              >
                                {procStatus.icon}
                                {procStatus.label}
                              </span>
                            </div>

                            <div className="text-sm font-semibold text-slate-900 mt-1 line-clamp-1">
                              {doc.original_filename}
                            </div>

                            <div className="text-xs text-slate-500 flex flex-wrap items-center gap-2 mt-1">
                              <span>{(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                              <span>•</span>
                              <span>{formatDate(doc.created_at)}</span>
                              <span>•</span>
                              <span className="font-mono text-[11px] text-slate-400">
                                SHA: {doc.sha256_checksum.slice(0, 10)}...
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1.5 self-end sm:self-center shrink-0">
                          <button
                            onClick={() => handleDownload(doc)}
                            title="Download document payload"
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-medium text-slate-700 transition-colors shadow-sm"
                          >
                            <Download className="h-3.5 w-3.5 text-slate-500" />
                            <span>Download</span>
                          </button>

                          <button
                            onClick={() => setExtractionTargetDoc(doc)}
                            title="View extracted text and OCR intelligence"
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-brand-200 bg-brand-50 hover:bg-brand-100 text-xs font-semibold text-brand-700 transition-colors shadow-sm"
                          >
                            <Sparkles className="h-3.5 w-3.5 text-brand-600" />
                            <span>Extracted Text</span>
                          </button>

                          <button
                            onClick={() => setVersionTarget(doc)}
                            title="View version history"
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-medium text-slate-700 transition-colors shadow-sm"
                          >
                            <History className="h-3.5 w-3.5 text-slate-500" />
                            <span>History</span>
                          </button>

                          <button
                            onClick={() => setJobsTarget(doc)}
                            title="View background processing jobs"
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-medium text-slate-700 transition-colors shadow-sm"
                          >
                            <Cpu className="h-3.5 w-3.5 text-slate-500" />
                            <span>Jobs</span>
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50/70">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
          >
            Close
          </button>
          {onEdit && (
            <button
              onClick={() => {
                onClose()
                onEdit(shipment)
              }}
              className="px-4 py-2 text-sm font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors"
            >
              Edit Shipment
            </button>
          )}
        </div>
      </div>

      {/* Sub-Modals */}
      <UploadDocumentModal
        shipmentId={shipment.id}
        shipmentNumber={shipment.shipment_number}
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />

      {versionTarget && (
        <DocumentVersionModal
          shipmentId={shipment.id}
          documentId={versionTarget.id}
          isOpen={!!versionTarget}
          onClose={() => setVersionTarget(null)}
        />
      )}

      {jobsTarget && (
        <ProcessingJobsModal
          documentId={jobsTarget.id}
          documentName={jobsTarget.original_filename}
          isOpen={!!jobsTarget}
          onClose={() => setJobsTarget(null)}
        />
      )}

      {extractionTargetDoc && (
        <ExtractedTextModal
          isOpen={!!extractionTargetDoc}
          onClose={() => setExtractionTargetDoc(null)}
          shipmentId={shipment.id}
          document={extractionTargetDoc}
        />
      )}
    </div>
  )
}
