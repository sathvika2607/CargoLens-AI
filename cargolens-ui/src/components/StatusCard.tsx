import React from 'react'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'

interface StatusCardProps {
  title: string
  subtitle: string
  status: 'loading' | 'healthy' | 'unhealthy'
  details?: Record<string, string | number | boolean | null | undefined>
  errorMessage?: string | null
}

export const StatusCard: React.FC<StatusCardProps> = ({
  title,
  subtitle,
  status,
  details,
  errorMessage,
}) => {
  return (
    <div className="bg-white rounded-xl border border-slate-200/90 shadow-sm p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
        </div>
        <div>
          {status === 'loading' && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" /> Connecting...
            </span>
          )}
          {status === 'healthy' && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/80">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> Operational
            </span>
          )}
          {status === 'unhealthy' && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200/80">
              <XCircle className="h-3.5 w-3.5 text-rose-600" /> Unreachable
            </span>
          )}
        </div>
      </div>

      {details && Object.keys(details).length > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs">
          {Object.entries(details).map(([key, value]) => (
            <div key={key}>
              <span className="text-slate-400 font-mono text-[11px] block capitalize">
                {key.replace(/_/g, ' ')}
              </span>
              <span className="font-mono font-medium text-slate-700">
                {value !== null && value !== undefined ? String(value) : '—'}
              </span>
            </div>
          ))}
        </div>
      )}

      {errorMessage && (
        <div className="mt-4 p-3 bg-rose-50/80 border border-rose-200/80 rounded-lg text-xs font-mono text-rose-700 break-words">
          <span className="font-semibold block mb-0.5">Diagnostic Error:</span>
          {errorMessage}
        </div>
      )}
    </div>
  )
}
