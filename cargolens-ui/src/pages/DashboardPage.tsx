import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  FileCheck2,
  AlertTriangle,
  Clock,
  Layers,
  ArrowRight,
  FileText,
  Activity,
  Plus,
  RefreshCw,
  ChevronRight,
  Loader2,
  FileWarning,
} from 'lucide-react'
import { fetchDashboardStats } from '../api/dashboard'
import { useAuth } from '../context/AuthContext'
import { Shipment, ShipmentStatus } from '../types/shipment'
import { CreateShipmentModal } from '../components/CreateShipmentModal'

const STATUS_BADGE: Record<ShipmentStatus, { label: string; badgeClass: string }> = {
  CREATED: { label: 'Created', badgeClass: 'bg-slate-100 text-slate-700 border-slate-300' },
  DOCUMENTS_PENDING: { label: 'Doc Pending', badgeClass: 'bg-amber-50 text-amber-700 border-amber-300' },
  PROCESSING: { label: 'Processing', badgeClass: 'bg-sky-50 text-sky-700 border-sky-300' },
  REVIEW_REQUIRED: { label: 'Review Req', badgeClass: 'bg-rose-50 text-rose-700 border-rose-300' },
  VERIFIED: { label: 'Verified', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
  EXPORTED: { label: 'Exported', badgeClass: 'bg-purple-50 text-purple-700 border-purple-300' },
  FAILED: { label: 'Failed', badgeClass: 'bg-red-100 text-red-800 border-red-300' },
}

export const DashboardPage: React.FC = () => {
  const { isManager, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)

  const {
    data: stats,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['dashboardStats'],
    queryFn: fetchDashboardStats,
    enabled: isAuthenticated,
    refetchInterval: 15000,
  })

  // Format activity action for human readability
  const formatActivityAction = (action: string) => {
    switch (action) {
      case 'SHIPMENT_CREATED':
        return 'Shipment Created'
      case 'DOCUMENT_UPLOADED':
        return 'Document Uploaded'
      case 'EXTRACTION_COMPLETED':
        return 'AI Extraction Done'
      case 'VALIDATION_RUN':
        return 'Validation Executed'
      case 'FIELD_CONFIRMED':
        return 'Field Confirmed'
      case 'FIELD_CORRECTED':
        return 'Field Corrected'
      case 'SHIPMENT_VERIFIED':
        return 'Shipment Verified'
      default:
        return action.replace(/_/g, ' ')
    }
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-500">
        <Loader2 className="h-8 w-8 animate-spin text-brand-600 mb-3" />
        <p className="text-sm font-medium">Loading Nhava Sheva Operations Dashboard...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-700 space-y-3">
        <div className="flex items-center gap-2 font-semibold">
          <AlertTriangle className="h-5 w-5" />
          <span>Failed to load dashboard statistics</span>
        </div>
        <p className="text-xs text-red-600">
          {(error as Error)?.message || 'An unexpected error occurred while communicating with the API.'}
        </p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-red-600 text-white text-xs font-semibold rounded-lg hover:bg-red-700 transition"
        >
          Retry Connection
        </button>
      </div>
    )
  }

  const execStats = stats?.executive
  const mgrStats = stats?.manager
  const recentShipments = isManager ? mgrStats?.recent_shipments || [] : execStats?.recent_shipments || []
  const recentActivity = isManager ? mgrStats?.recent_activity || [] : execStats?.recent_activity || []

  return (
    <div className="space-y-6">
      {/* Page Title & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {isManager ? 'Port Oversight Dashboard' : 'Documentation Operations Dashboard'}
            </h1>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-300">
              JNPT Hub
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {isManager
              ? 'Real-time overview of active consignments, document validation bottlenecks, and officer throughput.'
              : 'Track assigned import consignments, upload statuses, and pending document verifications.'}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-xs transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <Link
            to="/shipments/create"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-xs transition"
          >
            <Plus className="h-4 w-4" />
            New Consignment
          </Link>
        </div>
      </div>

      {/* Role-Specific Metric Cards */}
      {isManager && mgrStats ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Total Shipments</span>
              <Box className="h-4 w-4 text-brand-600" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-900">{mgrStats.total_shipments_count}</span>
              <span className="text-xs text-slate-500 font-medium">all officers</span>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Awaiting Review</span>
              <FileCheck2 className="h-4 w-4 text-amber-600" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-amber-600">
                {mgrStats.documents_awaiting_review_count}
              </span>
              <span className="text-xs text-slate-500 font-medium">docs flagged</span>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Validation Failures</span>
              <AlertTriangle className="h-4 w-4 text-rose-600" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-rose-600">
                {mgrStats.validation_failures_count}
              </span>
              <span className="text-xs text-slate-500 font-medium">cross-doc discrepancies</span>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Processing Failures</span>
              <FileWarning className="h-4 w-4 text-red-600" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-900">
                {mgrStats.processing_failures_count}
              </span>
              <span className="text-xs text-slate-500 font-medium">OCR/Extraction</span>
            </div>
          </div>
        </div>
      ) : execStats ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>My Shipments</span>
              <Box className="h-4 w-4 text-brand-600" />
            </div>
            <div className="mt-2">
              <span className="text-2xl font-extrabold text-slate-900">{execStats.my_shipments_count}</span>
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Uploaded Docs</span>
              <FileText className="h-4 w-4 text-indigo-600" />
            </div>
            <div className="mt-2">
              <span className="text-2xl font-extrabold text-slate-900">{execStats.documents_uploaded_count}</span>
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>In Processing</span>
              <Clock className="h-4 w-4 text-sky-600" />
            </div>
            <div className="mt-2">
              <span className="text-2xl font-extrabold text-sky-600">{execStats.processing_in_progress_count}</span>
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Awaiting Review</span>
              <FileCheck2 className="h-4 w-4 text-amber-600" />
            </div>
            <div className="mt-2">
              <span className="text-2xl font-extrabold text-amber-600">
                {execStats.documents_awaiting_review_count}
              </span>
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Discrepancies</span>
              <AlertTriangle className="h-4 w-4 text-rose-600" />
            </div>
            <div className="mt-2">
              <span className="text-2xl font-extrabold text-rose-600">
                {execStats.validation_failures_count}
              </span>
            </div>
          </div>
        </div>
      ) : null}

      {/* Manager Status Breakdown Visual */}
      {isManager && mgrStats && (
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <h2 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
            <Layers className="h-4 w-4 text-brand-600" />
            Port Consignment Status Distribution
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {Object.entries(mgrStats.shipments_by_status || {}).map(([stKey, count]) => {
              const cfg = STATUS_BADGE[stKey as ShipmentStatus] || {
                label: stKey,
                badgeClass: 'bg-slate-100 text-slate-700 border-slate-300',
              }
              return (
                <div
                  key={stKey}
                  onClick={() => navigate(`/shipments?status=${stKey}`)}
                  className="cursor-pointer p-3 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 transition-colors"
                >
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold border ${cfg.badgeClass}`}
                  >
                    {cfg.label}
                  </span>
                  <p className="text-xl font-bold text-slate-900 mt-2">{count}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Main Grid: Recent Shipments & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Recent Shipments */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col">
          <div className="p-4 sm:p-5 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Box className="h-4 w-4 text-brand-600" />
              Recently Updated Shipments
            </h2>
            <Link
              to="/shipments"
              className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1"
            >
              View All <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Shipment #</th>
                  <th className="py-3 px-4">Client</th>
                  <th className="py-3 px-4">Origin</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {recentShipments.length > 0 ? (
                  recentShipments.map((shp: Shipment) => {
                    const badge = STATUS_BADGE[shp.status] || {
                      label: shp.status,
                      badgeClass: 'bg-slate-100 text-slate-700 border-slate-300',
                    }
                    return (
                      <tr key={shp.id} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                          <Link
                            to={`/shipments/${shp.id}`}
                            className="text-brand-600 hover:underline flex items-center gap-1"
                          >
                            {shp.shipment_number}
                          </Link>
                        </td>
                        <td className="py-3 px-4 truncate max-w-[140px] font-medium">{shp.client_name}</td>
                        <td className="py-3 px-4 text-slate-500">{shp.origin_country || '—'}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${badge.badgeClass}`}
                          >
                            {badge.label}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Link
                            to={`/shipments/${shp.id}`}
                            className="inline-flex items-center gap-1 text-slate-600 hover:text-brand-600 font-medium text-xs"
                          >
                            Workspace <ChevronRight className="h-3 w-3" />
                          </Link>
                        </td>
                      </tr>
                    )
                  })
                ) : (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">
                      No active shipments found in this registry view.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right 1 Col: Recent Audit / Operations Activity */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col">
          <div className="p-4 sm:p-5 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-600" />
              Live Operational Activity
            </h2>
            <Link
              to="/audit-history"
              className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1"
            >
              Audit Trail <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="p-4 flex-1 overflow-y-auto max-h-[380px] space-y-3">
            {recentActivity.length > 0 ? (
              recentActivity.map((act) => (
                <div
                  key={act.id}
                  className="p-2.5 rounded-lg border border-slate-100 bg-slate-50/70 text-xs space-y-1 hover:bg-slate-50 transition"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900">
                      {formatActivityAction(act.action_type)}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {new Date(act.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="text-slate-600 text-[11px] truncate">{act.description}</p>
                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-200/50">
                    <span>{act.actor_name || 'System'}</span>
                    {act.shipment_number && (
                      <span className="font-mono text-brand-600">{act.shipment_number}</span>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-400 text-center py-6">
                No recent activity logged in this session.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Modal for Quick Creation */}
      <CreateShipmentModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={() => {
          setIsCreateModalOpen(false)
          refetch()
        }}
      />
    </div>
  )
}
