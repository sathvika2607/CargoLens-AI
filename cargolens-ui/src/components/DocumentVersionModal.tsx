import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, History, Download, Loader2, AlertCircle, FileText, CheckCircle2 } from 'lucide-react'
import { listDocumentVersions, downloadDocument } from '../api/documents'
import { DocumentProcessingStatus } from '../types/document'

interface DocumentVersionModalProps {
  shipmentId: string
  documentId: string
  isOpen: boolean
  onClose: () => void
}

const STATUS_CONFIG: Record<DocumentProcessingStatus, { label: string; badgeClass: string }> = {
  PENDING: { label: 'Pending', badgeClass: 'bg-amber-50 text-amber-700 border-amber-200' },
  PROCESSING: { label: 'Processing', badgeClass: 'bg-sky-50 text-sky-700 border-sky-200' },
  COMPLETED: { label: 'Completed', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  FAILED: { label: 'Failed', badgeClass: 'bg-rose-50 text-rose-700 border-rose-200' },
}

export const DocumentVersionModal: React.FC<DocumentVersionModalProps> = ({
  shipmentId,
  documentId,
  isOpen,
  onClose,
}) => {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['documentVersions', shipmentId, documentId],
    queryFn: () => listDocumentVersions(shipmentId, documentId),
    enabled: isOpen && !!shipmentId && !!documentId,
  })

  if (!isOpen) return null

  const versions = data?.items || []

  const handleDownload = async (docId: string, filename: string) => {
    try {
      await downloadDocument(shipmentId, docId, filename)
    } catch {
      alert('Failed to download document file payload.')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-brand-50 text-brand-600">
              <History className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Document Version History</h3>
              <p className="text-xs text-slate-500">Immutable ledger of uploaded document revisions</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin text-brand-600 mb-2" />
              <span className="text-xs font-medium">Retrieving version history...</span>
            </div>
          ) : isError ? (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{(error as Error)?.message || 'Failed to load versions.'}</span>
            </div>
          ) : versions.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500">No versions found.</div>
          ) : (
            <div className="space-y-3">
              {versions.map((ver) => {
                const statusInfo = STATUS_CONFIG[ver.processing_status] || {
                  label: ver.processing_status,
                  badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
                }

                return (
                  <div
                    key={ver.id}
                    className="p-4 rounded-xl border border-slate-200 bg-white hover:bg-slate-50/60 transition-colors flex items-center justify-between gap-4"
                  >
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-lg bg-slate-100 text-slate-600 mt-0.5">
                        <FileText className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded">
                            v{ver.version}
                          </span>
                          {ver.is_latest && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                              <CheckCircle2 className="h-3 w-3" /> Latest
                            </span>
                          )}
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusInfo.badgeClass}`}
                          >
                            {statusInfo.label}
                          </span>
                        </div>
                        <div className="text-sm font-semibold text-slate-900 mt-1 line-clamp-1">
                          {ver.original_filename}
                        </div>
                        <div className="text-xs text-slate-500 flex items-center gap-3 mt-1">
                          <span>{(ver.file_size_bytes / 1024).toFixed(1)} KB</span>
                          <span>•</span>
                          <span>{new Date(ver.created_at).toLocaleString()}</span>
                          <span>•</span>
                          <span className="font-mono text-[11px] text-slate-400">
                            SHA: {ver.sha256_checksum.slice(0, 10)}...
                          </span>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => handleDownload(ver.id, ver.original_filename)}
                      title="Download this version"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-medium text-slate-700 transition-colors shadow-sm"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Download</span>
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-6 py-3 border-t border-slate-100 bg-slate-50/70">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
