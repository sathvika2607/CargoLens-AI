import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Filter,
  Search,
  RefreshCw,
  FolderOpen,
  FileCheck2,
  CheckCircle2,
  Loader2,
  ChevronRight,
} from 'lucide-react'
import { listValidationIssues } from '../api/validations'
import { ValidationSeverity, ValidationOutcome } from '../types/validation'

export const ValidationIssuesPage: React.FC = () => {
  const [severityFilter, setSeverityFilter] = useState<ValidationSeverity | ''>('')
  const [outcomeFilter, setOutcomeFilter] = useState<ValidationOutcome | ''>('FAIL')
  const [searchTerm, setSearchTerm] = useState('')

  const {
    data: issuesData,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['validationIssues', { severity: severityFilter || undefined, outcome: outcomeFilter || undefined }],
    queryFn: () =>
      listValidationIssues({
        severity: severityFilter ? (severityFilter as ValidationSeverity) : undefined,
        outcome: outcomeFilter ? (outcomeFilter as ValidationOutcome) : undefined,
        limit: 100,
      }),
  })

  const issues = issuesData?.items || []
  const filteredIssues = issues.filter((issue) => {
    if (!searchTerm.trim()) return true
    const term = searchTerm.toLowerCase()
    return (
      issue.rule_name.toLowerCase().includes(term) ||
      (issue.shipment_number && issue.shipment_number.toLowerCase().includes(term)) ||
      (issue.explanation && issue.explanation.toLowerCase().includes(term))
    )
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Cross-Document Validation Issues
            </h1>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
              {issuesData?.total || 0} Issues Logged
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Consolidated view of arithmetic errors, weight mismatches, and date conflicts across active consignments.
          </p>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-xs"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh Issues
        </button>
      </div>

      {/* Filter and Search Controls */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
        <div className="relative flex-1 max-w-md">
          <Search className="h-4 w-4 absolute left-3 top-3 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by rule, shipment #, or explanation..."
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 text-slate-900"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold">
            <Filter className="h-3.5 w-3.5" /> Severity:
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as any)}
              className="text-xs px-2 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800"
            >
              <option value="">All Severities</option>
              <option value="ERROR">ERROR</option>
              <option value="WARNING">WARNING</option>
              <option value="INFO">INFO</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold">
            Outcome:
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value as any)}
              className="text-xs px-2 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800"
            >
              <option value="">All Outcomes</option>
              <option value="FAIL">FAIL (Discrepancies)</option>
              <option value="MISSING_DATA">MISSING DATA</option>
            </select>
          </div>
        </div>
      </div>

      {/* Issues Cards Container */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-500">
            <Loader2 className="h-8 w-8 animate-spin text-brand-600 mb-2" />
            <span className="text-sm font-medium">Scanning cross-document issues...</span>
          </div>
        ) : isError ? (
          <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs">
            Failed to load validation issues: {(error as Error)?.message}
          </div>
        ) : filteredIssues.length === 0 ? (
          <div className="py-16 text-center bg-white rounded-xl border border-slate-200">
            <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
            <h3 className="text-sm font-bold text-slate-900">No Discrepancies Found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              All active consignments match the selected validation criteria without blocking errors.
            </p>
          </div>
        ) : (
          filteredIssues.map((issue) => (
            <div
              key={issue.id}
              className={`p-4 rounded-xl border bg-white shadow-xs space-y-3 transition-all ${
                issue.outcome === 'FAIL' ? 'border-rose-200' : 'border-amber-200'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-xs font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
                    {issue.shipment_number || 'Shipment'}
                  </span>
                  <span className="text-sm font-bold text-slate-900">{issue.rule_name}</span>
                  <span className="font-mono text-[10px] text-slate-400">({issue.rule_id})</span>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      issue.severity === 'ERROR'
                        ? 'bg-rose-100 text-rose-800'
                        : issue.severity === 'WARNING'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-slate-100 text-slate-700'
                    }`}
                  >
                    {issue.severity}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      issue.outcome === 'FAIL'
                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}
                  >
                    {issue.outcome}
                  </span>
                </div>
              </div>

              {issue.explanation && (
                <p className="text-xs text-slate-700 font-medium">{issue.explanation}</p>
              )}

              {/* Compared values viewer */}
              {issue.compared_values && Object.keys(issue.compared_values).length > 0 && (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[11px] text-slate-800 overflow-x-auto">
                  <span className="text-[10px] font-sans font-semibold text-slate-400 block mb-1">
                    Conflict Values:
                  </span>
                  <pre className="whitespace-pre-wrap">{JSON.stringify(issue.compared_values, null, 2)}</pre>
                </div>
              )}

              {/* Quick Action Navigation Links */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                <span className="text-[11px] text-slate-400">
                  Detected {new Date(issue.created_at).toLocaleString()}
                </span>

                <div className="flex items-center gap-2">
                  <Link
                    to={`/review/${issue.shipment_id}`}
                    className="inline-flex items-center gap-1 text-slate-600 hover:text-brand-600 font-semibold"
                  >
                    <FileCheck2 className="h-3.5 w-3.5" /> Review Extracted Values
                  </Link>
                  <span className="text-slate-300">•</span>
                  <Link
                    to={`/shipments/${issue.shipment_id}`}
                    className="inline-flex items-center gap-1 text-brand-600 hover:underline font-semibold"
                  >
                    <FolderOpen className="h-3.5 w-3.5" /> Open Workspace <ChevronRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
