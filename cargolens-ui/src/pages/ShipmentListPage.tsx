import React, { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Plus,
  Search,
  Filter,
  Edit2,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Loader2,
  RefreshCw,
  Building2,
  Shield,
  FolderOpen,
} from 'lucide-react'
import { listShipments } from '../api/shipments'
import { Shipment, ShipmentStatus } from '../types/shipment'
import { useAuth } from '../context/AuthContext'
import { CreateShipmentModal } from '../components/CreateShipmentModal'
import { EditShipmentModal } from '../components/EditShipmentModal'
import { ShipmentDetailModal } from '../components/ShipmentDetailModal'

const STATUS_CONFIG: Record<ShipmentStatus, { label: string; badgeClass: string }> = {
  CREATED: { label: 'Created', badgeClass: 'bg-slate-100 text-slate-700 border-slate-300' },
  DOCUMENTS_PENDING: { label: 'Doc Pending', badgeClass: 'bg-amber-50 text-amber-700 border-amber-300' },
  PROCESSING: { label: 'Processing', badgeClass: 'bg-sky-50 text-sky-700 border-sky-300' },
  REVIEW_REQUIRED: { label: 'Review Req', badgeClass: 'bg-rose-50 text-rose-700 border-rose-300' },
  VERIFIED: { label: 'Verified', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
  EXPORTED: { label: 'Exported', badgeClass: 'bg-purple-50 text-purple-700 border-purple-300' },
  FAILED: { label: 'Failed', badgeClass: 'bg-red-100 text-red-800 border-red-300' },
}

export const ShipmentListPage: React.FC = () => {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { isManager } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()

  // Read initial query params from URL
  const initialStatus = (searchParams.get('status') as ShipmentStatus) || ''
  const initialSearch = searchParams.get('search') || ''

  // Filters & Pagination State
  const [search, setSearch] = useState(initialSearch)
  const [statusFilter, setStatusFilter] = useState<ShipmentStatus | ''>(initialStatus)
  const [page, setPage] = useState(1)
  const [limit] = useState(10)

  // Modal State
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [editingShipment, setEditingShipment] = useState<Shipment | null>(null)
  const [detailShipment, setDetailShipment] = useState<Shipment | null>(null)

  // Fetch Shipments with TanStack Query
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['shipments', { status: statusFilter || undefined, search: search.trim() || undefined, page, limit }],
    queryFn: () =>
      listShipments({
        status: statusFilter ? (statusFilter as ShipmentStatus) : undefined,
        search: search.trim() || undefined,
        page,
        limit,
      }),
  })

  const shipments = data?.items || []
  const total = data?.total || 0
  const totalPages = data?.total_pages || 1
  const statusSummary = data?.status_summary

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['shipments'] })
  }

  const handleStatusFilterChange = (val: string) => {
    const nextStatus = val as ShipmentStatus | ''
    setStatusFilter(nextStatus)
    setPage(1)
    if (nextStatus) {
      searchParams.set('status', nextStatus)
    } else {
      searchParams.delete('status')
    }
    setSearchParams(searchParams, { replace: true })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextVal = e.target.value
    setSearch(nextVal)
    setPage(1)
    if (nextVal.trim()) {
      searchParams.set('search', nextVal.trim())
    } else {
      searchParams.delete('search')
    }
    setSearchParams(searchParams, { replace: true })
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Shipment Registry
            </h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
              {isManager ? (
                <>
                  <Shield className="h-3 w-3 text-brand-600" /> Port Oversight
                </>
              ) : (
                <>
                  <Building2 className="h-3 w-3 text-slate-500" /> Assigned Entries
                </>
              )}
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            {isManager
              ? 'Complete overview of all import consignments cleared or pending across Nhava Sheva (JNPT).'
              : 'Manage, review, and verify import consignments registered under your documentation queue.'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            title="Refresh Registry"
            className="p-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
          <Link
            to="/shipments/create"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-sm shadow-xs transition-colors"
          >
            <Plus className="h-4 w-4 stroke-[2.5]" />
            <span>New Consignment</span>
          </Link>
        </div>
      </div>

      {/* Manager Status Summary Metrics Bar */}
      {isManager && statusSummary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {(
            [
              { key: 'CREATED', label: 'Created', color: 'border-slate-300 bg-slate-50 text-slate-700' },
              { key: 'DOCUMENTS_PENDING', label: 'Docs Pending', color: 'border-amber-200 bg-amber-50 text-amber-800' },
              { key: 'PROCESSING', label: 'Processing', color: 'border-sky-200 bg-sky-50 text-sky-800' },
              { key: 'REVIEW_REQUIRED', label: 'Review Req', color: 'border-rose-200 bg-rose-50 text-rose-800' },
              { key: 'VERIFIED', label: 'Verified', color: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
              { key: 'EXPORTED', label: 'Exported', color: 'border-purple-200 bg-purple-50 text-purple-800' },
              { key: 'FAILED', label: 'Failed', color: 'border-red-200 bg-red-50 text-red-800' },
            ] as const
          ).map((item) => {
            const count = statusSummary[item.key] || 0
            const isSelected = statusFilter === item.key
            return (
              <button
                key={item.key}
                onClick={() => handleStatusFilterChange(isSelected ? '' : item.key)}
                className={`p-3 rounded-xl border text-left transition-all ${item.color} ${
                  isSelected ? 'ring-2 ring-brand-500 shadow-xs' : 'hover:opacity-90'
                }`}
              >
                <div className="text-[11px] font-semibold uppercase tracking-wider opacity-75">{item.label}</div>
                <div className="text-xl font-bold font-mono mt-0.5">{count}</div>
              </button>
            )
          })}
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
        <div className="relative flex-1 max-w-md">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
            <Search className="h-4 w-4" />
          </div>
          <input
            type="text"
            value={search}
            onChange={handleSearchChange}
            placeholder="Search by shipment #, client, or goods description..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900"
          />
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <Filter className="h-3.5 w-3.5" /> Status:
          </div>
          <select
            value={statusFilter}
            onChange={(e) => handleStatusFilterChange(e.target.value)}
            className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="CREATED">Created</option>
            <option value="DOCUMENTS_PENDING">Documents Pending</option>
            <option value="PROCESSING">Processing</option>
            <option value="REVIEW_REQUIRED">Review Required</option>
            <option value="VERIFIED">Verified</option>
            <option value="EXPORTED">Exported</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
      </div>

      {/* Shipments Table Container */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-500">
            <Loader2 className="h-8 w-8 animate-spin text-brand-600 mb-2" />
            <span className="text-sm font-medium">Loading shipment records...</span>
          </div>
        ) : isError ? (
          <div className="p-8 text-center">
            <div className="inline-flex p-3 rounded-full bg-rose-50 text-rose-600 mb-2">
              <AlertCircle className="h-6 w-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-900">Failed to load shipments</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {(error as { message?: string })?.message || 'Server error occurred while retrieving registry.'}
            </p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-1.5 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors"
            >
              Try Again
            </button>
          </div>
        ) : shipments.length === 0 ? (
          <div className="py-16 text-center">
            <div className="inline-flex p-3.5 rounded-full bg-slate-100 text-slate-400 mb-3">
              <Box className="h-8 w-8" />
            </div>
            <h3 className="text-base font-semibold text-slate-900">No shipments found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              {search || statusFilter
                ? 'No consignments matched your current search or status filters. Try clearing filters.'
                : 'Get started by registering a new import consignment for customs documentation verification.'}
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              {(search || statusFilter) && (
                <button
                  onClick={() => {
                    setSearch('')
                    setStatusFilter('')
                    setPage(1)
                    searchParams.delete('status')
                    searchParams.delete('search')
                    setSearchParams(searchParams, { replace: true })
                  }}
                  className="px-3.5 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                >
                  Clear Filters
                </button>
              )}
              <button
                onClick={() => setIsCreateOpen(true)}
                className="px-3.5 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-xs transition-colors"
              >
                + Register Shipment
              </button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left">
              <thead className="bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th scope="col" className="px-5 py-3">Shipment Ref</th>
                  <th scope="col" className="px-5 py-3">Client</th>
                  <th scope="col" className="px-5 py-3">Origin</th>
                  <th scope="col" className="px-5 py-3">Goods</th>
                  <th scope="col" className="px-5 py-3 text-right">Quantity</th>
                  <th scope="col" className="px-5 py-3 text-right">Gross Wt (KG)</th>
                  <th scope="col" className="px-5 py-3 text-right">Unit Price</th>
                  <th scope="col" className="px-5 py-3 text-center">Status</th>
                  <th scope="col" className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {shipments.map((shipment) => {
                  const statusInfo = STATUS_CONFIG[shipment.status] || {
                    label: shipment.status,
                    badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
                  }

                  return (
                    <tr
                      key={shipment.id}
                      className="hover:bg-slate-50/80 transition-colors group cursor-pointer"
                      onClick={() => navigate(`/shipments/${shipment.id}`)}
                    >
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Link
                            to={`/shipments/${shipment.id}`}
                            className="font-mono font-bold text-brand-600 hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {shipment.shipment_number}
                          </Link>
                          {(shipment.client_name?.includes('[DEMO]') ||
                            shipment.shipment_number?.startsWith('SHP-DEMO-') ||
                            shipment.shipment_number?.startsWith('SHP-2481')) && (
                            <span className="text-[9px] px-1.5 py-0.2 bg-amber-100 text-amber-800 border border-amber-300 rounded font-bold">
                              DEMO
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {new Date(shipment.created_at).toLocaleDateString('en-IN', {
                            day: '2-digit',
                            month: 'short',
                            year: 'numeric',
                          })}
                        </div>
                      </td>

                      <td className="px-5 py-3.5">
                        <div className="font-semibold text-slate-900 line-clamp-1 max-w-[180px]">
                          {shipment.client_name}
                        </div>
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap text-slate-600 text-xs">
                        {shipment.origin_country || '—'}
                      </td>

                      <td className="px-5 py-3.5">
                        <div className="text-xs text-slate-600 line-clamp-1 max-w-[200px]">
                          {shipment.product_description || <span className="text-slate-400 italic">None</span>}
                        </div>
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap text-right font-mono text-xs text-slate-700">
                        {shipment.quantity !== null && shipment.quantity !== undefined
                          ? Number(shipment.quantity).toLocaleString()
                          : '—'}
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap text-right font-mono text-xs text-slate-700">
                        {shipment.gross_weight_kg !== null && shipment.gross_weight_kg !== undefined
                          ? Number(shipment.gross_weight_kg).toLocaleString()
                          : '—'}
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap text-right font-mono text-xs text-slate-700">
                        {shipment.unit_price !== null && shipment.unit_price !== undefined
                          ? `${Number(shipment.unit_price).toLocaleString(undefined, {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}${shipment.currency ? ' ' + shipment.currency : ''}`
                          : '—'}
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap text-center">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${statusInfo.badgeClass}`}
                        >
                          {statusInfo.label}
                        </span>
                      </td>

                      <td
                        className="px-5 py-3.5 whitespace-nowrap text-right"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            to={`/shipments/${shipment.id}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-brand-50 text-brand-700 hover:bg-brand-100 transition-colors"
                          >
                            <FolderOpen className="h-3.5 w-3.5" /> Workspace
                          </Link>
                          <button
                            onClick={() => setEditingShipment(shipment)}
                            title="Edit Shipment Details"
                            className="p-1.5 rounded-md text-slate-400 hover:text-amber-600 hover:bg-slate-100 transition-colors"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {total > 0 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-slate-200 bg-slate-50/50 text-xs text-slate-600">
            <div>
              Showing <span className="font-semibold text-slate-900">{(page - 1) * limit + 1}</span> to{' '}
              <span className="font-semibold text-slate-900">{Math.min(page * limit, total)}</span> of{' '}
              <span className="font-semibold text-slate-900">{total}</span> consignments
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="font-medium text-slate-700">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <CreateShipmentModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={handleRefresh}
      />

      <EditShipmentModal
        shipment={editingShipment}
        isOpen={!!editingShipment}
        onClose={() => setEditingShipment(null)}
        onSuccess={handleRefresh}
      />

      <ShipmentDetailModal
        shipment={detailShipment}
        isOpen={!!detailShipment}
        onClose={() => setDetailShipment(null)}
        onEdit={(s) => setEditingShipment(s)}
      />
    </div>
  )
}
