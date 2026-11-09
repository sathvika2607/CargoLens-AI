import React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ShieldAlert,
  Clock,
  CheckCircle2,
  AlertTriangle,
  FileDown,
  ArrowRight,
  Users,
  RefreshCw,
  Loader2,
  Shield,
  Activity,
  Sparkles,
} from 'lucide-react'
import { listShipments } from '../api/shipments'
import { fetchDashboardStats } from '../api/dashboard'
import { useAuth } from '../context/AuthContext'
import { ShipmentStatus } from '../types/shipment'

const STATUS_BADGE: Record<ShipmentStatus, { label: string; badgeClass: string }> = {
  CREATED: { label: 'Created', badgeClass: 'bg-slate-100 text-slate-700 border-slate-300' },
  DOCUMENTS_PENDING: { label: 'Doc Pending', badgeClass: 'bg-amber-50 text-amber-700 border-amber-300' },
  PROCESSING: { label: 'Processing', badgeClass: 'bg-sky-50 text-sky-700 border-sky-300' },
  REVIEW_REQUIRED: { label: 'Review Req', badgeClass: 'bg-rose-50 text-rose-700 border-rose-300' },
  VERIFIED: { label: 'Verified', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
  EXPORTED: { label: 'Exported', badgeClass: 'bg-purple-50 text-purple-700 border-purple-300' },
  FAILED: { label: 'Failed', badgeClass: 'bg-red-100 text-red-800 border-red-300' },
}

export const ManagerCommandCenterPage: React.FC = () => {
  const { isManager } = useAuth()

  const {
    data: shipmentsData,
    isLoading: isLoadingShipments,
    refetch: refetchShipments,
  } = useQuery({
    queryKey: ['shipments', 'manager-queue'],
    queryFn: () => listShipments({ limit: 100 }),
    refetchInterval: 10000,
  })

  const {
    refetch: refetchStats,
  } = useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: fetchDashboardStats,
    refetchInterval: 10000,
  })

  const shipments = shipmentsData?.items || []

  // Metrics aggregation
  const reviewQueue = shipments.filter((s) => s.status === 'REVIEW_REQUIRED')
  const processingQueue = shipments.filter((s) => s.status === 'PROCESSING')
  const verifiedQueue = shipments.filter((s) => s.status === 'VERIFIED')
  const exportedQueue = shipments.filter((s) => s.status === 'EXPORTED')

  const handleRefresh = () => {
    refetchShipments()
    refetchStats()
  }

  return (
    <div className="space-y-6 select-none">
      {/* Top Header & Role Notice */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-bold bg-indigo-900 text-indigo-200 border border-indigo-700">
              <Shield className="h-3.5 w-3.5 text-indigo-300" />
              <span>Manager Command Deck</span>
            </span>
            <span className="text-xs text-slate-500 font-mono">• JNPT Port Terminal INNSA</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Clearance Operations & Verification Oversight
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time queue velocity, reviewer bottlenecks, and customs declaration authorization across the terminal.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition shadow-sm"
          >
            <RefreshCw className="h-3.5 w-3.5 text-slate-500" />
            <span>Refresh Telemetry</span>
          </button>
          <Link
            to="/simulation"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg shadow-sm transition"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-500" />
            <span>Simulation Center</span>
          </Link>
          <Link
            to="/exports"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-sm transition"
          >
            <FileDown className="h-3.5 w-3.5" />
            <span>Customs Export Portal</span>
          </Link>
        </div>
      </div>

      {!isManager && (
        <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-xs text-amber-900">
            <span className="font-semibold text-amber-950">Executive Telemetry Mode:</span> You are viewing the Command Center as a{' '}
            <span className="font-bold">Documentation Executive</span>. You can review consignment queues and assigned tasks. Final customs export release is restricted to Documentation Managers.
          </div>
        </div>
      )}

      {/* Primary KPI Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Awaiting Human Review</p>
            <h3 className="text-2xl font-extrabold text-rose-600 mt-1">
              {isLoadingShipments ? '...' : reviewQueue.length}
            </h3>
            <span className="text-[11px] text-slate-400 mt-0.5 block">Requires field confirmation/correction</span>
          </div>
          <div className="h-11 w-11 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
            <ShieldAlert className="h-6 w-6 stroke-[2.2]" />
          </div>
        </div>

        {/* Metric 2 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">In Active OCR / AI Extraction</p>
            <h3 className="text-2xl font-extrabold text-sky-600 mt-1">
              {isLoadingShipments ? '...' : processingQueue.length}
            </h3>
            <span className="text-[11px] text-slate-400 mt-0.5 block">Worker leases active</span>
          </div>
          <div className="h-11 w-11 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center">
            <Activity className="h-6 w-6 stroke-[2.2]" />
          </div>
        </div>

        {/* Metric 3 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Verified & Export Ready</p>
            <h3 className="text-2xl font-extrabold text-emerald-600 mt-1">
              {isLoadingShipments ? '...' : verifiedQueue.length}
            </h3>
            <span className="text-[11px] text-slate-400 mt-0.5 block">All 11 rules passed</span>
          </div>
          <div className="h-11 w-11 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <CheckCircle2 className="h-6 w-6 stroke-[2.2]" />
          </div>
        </div>

        {/* Metric 4 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Exported to Customs</p>
            <h3 className="text-2xl font-extrabold text-purple-600 mt-1">
              {isLoadingShipments ? '...' : exportedQueue.length}
            </h3>
            <span className="text-[11px] text-slate-400 mt-0.5 block">SHA-256 snapshot sealed</span>
          </div>
          <div className="h-11 w-11 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
            <FileDown className="h-6 w-6 stroke-[2.2]" />
          </div>
        </div>
      </div>

      {/* Operational Velocity & Port Clearance SLA Tracker */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Priority Verification Queue */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
                <ShieldAlert className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-900">Priority Review Queue (Action Required)</h2>
                <p className="text-xs text-slate-500">Consignments with discrepancies or awaiting human verification.</p>
              </div>
            </div>
            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
              {reviewQueue.length} Pending
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Consignment</th>
                  <th className="py-3 px-4">Client / Consignee</th>
                  <th className="py-3 px-4">Origin & Commodity</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoadingShipments ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">
                      <Loader2 className="h-5 w-5 animate-spin mx-auto mb-2 text-brand-600" />
                      <span>Loading operations queue...</span>
                    </td>
                  </tr>
                ) : reviewQueue.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">
                      <CheckCircle2 className="h-6 w-6 text-emerald-500 mx-auto mb-1" />
                      <p className="text-xs font-medium text-slate-600">Review queue is clear!</p>
                      <span className="text-[11px] text-slate-400">No shipments currently require human intervention.</span>
                    </td>
                  </tr>
                ) : (
                  reviewQueue.map((shp) => (
                    <tr key={shp.id} className="hover:bg-slate-50/60 transition">
                      <td className="py-3.5 px-4 font-mono font-bold text-brand-700">
                        <Link to={`/shipments/${shp.id}`} className="hover:underline">
                          {shp.shipment_number}
                        </Link>
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-900">
                        {shp.client_name}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600">
                        <span className="font-semibold text-slate-800">{shp.origin_country}</span>
                        {shp.product_description && (
                          <span className="block text-[11px] text-slate-400 truncate max-w-xs">
                            {shp.product_description}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${STATUS_BADGE[shp.status]?.badgeClass}`}>
                          {STATUS_BADGE[shp.status]?.label || shp.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          to={`/shipments/${shp.id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-brand-600 hover:text-white hover:bg-brand-600 border border-brand-200 hover:border-brand-600 rounded-md transition"
                        >
                          <span>Review</span>
                          <ArrowRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Col: Team Oversight & Audit Status */}
        <div className="space-y-6">
          {/* Card: Team Allocation */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
              <Users className="h-4 w-4 text-indigo-600" />
              <h3 className="text-sm font-bold text-slate-900">Active Review Personnel</h3>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                <div className="flex items-center gap-2">
                  <div className="h-7 w-7 rounded-full bg-sky-100 text-sky-800 flex items-center justify-center font-bold text-[11px]">
                    DE
                  </div>
                  <div>
                    <span className="font-semibold text-slate-900 block">Documentation Executive</span>
                    <span className="text-[10px] text-slate-500 font-mono">executive@cargolens.in</span>
                  </div>
                </div>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-100 text-sky-800 font-semibold font-mono">
                  ACTIVE
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                <div className="flex items-center gap-2">
                  <div className="h-7 w-7 rounded-full bg-indigo-100 text-indigo-800 flex items-center justify-center font-bold text-[11px]">
                    DM
                  </div>
                  <div>
                    <span className="font-semibold text-slate-900 block">Documentation Manager</span>
                    <span className="text-[10px] text-slate-500 font-mono">manager@cargolens.in</span>
                  </div>
                </div>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800 font-semibold font-mono">
                  SUPERVISOR
                </span>
              </div>
            </div>

            <p className="text-[11px] text-slate-400">
              All human field reviews are cryptographically recorded in the immutable audit log with reviewer ID and timestamp.
            </p>
          </div>

          {/* Card: SLA & Gate Velocity */}
          <div className="bg-slate-900 text-white rounded-xl p-5 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
                  Nhava Sheva Port Clearance SLA
                </span>
                <span className="text-[10px] text-amber-400 font-semibold uppercase tracking-wider">
                  (Port Operational Benchmark — Illustrative Target)
                </span>
              </div>
              <Clock className="h-4 w-4 text-brand-400" />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Average Turnaround:</span>
                <span className="font-mono font-bold text-emerald-400">42 seconds</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Validation Pass Rate:</span>
                <span className="font-mono font-bold text-sky-400">98.4%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Discrepancy Capture:</span>
                <span className="font-mono font-bold text-amber-400">100% Deterministic</span>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800">
              <Link
                to="/analytics"
                className="text-xs text-brand-300 hover:text-white font-semibold flex items-center gap-1"
              >
                <span>View Full Customs Analytics</span>
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
