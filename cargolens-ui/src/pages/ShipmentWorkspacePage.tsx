import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Box,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowLeft,
  RefreshCw,
  FileCheck2,
  ShieldCheck,
  Upload,
  Eye,
  History,
  AlertCircle,
  ExternalLink,
  Loader2,
  Check,
  Edit3,
  XCircle,
  Info,
  FileDown,
  Download,
} from 'lucide-react'
import { getShipment } from '../api/shipments'
import { listDocuments } from '../api/documents'
import {
  getShipmentValidations,
  runShipmentValidations,
} from '../api/validations'
import {
  fetchShipmentReviewHistory,
  fetchShipmentReviews,
  submitFieldReview,
} from '../api/reviews'
import {
  fetchVerificationReadiness,
  verifyShipment,
} from '../api/workflow'
import {
  fetchExportReadiness,
  exportShipmentCsv,
  fetchShipmentExports,
  downloadExportSnapshot,
} from '../api/exports'
import { getLatestStructuredExtraction } from '../api/structuredExtractions'
import { ShipmentStatus } from '../types/shipment'
import { DocumentItem, DocumentType } from '../types/document'
import { UploadDocumentModal } from '../components/UploadDocumentModal'
import { DocumentVersionModal } from '../components/DocumentVersionModal'
import { ExtractedTextModal } from '../components/ExtractedTextModal'
import { ProcessingJobsModal } from '../components/ProcessingJobsModal'

