import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  X,
  FileText,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Cpu,
  History,
  Info,
} from 'lucide-react'
import {
  getDocumentExtraction,
  getDocumentExtractionPages,
  getDocumentExtractionHistory,
  triggerDocumentProcessing,
} from '../api/documents'
import {
  DocumentItem,
  ExtractionQualityStatus,
  ExtractionMethod,
  PageExtractionMethod,
} from '../types/document'

interface ExtractedTextModalProps {
  isOpen: boolean
  onClose: () => void
  shipmentId: string
  document: DocumentItem | null
}

const QUALITY_CONFIG: Record<
  ExtractionQualityStatus,
  { label: string; badgeClass: string; icon: React.ReactNode }
> = {
  GOOD: {
    label: 'High Quality',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />,
  },
  LOW_CONFIDENCE: {
    label: 'Low Confidence OCR',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: <AlertCircle className="h-3.5 w-3.5 text-amber-600" />,
  },
  EMPTY: {
    label: 'Empty Document',
    badgeClass: 'bg-slate-100 text-slate-600 border-slate-200',
    icon: <Info className="h-3.5 w-3.5 text-slate-400" />,
  },
  PARTIAL: {
    label: 'Partial Extraction',
    badgeClass: 'bg-orange-50 text-orange-700 border-orange-200',
    icon: <AlertCircle className="h-3.5 w-3.5 text-orange-600" />,
  },
  FAILED: {
    label: 'Extraction Failed',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    icon: <AlertCircle className="h-3.5 w-3.5 text-rose-600" />,
  },
}

const METHOD_LABELS: Record<ExtractionMethod | PageExtractionMethod, string> = {
  DIGITAL_TEXT: 'Digital Text (PDF)',
  OCR: 'Tesseract OCR',
  HYBRID: 'Hybrid (Digital + OCR)',
  EMPTY: 'Blank Page',
  FAILED: 'Failed',
}

