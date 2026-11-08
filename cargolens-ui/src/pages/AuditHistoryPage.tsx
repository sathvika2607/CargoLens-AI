import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Search,
  Filter,
  RefreshCw,
  Loader2,
  FolderOpen,
  AlertTriangle,
  UserCheck,
} from 'lucide-react'
import { fetchGlobalAuditHistory } from '../api/reviews'

export const AuditHistoryPage: React.FC = () => {
  const [actionFilter, setActionFilter] = useState<'CONFIRMED' | 'CORRECTED' | ''>('')
  const [provenanceFilter, setProvenanceFilter] = useState<'USER_ACTION' | 'DEMO_SEED' | ''>('')
  const [searchTerm, setSearchTerm] = useState('')

  const {
    data: auditData,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['globalAuditHistory'],
    queryFn: () => fetchGlobalAuditHistory(100),
    refetchInterval: 15000,
  })

  const items = auditData?.items || []
  const filteredItems = items.filter((item) => {
    if (actionFilter && item.action !== actionFilter) return false
    if (provenanceFilter && (item.provenance || 'USER_ACTION') !== provenanceFilter) return false
    if (!searchTerm.trim()) return true
    const term = searchTerm.toLowerCase()
    return (
      item.field_name.toLowerCase().includes(term) ||
      (item.reviewer_name && item.reviewer_name.toLowerCase().includes(term)) ||
      (item.reviewer_email && item.reviewer_email.toLowerCase().includes(term)) ||
      (item.reason && item.reason.toLowerCase().includes(term)) ||
      String(item.original_value || '').toLowerCase().includes(term) ||
      String(item.corrected_value || '').toLowerCase().includes(term)
    )
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Review & Verification Audit Trail
            </h1>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-300">
              {auditData?.total || 0} Actions Logged
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Immutable log of all human verifications, value confirmations, and field corrections across Nhava Sheva.
          </p>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-xs"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh Audit
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
        <div className="relative flex-1 max-w-md">
          <Search className="h-4 w-4 absolute left-3 top-3 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by field name, reviewer, or reason..."
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 text-slate-900"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold">
            <Filter className="h-3.5 w-3.5" /> Action:
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value as any)}
              className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800"
            >
              <option value="">All Actions</option>
              <option value="CONFIRMED">CONFIRMED</option>
              <option value="CORRECTED">CORRECTED</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold">
            <span>Provenance:</span>
            <select
              value={provenanceFilter}
              onChange={(e) => setProvenanceFilter(e.target.value as any)}
              className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800"
            >
              <option value="">All Provenance</option>
              <option value="USER_ACTION">Human Reviews Only</option>
              <option value="DEMO_SEED">Demo Fixtures Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-500">
            <Loader2 className="h-8 w-8 animate-spin text-brand-600 mb-2" />
            <span className="text-sm font-medium">Retrieving audit events...</span>
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-xs text-red-600">
            Failed to retrieve audit trail: {(error as Error)?.message}
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            No audit records found matching your filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Provenance</th>
                  <th className="py-3 px-4">Reviewer</th>
                  <th className="py-3 px-4">Field Name</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Value History</th>
                  <th className="py-3 px-4">Audit Rationale</th>
                  <th className="py-3 px-4 text-right">Workspace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredItems.map((item) => {
                  const isDemoSeed = item.provenance === 'DEMO_SEED'

                  return (
                    <tr
                      key={item.id}
                      className={`hover:bg-slate-50 transition-colors ${
                        isDemoSeed ? 'bg-amber-50/20' : ''
                      }`}
                    >
                      <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                        {new Date(item.created_at).toLocaleString()}
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
                            <UserCheck className="h-3 w-3 text-blue-600 flex-shrink-0" />
                            Human Review
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {isDemoSeed ? (
                          <div>
                            <div className="font-semibold text-amber-900">Demonstration Fixture</div>
                            <span className="text-[10px] text-amber-700 font-mono block">
                              Attributed to {item.reviewer_email || 'manager@cargolens.in'}
                            </span>
                            <span className="text-[9px] text-slate-400 italic block">
                              Automated demonstration dataset
                            </span>
                          </div>
                        ) : (
                          <div>
                            <div className="font-semibold text-slate-900">{item.reviewer_name || 'Officer'}</div>
                            <span className="text-[10px] text-slate-400">
                              {item.reviewer_email || item.reviewer_role || 'Executive'}
                            </span>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                        {item.field_name}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            item.action === 'CONFIRMED'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                          }`}
                        >
                          {item.action}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {item.action === 'CORRECTED' ? (
                          <div className="space-x-1">
                            <span className="line-through text-slate-400">{String(item.original_value)}</span>
                            <span className="text-slate-400">→</span>
                            <span className="font-bold text-indigo-900">{String(item.corrected_value)}</span>
                          </div>
                        ) : (
                          <span className="text-slate-600 font-medium">{String(item.original_value)}</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-600 max-w-xs truncate">
                        {item.reason || <span className="text-slate-400 italic">None</span>}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to={`/shipments/${item.shipment_id}`}
                          className="inline-flex items-center gap-1 text-brand-600 hover:underline font-semibold"
                        >
                          <FolderOpen className="h-3 w-3" /> View
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