const STATUS_BADGE: Record<ShipmentStatus, { label: string; badgeClass: string }> = {
  CREATED: { label: 'Created', badgeClass: 'bg-slate-100 text-slate-700 border-slate-300' },
  DOCUMENTS_PENDING: { label: 'Doc Pending', badgeClass: 'bg-amber-50 text-amber-700 border-amber-300' },
  PROCESSING: { label: 'Processing', badgeClass: 'bg-sky-50 text-sky-700 border-sky-300' },
  REVIEW_REQUIRED: { label: 'Review Req', badgeClass: 'bg-rose-50 text-rose-700 border-rose-300' },
  VERIFIED: { label: 'Verified', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
  EXPORTED: { label: 'Exported', badgeClass: 'bg-purple-50 text-purple-700 border-purple-300' },
  FAILED: { label: 'Failed', badgeClass: 'bg-red-100 text-red-800 border-red-300' },
}

const REQUIRED_DOC_TYPES: DocumentType[] = [
  'COMMERCIAL_INVOICE',
  'PACKING_LIST',
  'BILL_OF_LADING',
]

export const ShipmentWorkspacePage: React.FC = () => {
  const { id, tab } = useParams<{ id: string; tab?: string }>()

  // Active Tab: 'overview' | 'documents' | 'extractions' | 'validations' | 'history' | 'export'
  const [activeTab, setActiveTab] = useState<'overview' | 'documents' | 'extractions' | 'validations' | 'history' | 'export'>('overview')

  // Synchronize activeTab with URL tab param for deep-linking (Screen 5, 6, 7, 9, 10, 13)
  useEffect(() => {
    if (!tab || tab === 'overview') {
      setActiveTab('overview')
    } else if (tab === 'documents') {
      setActiveTab('documents')
    } else if (tab === 'intelligence' || tab === 'extractions') {
      setActiveTab('extractions')
    } else if (tab === 'validations') {
      setActiveTab('validations')
    } else if (tab === 'history' || tab === 'audit') {
      setActiveTab('history')
    } else if (tab === 'export' || tab === 'exports') {
      setActiveTab('export')
    }
  }, [tab])

  const handleTabChange = (
    newTab: 'overview' | 'documents' | 'extractions' | 'validations' | 'history' | 'export'
  ) => {
    setActiveTab(newTab)
  }

  // Modals state
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [versionDoc, setVersionDoc] = useState<DocumentItem | null>(null)
  const [textDoc, setTextDoc] = useState<DocumentItem | null>(null)
  const [jobsDoc, setJobsDoc] = useState<DocumentItem | null>(null)

  // Correction inline form state
  const [correctingField, setCorrectingField] = useState<{
    docId: string
    fieldName: string
    originalValue: any
    extractionId: string
  } | null>(null)
  const [correctionValue, setCorrectionValue] = useState('')
  const [correctionReason, setCorrectionReason] = useState('')
  const [correctionError, setCorrectionError] = useState<string | null>(null)

  // Verify feedback state
  const [verifyMessage, setVerifyMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Selected document for Extracted Data tab
  const [selectedDocId, setSelectedDocId] = useState<string>('')

  // 1. Fetch Shipment
  const {
    data: shipment,
    isLoading: isShipmentLoading,
    isError: isShipmentError,
    error: shipmentError,
    refetch: refetchShipment,
  } = useQuery({
    queryKey: ['shipment', id],
    queryFn: () => getShipment(id!),
    enabled: !!id,
  })

  // 2. Fetch Documents
  const {
    data: documentsData,
    refetch: refetchDocs,
  } = useQuery({
    queryKey: ['shipmentDocuments', id],
    queryFn: () => listDocuments(id!),
    enabled: !!id,
  })

  const documents = documentsData?.items || []

  // Ensure selectedDocId defaults to first document
  React.useEffect(() => {
    if (documents.length > 0 && !selectedDocId) {
      setSelectedDocId(documents[0].id)
    }
  }, [documents, selectedDocId])

  // 3. Fetch Verification Readiness
  const {
    data: readiness,
    refetch: refetchReadiness,
  } = useQuery({
    queryKey: ['verificationReadiness', id],
    queryFn: () => fetchVerificationReadiness(id!),
    enabled: !!id,
    refetchInterval: 10000,
  })

  // 4. Fetch Validations
  const {
    data: validations,
    refetch: refetchValidations,
  } = useQuery({
    queryKey: ['shipmentValidations', id],
    queryFn: () => getShipmentValidations(id!),
    enabled: !!id,
  })

  // 5. Fetch Review History
  const {
    data: reviewHistory,
    isLoading: isHistoryLoading,
    refetch: refetchHistory,
  } = useQuery({
    queryKey: ['shipmentReviewHistory', id],
    queryFn: () => fetchShipmentReviewHistory(id!),
    enabled: !!id,
  })

  // 6. Fetch Extraction for selected document in extractions tab
  const {
    data: selectedExtraction,
    isLoading: isExtractionLoading,
  } = useQuery({
    queryKey: ['docExtraction', id, selectedDocId],
    queryFn: () => getLatestStructuredExtraction(id!, selectedDocId),
    enabled: !!id && !!selectedDocId,
    retry: false,
  })

  // 7. Fetch reviews for selected document
  const {
    data: docReviewsData,
    refetch: refetchDocReviews,
  } = useQuery({
    queryKey: ['docReviews', id, selectedDocId],
    queryFn: () => fetchShipmentReviews(id!, selectedDocId),
    enabled: !!id && !!selectedDocId,
  })

  const docReviews = docReviewsData?.items || []

  // 8. Fetch Export Readiness
  const {
    data: exportReadiness,
    refetch: refetchExportReadiness,
  } = useQuery({
    queryKey: ['exportReadiness', id],
    queryFn: () => fetchExportReadiness(id!),
    enabled: !!id,
    refetchInterval: 10000,
  })

  // 9. Fetch Shipment Exports History
  const {
    data: exportHistory,
    refetch: refetchExportHistory,
  } = useQuery({
    queryKey: ['shipmentExports', id],
    queryFn: () => fetchShipmentExports(id!),
    enabled: !!id,
  })

  const [selectedTemplate, setSelectedTemplate] = useState<string>('STANDARD_CUSTOMS_CLEARANCE')
  const [exportMessage, setExportMessage] = useState<{ type: 'success' | 'error'; text: string; checksum?: string } | null>(null)

  // Mutation: Execute Customs Export
  const exportMutation = useMutation({
    mutationFn: () => exportShipmentCsv(id!, selectedTemplate),
    onSuccess: (data) => {
      setExportMessage({
        type: 'success',
        text: `Customs declaration CSV successfully generated (${data.filename})`,
        checksum: data.checksum,
      })
      refetchShipment()
      refetchReadiness()
      refetchExportReadiness()
      refetchExportHistory()
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : detail?.message || err.message || 'Export failed.'
      setExportMessage({
        type: 'error',
        text: msg,
      })
    },
  })

  // Mutation: Download Snapshot
  const downloadSnapshotMutation = useMutation({
    mutationFn: ({ exportId, filename }: { exportId: string; filename: string }) =>
      downloadExportSnapshot(id!, exportId, filename),
  })

  // Mutation: Run Validation
  const runValidationMutation = useMutation({
    mutationFn: () => runShipmentValidations(id!),
    onSuccess: () => {
      refetchValidations()
      refetchReadiness()
      refetchShipment()
    },
  })

  // Mutation: Verify Shipment Workflow
  const verifyMutation = useMutation({
    mutationFn: () => verifyShipment(id!),
    onSuccess: (data) => {
      setVerifyMessage({
        type: 'success',
        text: `Consignment ${data.shipment.shipment_number} successfully verified! Status is now VERIFIED.`,
      })
      refetchShipment()
      refetchReadiness()
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message || 'Verification failed.'
      setVerifyMessage({ type: 'error', text: msg })
    },
  })

  // Mutation: Submit Confirmation / Correction
  const reviewMutation = useMutation({
    mutationFn: (payload: {
      docId: string
      data: {
        extraction_id: string
        field_name: string
        action: 'CONFIRMED' | 'CORRECTED'
        original_value?: any
        corrected_value?: any
        reason?: string
      }
    }) => submitFieldReview(id!, payload.docId, payload.data),
    onSuccess: () => {
      setCorrectingField(null)
      setCorrectionValue('')
      setCorrectionReason('')
      setCorrectionError(null)
      refetchDocReviews()
      refetchHistory()
      refetchReadiness()
      runValidationMutation.mutate()
    },
    onError: (err: any) => {
      setCorrectionError(err.response?.data?.detail || err.message || 'Failed to save review.')
    },
  })

  const handleConfirmField = (fieldName: string, rawVal: any, docId: string, extractionId: string) => {
    reviewMutation.mutate({
      docId,
      data: {
        extraction_id: extractionId,
        field_name: fieldName,
        action: 'CONFIRMED',
        original_value: rawVal,
        reason: 'Confirmed by human reviewer',
      },
    })
  }

  const handleOpenCorrection = (fieldName: string, rawVal: any, docId: string, extractionId: string) => {
    setCorrectingField({
      docId,
      fieldName,
      originalValue: rawVal,
      extractionId,
    })
    setCorrectionValue(rawVal !== null && rawVal !== undefined ? String(rawVal) : '')
    setCorrectionReason('')
    setCorrectionError(null)
  }

  const handleSaveCorrection = (e: React.FormEvent) => {
    e.preventDefault()
    if (!correctingField) return
    if (!correctionReason.trim()) {
      setCorrectionError('A rationale or reason is required when correcting extracted data.')
      return
    }

    const numericFields = ['gross_weight_kg', 'grand_total', 'subtotal', 'tax_amount', 'net_weight_kg', 'package_count', 'quantity']
    if (numericFields.includes(correctingField.fieldName)) {
      const num = Number(correctionValue)
      if (isNaN(num) || num < 0) {
        setCorrectionError(`Field '${correctingField.fieldName}' must be a valid non-negative number.`)
        return
      }
    }

    reviewMutation.mutate({
      docId: correctingField.docId,
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

  if (isShipmentLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-500">
        <Loader2 className="h-8 w-8 animate-spin text-brand-600 mb-3" />
        <p className="text-sm font-medium">Loading Consignment Workspace...</p>
      </div>
    )
  }

  if (isShipmentError || !shipment) {
    return (
      <div className="p-8 bg-red-50 border border-red-200 rounded-xl text-red-700 max-w-2xl mx-auto space-y-4">
        <div className="flex items-center gap-3 font-semibold text-base">
          <AlertCircle className="h-6 w-6 text-red-600" />
          <span>Shipment Not Found or Access Denied</span>
        </div>
        <p className="text-xs text-red-600">
          {(shipmentError as Error)?.message || 'Could not retrieve consignment details. You may lack permission to view this record.'}
        </p>
        <Link
          to="/shipments"
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800"
        >
          <ArrowLeft className="h-4 w-4" /> Return to Shipment Registry
        </Link>
      </div>
    )
  }

  const statusBadge = STATUS_BADGE[shipment.status] || {
    label: shipment.status,
    badgeClass: 'bg-slate-100 text-slate-700 border-slate-300',
  }

  return (
    <div className="space-y-6">
      {/* Top Navigation & Workspace Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              to="/shipments"
              className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
              title="Back to Registry"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-xl font-bold text-slate-900">
                  {shipment.shipment_number}
                </span>
                {(shipment.client_name?.includes('[DEMO]') ||
                  shipment.shipment_number?.startsWith('SHP-DEMO-') ||
                  shipment.shipment_number?.startsWith('SHP-2481')) && (
                  <span className="text-[10px] px-2 py-0.5 bg-amber-100 text-amber-800 border border-amber-300 rounded-md font-bold tracking-wide">
                    DEMO
                  </span>
                )}
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusBadge.badgeClass}`}
                >
                  {statusBadge.label}
                </span>
                {readiness?.is_ready && shipment.status !== 'VERIFIED' && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-300 animate-pulse">
                    <CheckCircle2 className="h-3 w-3" /> Ready for Verification
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Client: <strong className="text-slate-700">{shipment.client_name}</strong> • Origin:{' '}
                <strong className="text-slate-700">{shipment.origin_country || 'Not specified'}</strong>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                refetchShipment()
                refetchDocs()
                refetchReadiness()
                refetchValidations()
                refetchHistory()
              }}
              title="Refresh Workspace"
              className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
            </button>

            <button
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-xs transition"
            >
              <Upload className="h-3.5 w-3.5 text-brand-600" />
              Upload Document
            </button>

            {/* Workflow Verification / Export Action Buttons */}
            {shipment.status !== 'VERIFIED' && shipment.status !== 'EXPORTED' ? (
              <button
                onClick={() => verifyMutation.mutate()}
                disabled={!readiness?.is_ready || verifyMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed text-white text-xs font-bold shadow-xs transition"
              >
                {verifyMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <ShieldCheck className="h-4 w-4" />
                )}
                Verify Consignment
              </button>
            ) : shipment.status === 'VERIFIED' ? (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-300 text-xs font-bold">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  Consignment Verified
                </span>
                <button
                  onClick={() => handleTabChange('export')}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-xs transition"
                >
                  <FileDown className="h-4 w-4" />
                  Export Declaration
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-300 text-xs font-bold">
                  <CheckCircle2 className="h-4 w-4 text-indigo-600" />
                  Customs Exported
                </span>
                <button
                  onClick={() => handleTabChange('export')}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold shadow-xs transition"
                >
                  <FileDown className="h-4 w-4" />
                  View Exports
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Verification Alert Banner if message exists */}
        {verifyMessage && (
          <div
            className={`p-3 rounded-lg text-xs font-medium flex items-center justify-between border ${
              verifyMessage.type === 'success'
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                : 'bg-red-50 text-red-800 border-red-200'
            }`}
          >
            <span>{verifyMessage.text}</span>
            <button
              onClick={() => setVerifyMessage(null)}
              className="text-slate-400 hover:text-slate-700 ml-2"
            >
              ×
            </button>
          </div>
        )}

        {/* Export Alert Banner if message exists */}
        {exportMessage && (
          <div
            className={`p-3.5 rounded-lg text-xs font-medium flex items-center justify-between border ${
              exportMessage.type === 'success'
                ? 'bg-indigo-50 text-indigo-900 border-indigo-200'
                : 'bg-red-50 text-red-900 border-red-200'
            }`}
          >
            <div className="space-y-0.5">
              <div className="font-semibold">{exportMessage.text}</div>
              {exportMessage.checksum && (
                <div className="text-[11px] font-mono text-indigo-700">
                  SHA-256: {exportMessage.checksum}
                </div>
              )}
            </div>
            <button
              onClick={() => setExportMessage(null)}
              className="text-slate-400 hover:text-slate-700 ml-2 font-bold"
            >
              ×
            </button>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 border-b border-slate-200 pt-2 -mb-5 overflow-x-auto">
          {[
            { id: 'overview', label: 'Consignment Overview', icon: Box },
            { id: 'documents', label: `Documents (${documents.length})`, icon: FileText },
            { id: 'extractions', label: 'Extracted Intelligence', icon: FileCheck2 },
            {
              id: 'validations',
              label: `Validation Issues (${validations?.failed_count || 0})`,
              icon: AlertTriangle,
              alert: (validations?.failed_count || 0) > 0,
            },
            { id: 'history', label: `Review History (${reviewHistory?.total || 0})`, icon: History },
            {
              id: 'export',
              label: `Customs Export (${exportHistory?.total || 0})`,
              icon: FileDown,
            },
          ].map((tab) => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors ${
                  active
                    ? 'border-brand-600 text-brand-600'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
                {tab.alert && (
                  <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse"></span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Consignment Metadata */}
            <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Box className="h-4 w-4 text-brand-600" />
                Consignment Particulars
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-slate-400 font-medium">Consignee / Client</span>
                  <p className="font-semibold text-slate-900 mt-0.5">{shipment.client_name}</p>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Country of Origin</span>
                  <p className="font-semibold text-slate-900 mt-0.5">{shipment.origin_country || '—'}</p>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Goods Description</span>
                  <p className="font-semibold text-slate-900 mt-0.5">{shipment.product_description || '—'}</p>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Consignment Quantity</span>
                  <p className="font-mono font-semibold text-slate-900 mt-0.5">
                    {shipment.quantity !== null && shipment.quantity !== undefined
                      ? Number(shipment.quantity).toLocaleString()
                      : '—'}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Gross Weight (KG)</span>
                  <p className="font-mono font-semibold text-slate-900 mt-0.5">
                    {shipment.gross_weight_kg !== null && shipment.gross_weight_kg !== undefined
                      ? `${Number(shipment.gross_weight_kg).toLocaleString()} kg`
                      : '—'}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Unit Price & Currency</span>
                  <p className="font-mono font-semibold text-slate-900 mt-0.5">
                    {shipment.unit_price !== null && shipment.unit_price !== undefined
                      ? `${Number(shipment.unit_price).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                        })} ${shipment.currency || ''}`
                      : '—'}
                  </p>
                </div>
              </div>
            </div>

            {/* Document Completeness Checklist */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FileText className="h-4 w-4 text-indigo-600" />
                Required Customs Documents
              </h2>
              <div className="space-y-2.5 text-xs">
                {REQUIRED_DOC_TYPES.map((docType) => {
                  const uploaded = documents.some((d: DocumentItem) => d.document_type === docType)
                  const label =
                    docType === 'COMMERCIAL_INVOICE'
                      ? 'Commercial Invoice (CI)'
                      : docType === 'PACKING_LIST'
                      ? 'Packing List (PL)'
                      : 'Bill of Lading (BL)'
                  return (
                    <div
                      key={docType}
                      className={`p-3 rounded-lg border flex items-center justify-between ${
                        uploaded
                          ? 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
                          : 'bg-amber-50/50 border-amber-200 text-amber-900'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {uploaded ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        ) : (
                          <Clock className="h-4 w-4 text-amber-600" />
                        )}
                        <span className="font-semibold">{label}</span>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          uploaded ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {uploaded ? 'Uploaded' : 'Missing'}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Verification Readiness Checklist Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                Pre-Clearance Verification Readiness Checklist
              </h2>
              <button
                onClick={() => refetchReadiness()}
                className="text-xs text-brand-600 hover:underline flex items-center gap-1 font-semibold"
              >
                <RefreshCw className="h-3 w-3" /> Re-check
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              {/* Criterion 1: Required Documents */}
              <div
                className={`p-4 rounded-xl border ${
                  readiness?.all_documents_present
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-rose-50/60 border-rose-200 text-rose-900'
                }`}
              >
                <div className="flex items-center justify-between font-bold mb-1">
                  <span>1. Required Documents</span>
                  {readiness?.all_documents_present ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-rose-600" />
                  )}
                </div>
                <p className="text-[11px] opacity-80">
                  {readiness?.all_documents_present
                    ? 'CI, PL, and BL all uploaded'
                    : `Missing: ${(readiness?.documents_missing || []).join(', ')}`}
                </p>
              </div>

              {/* Criterion 2: OCR & AI Extractions */}
              <div
                className={`p-4 rounded-xl border ${
                  readiness?.all_extractions_completed
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-amber-50/60 border-amber-200 text-amber-900'
                }`}
              >
                <div className="flex items-center justify-between font-bold mb-1">
                  <span>2. Document Extractions</span>
                  {readiness?.all_extractions_completed ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Clock className="h-4 w-4 text-amber-600" />
                  )}
                </div>
                <p className="text-[11px] opacity-80">
                  {readiness?.all_extractions_completed
                    ? 'All documents processed'
                    : 'Extractions pending/incomplete'}
                </p>
              </div>

              {/* Criterion 3: Validation Issues */}
              <div
                className={`p-4 rounded-xl border ${
                  !readiness?.has_blocking_failures
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-rose-50/60 border-rose-200 text-rose-900'
                }`}
              >
                <div className="flex items-center justify-between font-bold mb-1">
                  <span>3. Blocking Discrepancies</span>
                  {!readiness?.has_blocking_failures ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-rose-600" />
                  )}
                </div>
                <p className="text-[11px] opacity-80">
                  {!readiness?.has_blocking_failures
                    ? '0 blocking discrepancies'
                    : `${readiness?.blocking_validation_failures_count} blocking issue(s) detected`}
                </p>
              </div>

              {/* Criterion 4: Mandatory Human Reviews */}
              <div
                className={`p-4 rounded-xl border ${
                  readiness?.all_mandatory_fields_reviewed
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-amber-50/60 border-amber-200 text-amber-900'
                }`}
              >
                <div className="flex items-center justify-between font-bold mb-1">
                  <span>4. Mandatory Field Review</span>
                  {readiness?.all_mandatory_fields_reviewed ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Clock className="h-4 w-4 text-amber-600" />
                  )}
                </div>
                <p className="text-[11px] opacity-80">
                  {readiness?.all_mandatory_fields_reviewed
                    ? `All mandatory fields confirmed (${readiness?.human_reviews_count || 0} reviews)`
                    : `${readiness?.unreviewed_mandatory_fields?.length || 0} mandatory field(s) unreviewed`}
                </p>
              </div>
            </div>

            {readiness && !readiness.is_ready && (
              <div className="p-3.5 bg-amber-50/80 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-1.5">
                <div className="font-semibold flex items-center gap-1.5 text-amber-800">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  <span>Outstanding Verification Requirements:</span>
                </div>
                <ul className="list-disc pl-5 space-y-0.5 text-[11px] text-amber-800/90">
                  {readiness.missing_requirements.map((req, i) => (
                    <li key={i}>{req}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: DOCUMENTS */}
      {activeTab === 'documents' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 sm:p-5 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FileText className="h-4 w-4 text-brand-600" />
                Uploaded Consignment Documents ({documents.length})
              </h2>
              <button
                onClick={() => setIsUploadOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold shadow-xs"
              >
                <Upload className="h-3.5 w-3.5" /> Upload File
              </button>
            </div>

            {documents.length === 0 ? (
              <div className="py-12 text-center text-slate-400 text-xs">
                No documents uploaded for this consignment yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Document Type</th>
                      <th className="py-3 px-4">Filename</th>
                      <th className="py-3 px-4">Version</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Upload Date</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {documents.map((doc: DocumentItem) => (
                      <tr key={doc.id} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3 px-4 font-semibold text-slate-900">
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                            {doc.document_type.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono truncate max-w-[180px] text-slate-800">
                          {doc.original_filename}
                        </td>
                        <td className="py-3 px-4 font-semibold text-brand-700">v{doc.version}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded font-semibold text-[10px] ${
                              doc.processing_status === 'COMPLETED'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : doc.processing_status === 'FAILED'
                                ? 'bg-red-50 text-red-700 border border-red-200'
                                : 'bg-sky-50 text-sky-700 border border-sky-200'
                            }`}
                          >
                            {doc.processing_status || 'PENDING'}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-400">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Link
                              to={`/review/${shipment.id}/${doc.id}`}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-brand-50 hover:bg-brand-100 text-brand-700 font-semibold text-xs"
                            >
                              <FileCheck2 className="h-3.5 w-3.5" /> Review
                            </Link>
                            <button
                              onClick={() => setTextDoc(doc)}
                              title="Extracted Text"
                              className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => setJobsDoc(doc)}
                              title="Processing Jobs"
                              className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                            >
                              <Clock className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => setVersionDoc(doc)}
                              title="Upload New Version"
                              className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                            >
                              <Upload className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: EXTRACTED DATA */}
      {activeTab === 'extractions' && (
        <div className="space-y-4">
          {/* Document Selector Pills */}
          <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {documents.map((doc: DocumentItem) => {
              const active = selectedDocId === doc.id
              return (
                <button
                  key={doc.id}
                  onClick={() => setSelectedDocId(doc.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    active
                      ? 'bg-brand-600 text-white border-brand-600 shadow-xs'
                      : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  {doc.document_type.replace(/_/g, ' ')} (v{doc.version})
                </button>
              )
            })}
          </div>

          {/* Document Extraction View */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Field Extractions & Human Review State
                </h3>
                <p className="text-xs text-slate-500">
                  Review AI-extracted fields, verify source provenance, and execute corrections.
                </p>
              </div>

              {selectedDocId && (
                <Link
                  to={`/review/${shipment.id}/${selectedDocId}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-50 hover:bg-brand-100 text-brand-700 font-semibold text-xs border border-brand-200"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Open Split-Screen Viewer
                </Link>
              )}
            </div>

            {isExtractionLoading ? (
              <div className="py-12 flex flex-col items-center justify-center text-slate-500">
                <Loader2 className="h-6 w-6 animate-spin text-brand-600 mb-2" />
                <span className="text-xs font-medium">Loading field extractions...</span>
              </div>
            ) : !selectedExtraction ? (
              <div className="py-10 text-center text-slate-400 text-xs">
                No structured extractions available for this document yet. Ensure OCR and AI extraction have completed.
              </div>
            ) : (
              <div className="space-y-4">
                {/* Field-by-field table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
                      <tr>
                        <th className="py-3 px-4">Field Name</th>
                        <th className="py-3 px-4">Value</th>
                        <th className="py-3 px-4">Confidence</th>
                        <th className="py-3 px-4">Source Page</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4 text-right">Review Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {Object.entries(selectedExtraction.extracted_data || {}).map(([fname, fmeta]) => {
                        const isObj = typeof fmeta === 'object' && fmeta !== null
                        const rawVal = isObj && 'value' in fmeta ? fmeta.value : fmeta
                        const conf = isObj && 'confidence' in fmeta ? fmeta.confidence : null
                        const pageNum = isObj && 'source_page_number' in fmeta ? fmeta.source_page_number : null

                        // Check if this field has a human review record
                        const humanReview = docReviews.find((r) => r.field_name === fname)
                        const isConfirmed = humanReview?.action === 'CONFIRMED'
                        const isCorrected = humanReview?.action === 'CORRECTED'

                        return (
                          <tr key={fname} className="hover:bg-slate-50 transition-colors">
                            <td className="py-3 px-4 font-semibold text-slate-900 font-mono">
                              {fname}
                            </td>
                            <td className="py-3 px-4">
                              {isCorrected ? (
                                <div className="space-y-0.5">
                                  <span className="line-through text-slate-400 mr-1.5">
                                    {String(humanReview.original_value)}
                                  </span>
                                  <span className="font-bold text-emerald-700">
                                    {String(humanReview.corrected_value)}
                                  </span>
                                  <span className="block text-[10px] text-slate-400 italic">
                                    "{humanReview.reason}"
                                  </span>
                                </div>
                              ) : (
                                <span className="font-medium text-slate-800">
                                  {rawVal !== null && rawVal !== undefined ? (
                                    String(rawVal)
                                  ) : (
                                    <span className="text-slate-500 italic text-[11px] bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                                      Not provided in source declaration
                                    </span>
                                  )}
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              {conf !== null && conf !== undefined ? (
                                <span
                                  className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${
                                    conf >= 0.85
                                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                                  }`}
                                >
                                  {Math.round(conf * 100)}%
                                </span>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td className="py-3 px-4">
                              {pageNum ? (
                                <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px]">
                                  Page {pageNum}
                                </span>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td className="py-3 px-4">
                              {isCorrected ? (
                                <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 text-[10px] font-bold">
                                  Corrected
                                </span>
                              ) : isConfirmed ? (
                                <div>
                                  {humanReview?.provenance === 'DEMO_SEED' ? (
                                    <span
                                      data-testid="demo-fixture-badge"
                                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 text-amber-900 border border-amber-300 text-[9px] font-bold shadow-2xs"
                                      title="Seeded demonstration fixture — not an authentic human verification"
                                    >
                                      <AlertTriangle className="h-2.5 w-2.5 text-amber-600 flex-shrink-0" />
                                      DEMO FIXTURE — NOT A REAL HUMAN APPROVAL
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">
                                      Confirmed
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-semibold">
                                  AI Extracted
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                {!isConfirmed && !isCorrected && (
                                  <button
                                    onClick={() =>
                                      handleConfirmField(
                                        fname,
                                        rawVal,
                                        selectedDocId,
                                        selectedExtraction.id
                                      )
                                    }
                                    title="Confirm this value"
                                    className="p-1 rounded bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-colors"
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </button>
                                )}
                                <button
                                  onClick={() =>
                                    handleOpenCorrection(
                                      fname,
                                      rawVal,
                                      selectedDocId,
                                      selectedExtraction.id
                                    )
                                  }
                                  title="Correct this value"
                                  className="p-1 rounded bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors"
                                >
                                  <Edit3 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Inline Field Correction Form */}
                {correctingField && (
                  <div className="mt-4 p-4 rounded-xl border border-amber-300 bg-amber-50/70 space-y-3">
                    <div className="flex items-center justify-between font-bold text-xs text-amber-900">
                      <span>Correcting Field: <strong className="font-mono">{correctingField.fieldName}</strong></span>
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

                    <form onSubmit={handleSaveCorrection} className="space-y-3 text-xs">
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">
                          Correct Value
                        </label>
                        <input
                          type="text"
                          value={correctionValue}
                          onChange={(e) => setCorrectionValue(e.target.value)}
                          placeholder="Enter corrected value"
                          className="w-full px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-1 focus:ring-brand-500"
                        />
                      </div>

                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">
                          Reason / Audit Rationale <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={correctionReason}
                          onChange={(e) => setCorrectionReason(e.target.value)}
                          placeholder="e.g. Scanned OCR misread digit 8 as 3"
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
                          disabled={reviewMutation.isPending}
                          className="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-semibold"
                        >
                          {reviewMutation.isPending ? 'Saving...' : 'Save Correction'}
                        </button>
                      </div>
                    </form>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: VALIDATION */}
      {activeTab === 'validations' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-200">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-brand-600" />
                  Deterministic Cross-Document Reconciliation Results
                </h3>
                <p className="text-xs text-slate-500">
                  Reconciles arithmetic, container numbers, weights, and dates across all uploaded documents.
                </p>
              </div>

              <button
                onClick={() => runValidationMutation.mutate()}
                disabled={runValidationMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${runValidationMutation.isPending ? 'animate-spin' : ''}`}
                />
                Re-run Validations
              </button>
            </div>

            {/* Validation Outcome Metrics */}
            {validations && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
                <div className="p-3 rounded-lg border border-slate-200 bg-slate-50">
                  <span className="text-slate-500 font-semibold">Total Rules</span>
                  <p className="text-xl font-extrabold text-slate-900 mt-0.5">{validations.total_rules}</p>
                </div>
                <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-900">
                  <span className="font-semibold">Passed</span>
                  <p className="text-xl font-extrabold mt-0.5">{validations.passed_count}</p>
                </div>
                <div className="p-3 rounded-lg border border-rose-200 bg-rose-50 text-rose-900">
                  <span className="font-semibold">Discrepancies</span>
                  <p className="text-xl font-extrabold mt-0.5">{validations.failed_count}</p>
                </div>
                <div className="p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900">
                  <span className="font-semibold">Missing Data</span>
                  <p className="text-xl font-extrabold mt-0.5">{validations.missing_data_count}</p>
                </div>
                <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-slate-700">
                  <span className="font-semibold">Not Applicable</span>
                  <p className="text-xl font-extrabold mt-0.5">{validations.not_applicable_count}</p>
                </div>
              </div>
            )}

            {/* Validation Rule Details List */}
            {validations?.results && validations.results.length > 0 ? (
              <div className="space-y-3 pt-2">
                {validations.results.map((rule) => {
                  const isFail = rule.outcome === 'FAIL'
                  const isPass = rule.outcome === 'PASS'

                  return (
                    <div
                      key={rule.id}
                      className={`p-4 rounded-xl border text-xs space-y-2 transition-all ${
                        isFail
                          ? 'border-rose-300 bg-rose-50/50'
                          : isPass
                          ? 'border-emerald-200 bg-emerald-50/30'
                          : 'border-slate-200 bg-slate-50/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {isPass ? (
                            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                          ) : isFail ? (
                            <AlertTriangle className="h-4 w-4 text-rose-600" />
                          ) : (
                            <Info className="h-4 w-4 text-slate-400" />
                          )}
                          <span className="font-bold text-slate-900">{rule.rule_name}</span>
                          <span className="font-mono text-[10px] text-slate-400">({rule.rule_id})</span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                              rule.severity === 'ERROR'
                                ? 'bg-red-100 text-red-800'
                                : rule.severity === 'WARNING'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {rule.severity}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                              isPass
                                ? 'bg-emerald-100 text-emerald-800'
                                : isFail
                                ? 'bg-rose-100 text-rose-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            {rule.outcome}
                          </span>
                        </div>
                      </div>

                      {rule.explanation && (
                        <p className="text-slate-700 font-medium">{rule.explanation}</p>
                      )}

                      {rule.compared_values && Object.keys(rule.compared_values).length > 0 && (
                        <div className="p-2.5 rounded-lg bg-white/80 border border-slate-200/80 font-mono text-[11px] space-y-1">
                          <div className="text-[10px] text-slate-400 font-sans font-semibold uppercase">
                            Compared Values:
                          </div>
                          <pre className="text-slate-800 overflow-x-auto whitespace-pre-wrap">
                            {JSON.stringify(rule.compared_values, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="py-8 text-center text-slate-400 text-xs">
                No validation run results found. Click "Re-run Validations" above to execute rule checks.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 5: REVIEW HISTORY */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 pb-3 border-b border-slate-200">
              <History className="h-4 w-4 text-brand-600" />
              Consignment Human Review & Verification Audit Trail
            </h3>

            {isHistoryLoading ? (
              <div className="py-12 flex flex-col items-center justify-center text-slate-500">
                <Loader2 className="h-6 w-6 animate-spin text-brand-600 mb-2" />
                <span className="text-xs font-medium">Loading audit history...</span>
              </div>
            ) : reviewHistory?.items && reviewHistory.items.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Timestamp</th>
                      <th className="py-3 px-4">Provenance</th>
                      <th className="py-3 px-4">Reviewer</th>
                      <th className="py-3 px-4">Field Name</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Original → Corrected</th>
                      <th className="py-3 px-4">Reason / Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {reviewHistory.items.map((rev) => {
                      const isDemoSeed = rev.provenance === 'DEMO_SEED'

                      return (
                        <tr
                          key={rev.id}
                          className={`hover:bg-slate-50 transition-colors ${
                            isDemoSeed ? 'bg-amber-50/20' : ''
                          }`}
                        >
                          <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                            {new Date(rev.created_at).toLocaleString()}
                          </td>
                          <td className="py-3 px-4 whitespace-nowrap">
                            {isDemoSeed ? (
                              <span
                                data-testid="demo-fixture-badge"
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-amber-50 border border-amber-300 text-amber-900 font-bold text-[10px] tracking-wide shadow-2xs"
                              >
                                <AlertTriangle className="h-3 w-3 text-amber-600 flex-shrink-0" />
                                DEMO FIXTURE — NOT A REAL HUMAN APPROVAL
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 border border-blue-200 text-blue-700 font-semibold text-[10px]">
                                Human Review
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            {isDemoSeed ? (
                              <div>
                                <span className="font-semibold text-amber-900 block">Demonstration Fixture</span>
                                <span className="text-[10px] text-amber-700 font-mono block">
                                  Attributed to {rev.reviewer_email || 'manager@cargolens.in'}
                                </span>
                                <span className="text-[9px] text-slate-400 italic block">
                                  Automated demo generation
                                </span>
                              </div>
                            ) : (
                              <div>
                                <span className="font-semibold text-slate-900 block">{rev.reviewer_name || 'Officer'}</span>
                                <span className="text-[10px] text-slate-400 block">{rev.reviewer_email || rev.reviewer_role || 'Executive'}</span>
                              </div>
                            )}
                          </td>
                          <td className="py-3 px-4 font-mono font-semibold text-slate-800">
                            {rev.field_name}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                rev.action === 'CONFIRMED'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                              }`}
                            >
                              {rev.action}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            {rev.action === 'CORRECTED' ? (
                              <div className="space-x-1">
                                <span className="line-through text-slate-400">{String(rev.original_value)}</span>
                                <span>→</span>
                                <span className="font-bold text-slate-900">{String(rev.corrected_value)}</span>
                              </div>
                            ) : (
                              <span className="text-slate-500">{String(rev.original_value)}</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-slate-600 max-w-xs truncate">
                            {rev.reason || '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-10 text-center text-slate-400 text-xs">
                No human review actions have been recorded on this consignment yet.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 6: CUSTOMS EXPORT */}
      {activeTab === 'export' && (
        <div className="space-y-6">
          {/* Export Readiness Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FileDown className="h-4 w-4 text-indigo-600" />
                Customs Declaration Export Readiness
              </h2>
              <span
                className={`px-2.5 py-1 rounded-full text-xs font-bold border ${
                  exportReadiness?.is_ready_to_export
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-amber-50 text-amber-800 border-amber-200'
                }`}
              >
                {exportReadiness?.is_ready_to_export ? 'READY FOR EXPORT' : 'EXPORT BLOCKED'}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              {/* Check 1: Verification status */}
              <div
                className={`p-4 rounded-xl border ${
                  exportReadiness?.is_verified
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-rose-50/60 border-rose-200 text-rose-900'
                }`}
              >
                <div className="flex items-center justify-between font-bold mb-1">
                  <span>1. Consignment Verification</span>
                  {exportReadiness?.is_verified ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-rose-600" />
                  )}
                </div>
                <p className="text-[11px] opacity-80">
                  {exportReadiness?.is_verified
                    ? `Status: ${shipment.status} (Verified for clearance)`
                    : 'Consignment must be in VERIFIED status before export'}
                </p>
              </div>

              {/* Check 2: Mandatory fields */}
              <div
                className={`p-4 rounded-xl border ${
                  exportReadiness?.all_mandatory_fields_reviewed
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-amber-50/60 border-amber-200 text-amber-900'
                }`}
              >
                <div className="flex items-center justify-between font-bold mb-1">
                  <span>2. Mandatory Field Reviews</span>
                  {exportReadiness?.all_mandatory_fields_reviewed ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Clock className="h-4 w-4 text-amber-600" />
                  )}
                </div>
                <p className="text-[11px] opacity-80">
                  {exportReadiness?.all_mandatory_fields_reviewed
                    ? 'All mandatory export fields confirmed or corrected'
                    : 'Mandatory fields require human confirmation'}
                </p>
              </div>

              {/* Check 3: Blocking validation issues */}
              <div
                className={`p-4 rounded-xl border ${
                  !exportReadiness?.has_blocking_failures
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-rose-50/60 border-rose-200 text-rose-900'
                }`}
              >
                <div className="flex items-center justify-between font-bold mb-1">
                  <span>3. Discrepancy Integrity</span>
                  {!exportReadiness?.has_blocking_failures ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-rose-600" />
                  )}
                </div>
                <p className="text-[11px] opacity-80">
                  {!exportReadiness?.has_blocking_failures
                    ? '0 blocking cross-document discrepancies'
                    : 'Discrepancies remain unresolved'}
                </p>
              </div>
            </div>

            {/* Blocked Explanation Banner */}
            {exportReadiness && !exportReadiness.is_ready_to_export && (
              <div className="p-3.5 bg-amber-50/80 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-1.5">
                <div className="font-semibold flex items-center gap-1.5 text-amber-800">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  <span>Export Prerequisites Remaining:</span>
                </div>
                <ul className="list-disc pl-5 space-y-0.5 text-[11px] text-amber-800/90">
                  {exportReadiness.missing_requirements.map((req, i) => (
                    <li key={i}>{req}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Export Action & Template Selector */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-5">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FileText className="h-4 w-4 text-brand-600" />
                Select Customs Declaration Template
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Choose the customs clearance CSV mapping format. Only human-reviewed values will be included.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label
                className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                  selectedTemplate === 'STANDARD_CUSTOMS_CLEARANCE'
                    ? 'border-brand-500 bg-brand-50/30 ring-1 ring-brand-500'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900">
                      Standard Customs Clearance
                    </span>
                    <input
                      type="radio"
                      name="template"
                      value="STANDARD_CUSTOMS_CLEARANCE"
                      checked={selectedTemplate === 'STANDARD_CUSTOMS_CLEARANCE'}
                      onChange={() => setSelectedTemplate('STANDARD_CUSTOMS_CLEARANCE')}
                      className="text-brand-600 focus:ring-brand-500"
                    />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Consolidated single-consignment customs declaration with validated commercial invoice, packing list, and bill of lading fields.
                  </p>
                </div>
                <div className="mt-3 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                  19 Customs Fields • Single Row
                </div>
              </label>

              <label
                className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                  selectedTemplate === 'LINE_ITEM_DECLARATION'
                    ? 'border-brand-500 bg-brand-50/30 ring-1 ring-brand-500'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900">
                      Line-Item Customs Declaration
                    </span>
                    <input
                      type="radio"
                      name="template"
                      value="LINE_ITEM_DECLARATION"
                      checked={selectedTemplate === 'LINE_ITEM_DECLARATION'}
                      onChange={() => setSelectedTemplate('LINE_ITEM_DECLARATION')}
                      className="text-brand-600 focus:ring-brand-500"
                    />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Itemized line-item declaration for tariff classification, individual line valuation, quantities, and commodity descriptions.
                  </p>
                </div>
                <div className="mt-3 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                  17 Customs Fields • Itemized Multi-Row
                </div>
              </label>
            </div>

            {/* Export Execution CTA */}
            <div className="pt-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-t border-slate-100">
              <div className="text-xs text-slate-500 flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />
                <span>
                  Protected with CSV formula injection mitigation and SHA-256 snapshot auditing.
                </span>
              </div>

              <button
                onClick={() => exportMutation.mutate()}
                disabled={!exportReadiness?.is_ready_to_export || exportMutation.isPending}
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed text-white text-xs font-bold shadow-xs transition"
              >
                {exportMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Generating CSV Export...</span>
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    <span>Generate & Download Verified CSV</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Export History Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden space-y-0">
            <div className="p-4 sm:p-5 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <History className="h-4 w-4 text-brand-600" />
                  Consignment Export History & Immutable Snapshots
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Historical declaration files with cryptographic SHA-256 checksums. Re-download past snapshots at any time.
                </p>
              </div>
              <button
                onClick={() => refetchExportHistory()}
                className="text-xs text-brand-600 hover:underline flex items-center gap-1 font-semibold"
              >
                <RefreshCw className="h-3 w-3" /> Refresh
              </button>
            </div>

            {exportHistory?.items && exportHistory.items.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                    <tr>
                      <th className="py-3 px-4">Export Timestamp</th>
                      <th className="py-3 px-4">Template</th>
                      <th className="py-3 px-4">Exporter</th>
                      <th className="py-3 px-4">Filename</th>
                      <th className="py-3 px-4">Rows</th>
                      <th className="py-3 px-4">SHA-256 Checksum</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {exportHistory.items.map((exp) => (
                      <tr key={exp.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                          {new Date(exp.exported_at).toLocaleString()}
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-800">
                            {exp.template_name === 'STANDARD_CUSTOMS_CLEARANCE'
                              ? 'Standard Single'
                              : 'Line-Item Declaration'}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-semibold text-slate-900">{exp.exporter_name || 'Exporter'}</span>
                          <span className="block text-[10px] text-slate-400">{exp.exporter_email}</span>
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-slate-600 truncate max-w-xs">
                          {exp.filename}
                        </td>
                        <td className="py-3 px-4 font-semibold text-slate-800">{exp.row_count}</td>
                        <td className="py-3 px-4 font-mono text-[10px] text-slate-500 truncate max-w-[140px]" title={exp.sha256_checksum}>
                          {exp.sha256_checksum.slice(0, 16)}...
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() =>
                              downloadSnapshotMutation.mutate({
                                exportId: exp.id,
                                filename: exp.filename,
                              })
                            }
                            disabled={downloadSnapshotMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-white border border-slate-200 text-brand-600 hover:bg-brand-50 text-[11px] font-semibold transition"
                          >
                            <Download className="h-3 w-3" />
                            Download
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-12 text-center text-slate-400 text-xs">
                No exports have been generated for this consignment yet. Once verified, click "Generate & Download Verified CSV" above.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Auxiliary Modals */}
      <UploadDocumentModal
        shipmentId={shipment.id}
        shipmentNumber={shipment.shipment_number}
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => {
          setIsUploadOpen(false)
          refetchDocs()
          refetchReadiness()
        }}
      />

      <DocumentVersionModal
        shipmentId={shipment.id}
        documentId={versionDoc?.id || ''}
        isOpen={!!versionDoc}
        onClose={() => setVersionDoc(null)}
      />

      <ExtractedTextModal
        shipmentId={shipment.id}
        document={textDoc}
        isOpen={!!textDoc}
        onClose={() => setTextDoc(null)}
      />

      <ProcessingJobsModal
        documentId={jobsDoc?.id || ''}
        documentName={jobsDoc?.original_filename || ''}
        isOpen={!!jobsDoc}
        onClose={() => setJobsDoc(null)}
      />
    </div>
  )
}