export const ExtractedTextModal: React.FC<ExtractedTextModalProps> = ({
  isOpen,
  onClose,
  shipmentId,
  document: doc,
}) => {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'pages' | 'history'>('pages')
  const [selectedPageIndex, setSelectedPageIndex] = useState<number>(0)
  const [copied, setCopied] = useState<boolean>(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // 1. Fetch latest extraction summary
  const {
    data: extraction,
    isLoading: isExtractionLoading,
    isError: isExtractionError,
    refetch: refetchExtraction,
  } = useQuery({
    queryKey: ['document-extraction', shipmentId, doc?.id],
    queryFn: () => getDocumentExtraction(shipmentId, doc!.id),
    enabled: isOpen && !!doc,
    retry: 1,
  })

  // 2. Fetch all pages for latest extraction
  const {
    data: pagesData,
    isLoading: isPagesLoading,
  } = useQuery({
    queryKey: ['document-extraction-pages', shipmentId, doc?.id, extraction?.attempt_number],
    queryFn: () => getDocumentExtractionPages(shipmentId, doc!.id, 1, 100),
    enabled: isOpen && !!doc && !!extraction,
  })

  // 3. Fetch extraction history
  const {
    data: historyData,
    isLoading: isHistoryLoading,
  } = useQuery({
    queryKey: ['document-extraction-history', shipmentId, doc?.id],
    queryFn: () => getDocumentExtractionHistory(shipmentId, doc!.id),
    enabled: isOpen && !!doc && activeTab === 'history',
  })

  // 4. Trigger reprocess mutation
  const reprocessMutation = useMutation({
    mutationFn: () => triggerDocumentProcessing(shipmentId, doc!.id),
    onSuccess: () => {
      setActionError(null)
      queryClient.invalidateQueries({ queryKey: ['shipment-documents', shipmentId] })
      queryClient.invalidateQueries({ queryKey: ['document-extraction', shipmentId, doc?.id] })
      queryClient.invalidateQueries({ queryKey: ['document-extraction-pages', shipmentId, doc?.id] })
      queryClient.invalidateQueries({ queryKey: ['document-extraction-history', shipmentId, doc?.id] })
      refetchExtraction()
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message || 'Failed to trigger document processing.'
      setActionError(msg)
    },
  })

  if (!isOpen || !doc) return null

  const pages = pagesData?.items || []
  const currentPage = pages[selectedPageIndex] || pages[0]
  const totalPages = pages.length

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const qualityInfo = extraction ? QUALITY_CONFIG[extraction.quality_status] : null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-brand-50 text-brand-600 border border-brand-100">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900">Document Text Intelligence</h3>
                <span className="font-mono text-xs font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                  v{doc.version}
                </span>
                {qualityInfo && (
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${qualityInfo.badgeClass}`}
                  >
                    {qualityInfo.icon}
                    {qualityInfo.label}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5 truncate max-w-md">
                {doc.original_filename}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Action Error Banner */}
        {actionError && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
              <span>{actionError}</span>
            </div>
            <button
              onClick={() => setActionError(null)}
              className="text-rose-600 hover:text-rose-800 font-bold ml-2"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Tab Navigation & KPI Header */}
        <div className="px-6 pt-4 border-b border-slate-100">
          {extraction && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-[11px] font-medium text-slate-500 uppercase block">Method</span>
                <span className="text-xs font-bold text-slate-800 mt-0.5 block truncate">
                  {METHOD_LABELS[extraction.extraction_method] || extraction.extraction_method}
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-[11px] font-medium text-slate-500 uppercase block">Pages</span>
                <span className="text-xs font-bold text-slate-800 mt-0.5 block">
                  {extraction.processed_page_count} / {extraction.page_count} processed
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-[11px] font-medium text-slate-500 uppercase block">Characters</span>
                <span className="text-xs font-bold font-mono text-slate-800 mt-0.5 block">
                  {extraction.character_count.toLocaleString()}
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-[11px] font-medium text-slate-500 uppercase block">OCR Confidence</span>
                <span className="text-xs font-bold text-slate-800 mt-0.5 block">
                  {extraction.avg_confidence !== null && extraction.avg_confidence !== undefined
                    ? `${Number(extraction.avg_confidence).toFixed(1)}%`
                    : 'N/A (Digital Text)'}
                </span>
              </div>
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('pages')}
              className={`pb-2.5 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'pages'
                  ? 'border-brand-600 text-brand-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <FileText className="h-3.5 w-3.5" />
              <span>Extracted Content (Page Viewer)</span>
              {totalPages > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-100 text-slate-600">
                  {totalPages}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`pb-2.5 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'history'
                  ? 'border-brand-600 text-brand-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <History className="h-3.5 w-3.5" />
              <span>Extraction History</span>
            </button>
          </div>
        </div>

        {/* Body Content */}
        <div className="p-6 overflow-y-auto flex-1">
          {isExtractionLoading ? (
            <div className="py-20 flex flex-col items-center justify-center text-slate-500 space-y-3">
              <Cpu className="h-8 w-8 animate-spin text-brand-600" />
              <span className="text-xs font-medium">Loading extracted text intelligence...</span>
            </div>
          ) : isExtractionError ? (
            <div className="py-16 text-center space-y-4 max-w-md mx-auto">
              <div className="p-3 rounded-full bg-amber-50 text-amber-600 inline-flex border border-amber-100">
                <AlertCircle className="h-7 w-7" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900">No Extracted Text Found</h4>
                <p className="text-xs text-slate-500 mt-1">
                  This document has not been processed by the OCR pipeline yet or is currently queued in the background.
                </p>
              </div>
              <button
                onClick={() => reprocessMutation.mutate()}
                disabled={reprocessMutation.isPending}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs shadow-sm transition-colors"
              >
                <RotateCcw className={`h-4 w-4 ${reprocessMutation.isPending ? 'animate-spin' : ''}`} />
                <span>{reprocessMutation.isPending ? 'Queuing OCR...' : 'Run OCR Ingestion Now'}</span>
              </button>
            </div>
          ) : activeTab === 'pages' ? (
            /* Pages Tab */
            isPagesLoading ? (
              <div className="py-20 flex flex-col items-center justify-center text-slate-500 space-y-2">
                <Cpu className="h-6 w-6 animate-spin text-brand-600" />
                <span className="text-xs font-medium">Loading document pages...</span>
              </div>
            ) : (
            <div className="space-y-4">
              {totalPages === 0 ? (
                <div className="py-12 border-2 border-dashed border-slate-200 rounded-xl text-center p-6 space-y-2">
                  <span className="text-xs font-medium text-slate-500">
                    No pages available for this document extraction attempt.
                  </span>
                </div>
              ) : (
                <>
                  {/* Page Navigation Toolbar */}
                  <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setSelectedPageIndex((prev) => Math.max(0, prev - 1))}
                        disabled={selectedPageIndex === 0}
                        className="p-1 rounded-lg border border-slate-200 bg-white text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-100"
                        title="Previous page"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </button>

                      <span className="text-xs font-semibold text-slate-700 px-2">
                        Page {selectedPageIndex + 1} of {totalPages}
                      </span>

                      <button
                        onClick={() => setSelectedPageIndex((prev) => Math.min(totalPages - 1, prev + 1))}
                        disabled={selectedPageIndex >= totalPages - 1}
                        className="p-1 rounded-lg border border-slate-200 bg-white text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-100"
                        title="Next page"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </button>

                      <div className="h-4 w-px bg-slate-200 mx-1 hidden sm:block" />

                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-white border border-slate-200 text-slate-700">
                        {METHOD_LABELS[currentPage.extraction_method] || currentPage.extraction_method}
                      </span>

                      {currentPage.ocr_confidence !== null && currentPage.ocr_confidence !== undefined && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-white border border-slate-200 text-emerald-700">
                          {Number(currentPage.ocr_confidence).toFixed(1)}% conf
                        </span>
                      )}

                      <span className="text-[11px] text-slate-400">
                        {currentPage.character_count.toLocaleString()} chars
                      </span>
                    </div>

                    <button
                      onClick={() => handleCopyText(currentPage.raw_text)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-medium text-slate-700 transition-colors shadow-sm"
                    >
                      {copied ? (
                        <>
                          <Check className="h-3.5 w-3.5 text-emerald-600" />
                          <span className="text-emerald-700 font-semibold">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5 text-slate-500" />
                          <span>Copy Page Text</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Monospace Extracted Text Container */}
                  <div className="relative">
                    {currentPage.raw_text ? (
                      <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 font-mono text-xs leading-relaxed text-slate-900 whitespace-pre-wrap select-text max-h-[460px] overflow-y-auto">
                        {currentPage.raw_text}
                      </div>
                    ) : (
                      <div className="p-12 text-center border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/30">
                        <span className="text-xs font-medium text-slate-400 italic">
                          This page contains no readable text or is blank.
                        </span>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
            )
          ) : (
            /* History Tab */
            <div className="space-y-3">
              {isHistoryLoading ? (
                <div className="py-12 text-center text-xs text-slate-500">Loading history...</div>
              ) : (historyData?.items || []).length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-500">No prior extraction history.</div>
              ) : (
                <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
                  {historyData?.items.map((item) => {
                    const qInfo = QUALITY_CONFIG[item.quality_status]
                    return (
                      <div
                        key={item.id}
                        className="p-4 hover:bg-slate-50/80 transition-colors flex items-center justify-between"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-xs text-slate-900">
                              Attempt #{item.attempt_number}
                            </span>
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${qInfo.badgeClass}`}
                            >
                              {qInfo.icon}
                              {qInfo.label}
                            </span>
                            <span className="text-[11px] font-semibold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                              {METHOD_LABELS[item.extraction_method] || item.extraction_method}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500 flex items-center gap-2">
                            <span>{item.character_count.toLocaleString()} chars</span>
                            <span>•</span>
                            <span>{item.page_count} pages</span>
                            {item.avg_confidence !== null && item.avg_confidence !== undefined && (
                              <>
                                <span>•</span>
                                <span className="font-mono text-emerald-700">
                                  {Number(item.avg_confidence).toFixed(1)}% conf
                                </span>
                              </>
                            )}
                          </div>
                        </div>

                        <span className="text-[11px] text-slate-400 font-mono">
                          {new Date(item.created_at).toLocaleString()}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <div className="text-xs text-slate-500">
            {extraction && (
              <span>
                Attempt #{extraction.attempt_number} • Completed at{' '}
                {extraction.completed_at ? new Date(extraction.completed_at).toLocaleTimeString() : '—'}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => reprocessMutation.mutate()}
              disabled={reprocessMutation.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors shadow-sm disabled:opacity-50"
              title="Request OCR reprocessing or retry"
            >
              <RotateCcw className={`h-3.5 w-3.5 ${reprocessMutation.isPending ? 'animate-spin' : ''}`} />
              <span>{reprocessMutation.isPending ? 'Queuing...' : 'Re-process OCR'}</span>
            </button>

            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs shadow-sm transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
