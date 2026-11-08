import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, Cpu, Clock, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { listDocumentJobs } from '../api/documents'
import { JobStatus } from '../types/document'

interface ProcessingJobsModalProps {
  documentId: string
  documentName: string
  isOpen: boolean
  onClose: () => void
}

const JOB_STATUS_CONFIG: Record<JobStatus, { label: string; badgeClass: string; icon: React.ReactNode }> = {
  PENDING: {
    label: 'Pending',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: <Clock className="h-3.5 w-3.5 text-amber-600" />,
  },
  PROCESSING: {
    label: 'Processing',
    badgeClass: 'bg-sky-50 text-sky-700 border-sky-200',
    icon: <Loader2 className="h-3.5 w-3.5 text-sky-600 animate-spin" />,
  },
  COMPLETED: {
    label: 'Completed',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />,
  },
  FAILED: {
    label: 'Failed',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    icon: <AlertCircle className="h-3.5 w-3.5 text-rose-600" />,
  },
}

export const ProcessingJobsModal: React.FC<ProcessingJobsModalProps> = ({
  documentId,
  documentName,
  isOpen,
  onClose,
}) => {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['documentJobs', documentId],
    queryFn: () => listDocumentJobs(documentId),
    enabled: isOpen && !!documentId,
    refetchInterval: (query) => {
      // Auto-poll if any job is still pending or processing
      const hasActive = query.state.data?.items.some(
        (j) => j.status === 'PENDING' || j.status === 'PROCESSING'
      )
      return hasActive ? 2000 : false
    },
  })

  if (!isOpen) return null

  const jobs = data?.items || []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-sky-50 text-sky-600">
              <Cpu className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Background Processing Jobs</h3>
              <p className="text-xs text-slate-500 font-mono truncate max-w-md">{documentName}</p>
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
              <span className="text-xs font-medium">Checking job queue status...</span>
            </div>
          ) : isError ? (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{(error as Error)?.message || 'Failed to retrieve jobs.'}</span>
            </div>
          ) : jobs.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500">No processing jobs recorded.</div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => {
                const statusInfo = JOB_STATUS_CONFIG[job.status] || {
                  label: job.status,
                  badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
                  icon: <Clock className="h-3.5 w-3.5 text-slate-500" />,
                }

                return (
                  <div
                    key={job.id}
                    className="p-4 rounded-xl border border-slate-200 bg-white space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 px-2.5 py-0.5 rounded">
                          {job.job_type}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusInfo.badgeClass}`}
                        >
                          {statusInfo.icon}
                          {statusInfo.label}
                        </span>
                      </div>
                      <span className="text-xs text-slate-500 font-mono">
                        Attempt: {job.attempt_count} / {job.max_attempts}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] text-slate-500 border-t border-slate-100 pt-2 font-mono">
                      <div>
                        <span className="text-slate-400 block font-sans">Created:</span>
                        {new Date(job.created_at).toLocaleTimeString()}
                      </div>
                      <div>
                        <span className="text-slate-400 block font-sans">Started:</span>
                        {job.started_at ? new Date(job.started_at).toLocaleTimeString() : '—'}
                      </div>
                      <div>
                        <span className="text-slate-400 block font-sans">Completed:</span>
                        {job.completed_at ? new Date(job.completed_at).toLocaleTimeString() : '—'}
                      </div>
                    </div>

                    {job.error_message && (
                      <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800">
                        <span className="font-semibold">Worker Error:</span> {job.error_message}
                      </div>
                    )}
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
