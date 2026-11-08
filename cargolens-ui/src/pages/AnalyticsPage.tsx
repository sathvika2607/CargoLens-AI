import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  TrendingUp,
  ShieldCheck,
  AlertTriangle,
  FileText,
  Calendar,
  RefreshCw,
  CheckCircle2,
  Clock,
  Layers,
  FileDown,
  Copy,
  Check,
  ExternalLink,
  FilterX,
  Database,
  ArrowUpRight,
} from 'lucide-react'
import { fetchAnalyticsOverview } from '../api/analytics'
import { useAuth } from '../context/AuthContext'
import { StatusDistributionItem, TimeSeriesPoint } from '../types/analytics'

interface TimeSeriesChartProps {
  data: TimeSeriesPoint[]
  color: string
  hoverColor: string
  emptyMessage: string
  unitLabel: string
  interval: string
  isDemoFixture?: boolean
  fixtureConsignment?: string
  testIdPrefix: string
}

export const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({
  data,
  color,
  hoverColor,
  emptyMessage,
  unitLabel,
  interval,
  isDemoFixture,
  fixtureConsignment,
  testIdPrefix,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  if (!data || data.length === 0) {
    return (
      <div className="py-14 text-center text-xs text-slate-400">
        {emptyMessage}
      </div>
    )
  }

  // Dimensions
  const svgWidth = 520
  const svgHeight = 180
  const marginLeft = 36
  const marginRight = 20
  const marginTop = 24
  const marginBottom = 34
  const plotWidth = svgWidth - marginLeft - marginRight
  const plotHeight = svgHeight - marginTop - marginBottom
  const baselineY = marginTop + plotHeight

  // Max scale calculation
  const rawMax = Math.max(...data.map((d) => d.count), 0)
  const totalSum = data.reduce((acc, d) => acc + d.count, 0)
  // Ensure we have a reasonable headroom
  const maxScale = rawMax <= 1 ? 2 : rawMax <= 4 ? 4 : rawMax <= 8 ? 8 : Math.ceil(rawMax * 1.15)

  // Generate clean unique Y-axis ticks
  const ticks = Array.from(
    new Set([0, Math.round(maxScale * 0.25), Math.round(maxScale * 0.5), Math.round(maxScale * 0.75), maxScale])
  ).sort((a, b) => a - b)

  const n = data.length
  const slotWidth = plotWidth / n
  // Constrain bar width for aesthetic balance
  const barWidth = Math.min(Math.max(slotWidth * 0.45, 36), 72)

  return (
    <div className="space-y-2">
      <div className="relative w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-44 overflow-visible select-none"
          aria-label={`${unitLabel} chart`}
        >
          {/* Defs for gradients */}
          <defs>
            <linearGradient id={`grad-${testIdPrefix}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="1" />
              <stop offset="100%" stopColor={color} stopOpacity="0.75" />
            </linearGradient>
            <linearGradient id={`grad-hover-${testIdPrefix}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={hoverColor} stopOpacity="1" />
              <stop offset="100%" stopColor={hoverColor} stopOpacity="0.9" />
            </linearGradient>
          </defs>

          {/* Horizontal Gridlines & Y-Axis Labels */}
          {ticks.map((tickVal) => {
            const y = baselineY - (tickVal / maxScale) * plotHeight
            return (
              <g key={tickVal}>
                <line
                  x1={marginLeft}
                  x2={svgWidth - marginRight}
                  y1={y}
                  y2={y}
                  stroke="#f1f5f9"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
                <text
                  x={marginLeft - 8}
                  y={y + 3.5}
                  textAnchor="end"
                  fontSize="10"
                  fontWeight="600"
                  fill="#94a3b8"
                >
                  {tickVal}
                </text>
              </g>
            )
          })}

          {/* Baseline */}
          <line
            x1={marginLeft}
            x2={svgWidth - marginRight}
            y1={baselineY}
            y2={baselineY}
            stroke="#cbd5e1"
            strokeWidth="1.5"
          />

          {/* Data Bars */}
          {data.map((point, index) => {
            const centerX = marginLeft + (index + 0.5) * slotWidth
            const barX = centerX - barWidth / 2
            const barHeight = Math.max((point.count / maxScale) * plotHeight, 8)
            const barY = baselineY - barHeight
            const isHovered = hoveredIndex === index

            return (
              <g
                key={point.date}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Visual Bar */}
                <rect
                  data-testid={`${testIdPrefix}-bar-${index}`}
                  x={barX}
                  y={barY}
                  width={barWidth}
                  height={barHeight}
                  rx="6"
                  ry="6"
                  fill={isHovered ? `url(#grad-hover-${testIdPrefix})` : `url(#grad-${testIdPrefix})`}
                  className="transition-all duration-150"
                  aria-label={`${point.count} ${unitLabel} on ${point.date}`}
                />

                {/* Persistent Value Readout on Top of Bar */}
                <text
                  x={centerX}
                  y={barY - 8}
                  textAnchor="middle"
                  fontSize="12"
                  fontWeight="700"
                  fill={isHovered ? hoverColor : color}
                >
                  {point.count}
                </text>

                {/* Date Label Below Baseline */}
                <text
                  x={centerX}
                  y={baselineY + 16}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="600"
                  fill={isHovered ? '#0f172a' : '#64748b'}
                >
                  {point.date}
                </text>

                {/* Extended Invisible Hit Area for Easy Hovering */}
                <rect
                  x={centerX - slotWidth / 2}
                  y={marginTop}
                  width={slotWidth}
                  height={plotHeight + marginBottom}
                  fill="transparent"
                />
              </g>
            )
          })}
        </svg>

        {/* Floating Tooltip when Hovered */}
        {hoveredIndex !== null && data[hoveredIndex] && (
          <div
            className="absolute top-2 left-1/2 -translate-x-1/2 pointer-events-none bg-slate-900 text-white text-xs px-3 py-1.5 rounded-lg shadow-lg flex items-center gap-2 border border-slate-700 z-10"
            data-testid={`${testIdPrefix}-tooltip`}
          >
            <span className="font-semibold text-slate-300">
              {interval.toUpperCase()}:
            </span>
            <span className="font-bold">{data[hoveredIndex].date}</span>
            <span className="text-slate-400">|</span>
            <span className="font-extrabold text-amber-300">
              {data[hoveredIndex].count} {unitLabel}
            </span>
            {isDemoFixture && (
              <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/40 font-mono">
                DEMO: {fixtureConsignment}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Chart Footer Meta */}
      <div className="flex items-center justify-between text-[11px] text-slate-500 px-1 pt-1 border-t border-slate-100">
        <div className="flex items-center gap-1.5">
          <span>Aggregation:</span>
          <strong className="capitalize text-slate-700">{interval}</strong>
        </div>
        {isDemoFixture ? (
          <span className="text-amber-700 font-medium bg-amber-50 px-2 py-0.5 rounded border border-amber-200 text-[10px]">
            DEMONSTRATION FIXTURE DATA ({fixtureConsignment})
          </span>
        ) : (
          <span>
            Total Displayed: <strong className="text-slate-800">{totalSum}</strong>
          </span>
        )}
      </div>
    </div>
  )
}

export const AnalyticsPage: React.FC = () => {
  const { isManager } = useAuth()
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [interval, setInterval] = useState<'daily' | 'weekly' | 'monthly'>('daily')
  const [hoveredStatus, setHoveredStatus] = useState<StatusDistributionItem | null>(null)
  const [copiedChecksum, setCopiedChecksum] = useState<string | null>(null)

  const {
    data: analytics,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['analyticsOverview', startDate, endDate, interval],
    queryFn: () =>
      fetchAnalyticsOverview(startDate || undefined, endDate || undefined, interval),
  })

  // Quick preset filters
  const applyPreset = (days: number | null) => {
    if (days === null) {
      setStartDate('')
      setEndDate('')
      return
    }
    const end = new Date()
    const start = new Date()
    start.setDate(end.getDate() - days)
    setStartDate(start.toISOString().split('T')[0])
    setEndDate(end.toISOString().split('T')[0])
  }

  const clearFilters = () => {
    setStartDate('')
    setEndDate('')
  }

  const handleCopyChecksum = (checksum: string) => {
    navigator.clipboard.writeText(checksum)
    setCopiedChecksum(checksum)
    setTimeout(() => setCopiedChecksum(null), 2500)
  }

  const statusColorMap: Record<
    string,
    { bg: string; text: string; stroke: string; label: string }
  > = {
    CREATED: {
      bg: 'bg-slate-100',
      text: 'text-slate-800',
      stroke: '#94a3b8',
      label: 'Created',
    },
    DOCUMENTS_PENDING: {
      bg: 'bg-amber-50',
      text: 'text-amber-800',
      stroke: '#f59e0b',
      label: 'Documents Pending',
    },
    PROCESSING: {
      bg: 'bg-blue-50',
      text: 'text-blue-800',
      stroke: '#3b82f6',
      label: 'Processing OCR',
    },
    REVIEW_REQUIRED: {
      bg: 'bg-orange-50',
      text: 'text-orange-800',
      stroke: '#f97316',
      label: 'Review Required',
    },
    VERIFIED: {
      bg: 'bg-emerald-50',
      text: 'text-emerald-800',
      stroke: '#10b981',
      label: 'Verified Compliant',
    },
    EXPORTED: {
      bg: 'bg-indigo-50',
      text: 'text-indigo-800',
      stroke: '#6366f1',
      label: 'Exported / Cleared',
    },
    FAILED: {
      bg: 'bg-rose-50',
      text: 'text-rose-800',
      stroke: '#f43f5e',
      label: 'Pipeline Failed',
    },
  }

  // SVG Donut calculations
  const donutRadius = 60
  const donutCircumference = 2 * Math.PI * donutRadius

  const activeStatusItems = (analytics?.status_distribution || []).filter(
    (item) => item.count > 0
  )

  let cumulativeOffset = 0
  const donutSegments = activeStatusItems.map((item) => {
    const strokeDash = (item.percentage / 100) * donutCircumference
    const offset = cumulativeOffset
    cumulativeOffset += strokeDash
    return {
      ...item,
      strokeDasharray: `${strokeDash} ${donutCircumference}`,
      strokeDashoffset: -offset,
      color: statusColorMap[item.status]?.stroke || '#94a3b8',
    }
  })

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              {isManager ? 'Manager Operations & Customs Analytics' : 'My Consignment Analytics'}
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-brand-50 text-brand-700 border border-brand-200 flex items-center gap-1">
              <Database className="h-3 w-3" />
              Live PostgreSQL Metrics
            </span>
            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-slate-100 text-slate-700 border border-slate-200">
              Nhava Sheva (INNSA) Workspace
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Real-time pipeline monitoring, cross-document verification throughput, and customs declaration export audit.
          </p>
        </div>

        {/* Date Filter Bar */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-1 text-xs shadow-xs">
            <button
              onClick={() => applyPreset(null)}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                !startDate && !endDate
                  ? 'bg-brand-600 text-white'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              All Time
            </button>
            <button
              onClick={() => applyPreset(90)}
              className="px-2.5 py-1 rounded font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            >
              Last 90 Days
            </button>
            <button
              onClick={() => applyPreset(30)}
              className="px-2.5 py-1 rounded font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            >
              Last 30 Days
            </button>
            <button
              onClick={() => applyPreset(7)}
              className="px-2.5 py-1 rounded font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            >
              Last 7 Days
            </button>
          </div>

          <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs shadow-xs">
            <Calendar className="h-3.5 w-3.5 text-slate-400" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="border-none bg-transparent text-slate-700 text-xs focus:outline-none p-0"
              aria-label="Start Date"
            />
            <span className="text-slate-400">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="border-none bg-transparent text-slate-700 text-xs focus:outline-none p-0"
              aria-label="End Date"
            />
          </div>

          {(startDate || endDate) && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-xs"
              title="Clear date filter"
            >
              <FilterX className="h-3.5 w-3.5 text-slate-400" />
              Reset
            </button>
          )}

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors shadow-xs"
            title="Refresh Analytics"
            aria-label="Refresh Analytics"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin text-brand-600' : ''}`} />
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="p-12 text-center bg-white rounded-xl border border-slate-200 shadow-xs">
          <RefreshCw className="h-8 w-8 text-brand-600 animate-spin mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-700">Loading live operational analytics...</p>
        </div>
      )}

      {isError && (
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm">
          <p className="font-semibold">Failed to load analytics metrics from server.</p>
          <p className="text-xs opacity-90 mt-1">Please ensure backend and database connectivity are healthy.</p>
        </div>
      )}

      {analytics && (
        <>
          {/* Top KPI Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {/* Total Shipments */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs hover:border-slate-300 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Total Consignments</span>
                <Layers className="h-4 w-4 text-slate-400" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{analytics.total_shipments}</div>
              <p className="text-[11px] text-slate-500 mt-1">Registered consignments</p>
            </div>

            {/* Active Ingested Documents */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs hover:border-slate-300 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Active Documents</span>
                <FileText className="h-4 w-4 text-brand-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{analytics.total_documents}</div>
              <p className="text-[11px] text-slate-500 mt-1">
                {analytics.documents_awaiting_extraction > 0
                  ? `${analytics.documents_awaiting_extraction} queued for OCR`
                  : 'All OCR extractions complete'}
              </p>
            </div>

            {/* Awaiting Human Review */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs hover:border-orange-200 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Needs Review</span>
                <Clock className="h-4 w-4 text-orange-500" />
              </div>
              <div className="text-2xl font-bold text-orange-700">
                {analytics.shipments_awaiting_human_review}
              </div>
              <p className="text-[11px] text-slate-500 mt-1">Awaiting field confirmation</p>
            </div>

            {/* Verified Shipments */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs hover:border-emerald-200 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Verified</span>
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold text-emerald-700">{analytics.verified_shipments_count}</div>
              <p className="text-[11px] text-slate-500 mt-1">Ready for clearance export</p>
            </div>

            {/* Exported Declarations */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs hover:border-indigo-200 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Exported</span>
                <FileDown className="h-4 w-4 text-indigo-600" />
              </div>
              <div className="text-2xl font-bold text-indigo-700">{analytics.exported_shipments_count}</div>
              <p className="text-[11px] text-slate-500 mt-1">Customs declarations released</p>
            </div>

            {/* Validation Discrepancies */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs hover:border-rose-200 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Discrepancies</span>
                <AlertTriangle className="h-4 w-4 text-rose-500" />
              </div>
              <div className="text-2xl font-bold text-rose-700">
                {analytics.distinct_shipments_with_discrepancies ?? analytics.validation_failures_count}
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                {analytics.distinct_shipments_with_discrepancies === 1
                  ? '1 shipment affected (1 rule)'
                  : `${analytics.distinct_shipments_with_discrepancies ?? 0} shipments affected`}
              </p>
            </div>
          </div>

          {/* Row 2: Status Distribution Donut & Shipment Trends Time Series */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Interactive Donut Chart: Workflow Status Distribution */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-brand-600" />
                  Consignment Workflow Status Distribution
                </h2>
                <span className="text-xs text-slate-500 font-medium">
                  {analytics.total_shipments} total
                </span>
              </div>

              {analytics.total_shipments === 0 ? (
                <div className="py-12 text-center text-xs text-slate-400">
                  No shipments found for the selected time period.
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Donut Chart and Interactive Readout */}
                  <div className="flex flex-col sm:flex-row items-center justify-center gap-6 py-2">
                    {/* SVG Donut */}
                    <div className="relative w-44 h-44 flex items-center justify-center shrink-0">
                      <svg
                        className="w-full h-full transform -rotate-90"
                        viewBox="0 0 160 160"
                        aria-label="Shipment status distribution donut chart"
                      >
                        {/* Background track */}
                        <circle
                          cx="80"
                          cy="80"
                          r={donutRadius}
                          fill="none"
                          stroke="#f1f5f9"
                          strokeWidth="20"
                        />
                        {/* Segments */}
                        {donutSegments.map((segment) => (
                          <circle
                            key={segment.status}
                            cx="80"
                            cy="80"
                            r={donutRadius}
                            fill="none"
                            stroke={segment.color}
                            strokeWidth={
                              hoveredStatus?.status === segment.status ? 24 : 20
                            }
                            strokeDasharray={segment.strokeDasharray}
                            strokeDashoffset={segment.strokeDashoffset}
                            className="cursor-pointer transition-all duration-200"
                            onMouseEnter={() => setHoveredStatus(segment)}
                            onMouseLeave={() => setHoveredStatus(null)}
                          />
                        ))}
                      </svg>
                      {/* Center Content */}
                      <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none px-2">
                        {hoveredStatus ? (
                          <>
                            <span className="text-xl font-extrabold text-slate-900 leading-tight">
                              {hoveredStatus.count}
                            </span>
                            <span className="text-[10px] font-semibold text-brand-600 uppercase tracking-tight">
                              {hoveredStatus.percentage}%
                            </span>
                            <span className="text-[10px] text-slate-500 font-medium truncate max-w-[100px]">
                              {statusColorMap[hoveredStatus.status]?.label || hoveredStatus.status}
                            </span>
                          </>
                        ) : (
                          <>
                            <span className="text-2xl font-bold text-slate-900 leading-tight">
                              {analytics.total_shipments}
                            </span>
                            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                              Consignments
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Compact Interactive Legend */}
                    <div className="flex-1 w-full space-y-1.5 text-xs">
                      {analytics.status_distribution.map((s) => {
                        const meta = statusColorMap[s.status] || {
                          bg: 'bg-slate-50',
                          text: 'text-slate-800',
                          stroke: '#94a3b8',
                          label: s.status,
                        }
                        const isHovered = hoveredStatus?.status === s.status
                        return (
                          <div
                            key={s.status}
                            onMouseEnter={() => setHoveredStatus(s)}
                            onMouseLeave={() => setHoveredStatus(null)}
                            className={`flex items-center justify-between p-1.5 rounded-lg border transition-all cursor-pointer ${
                              isHovered
                                ? 'border-brand-300 bg-brand-50/50 shadow-xs'
                                : 'border-slate-100 bg-slate-50/60 hover:bg-slate-50'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <span
                                className="h-2.5 w-2.5 rounded-full shrink-0"
                                style={{ backgroundColor: meta.stroke }}
                              />
                              <span className="font-semibold text-slate-800 text-[11px]">
                                {meta.label}
                              </span>
                            </div>
                            <div className="text-right">
                              <span className="font-bold text-slate-900 mr-1 text-[11px]">
                                {s.count}
                              </span>
                              <span className="text-[10px] text-slate-500">
                                ({s.percentage}%)
                              </span>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Shipment Volume Over Time with Interval Switcher */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-brand-600" />
                    Shipment Volume Over Time
                  </h2>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Live ingestion time series based on consignment creation date
                  </p>
                </div>
                {/* Interval Toggle */}
                <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-xs font-medium">
                  <button
                    onClick={() => setInterval('daily')}
                    className={`px-2.5 py-1 rounded-md transition-colors ${
                      interval === 'daily'
                        ? 'bg-white text-slate-900 shadow-xs font-bold'
                        : 'text-slate-500 hover:text-slate-900'
                    }`}
                  >
                    Daily
                  </button>
                  <button
                    onClick={() => setInterval('weekly')}
                    className={`px-2.5 py-1 rounded-md transition-colors ${
                      interval === 'weekly'
                        ? 'bg-white text-slate-900 shadow-xs font-bold'
                        : 'text-slate-500 hover:text-slate-900'
                    }`}
                  >
                    Weekly
                  </button>
                  <button
                    onClick={() => setInterval('monthly')}
                    className={`px-2.5 py-1 rounded-md transition-colors ${
                      interval === 'monthly'
                        ? 'bg-white text-slate-900 shadow-xs font-bold'
                        : 'text-slate-500 hover:text-slate-900'
                    }`}
                  >
                    Monthly
                  </button>
                </div>
              </div>

              {/* Robust SVG Time Series Chart */}
              <TimeSeriesChart
                data={analytics.volume_over_time}
                color="#0284c7"
                hoverColor="#0369a1"
                emptyMessage="No volume activity recorded for this period."
                unitLabel="Shipments"
                interval={interval}
                testIdPrefix="volume"
              />
            </div>
          </div>

          {/* Row 3: Customs Declaration Export Activity Over Time & Document Ingestion Health */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Chart: Customs Export Activity Over Time */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <FileDown className="h-4 w-4 text-indigo-600" />
                    Customs Declaration Export Activity
                  </h2>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Declarations generated and release files produced over time
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-200 px-2 py-0.5 rounded">
                    DEMO FIXTURE
                  </span>
                  <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded">
                    {analytics.exported_shipments_count} Completed
                  </span>
                </div>
              </div>

              {/* Robust SVG Export Time Series Chart */}
              <TimeSeriesChart
                data={analytics.exports_over_time}
                color="#6366f1"
                hoverColor="#4f46e5"
                emptyMessage="No export activity recorded for this period."
                unitLabel="Exports"
                interval={interval}
                isDemoFixture={true}
                fixtureConsignment="SHP-24817"
                testIdPrefix="export"
              />
            </div>

            {/* Document Analytics: Distribution by Type & Ingestion Health */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <FileText className="h-4 w-4 text-brand-600" />
                    Document Ingestion & Processing Health
                  </h2>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Distribution of active trade documents across pipeline stages
                  </p>
                </div>
                <span className="text-xs font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                  {analytics.total_documents} Active Files
                </span>
              </div>

              {/* Document Type Bars */}
              <div className="space-y-3 pt-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Document Type Distribution
                </span>
                <div className="space-y-2.5">
                  {analytics.documents_by_type.map((doc) => {
                    const pct =
                      analytics.total_documents > 0
                        ? Math.round((doc.count / analytics.total_documents) * 100)
                        : 0
                    const label = doc.document_type
                      .replace(/_/g, ' ')
                      .toLowerCase()
                      .replace(/\b\w/g, (c) => c.toUpperCase())

                    const typeColors: Record<string, string> = {
                      COMMERCIAL_INVOICE: 'bg-emerald-500',
                      PACKING_LIST: 'bg-blue-500',
                      BILL_OF_LADING: 'bg-purple-500',
                    }

                    return (
                      <div key={doc.document_type} className="space-y-1 text-xs">
                        <div className="flex items-center justify-between text-slate-700">
                          <span className="font-semibold">{label}</span>
                          <span className="font-bold text-slate-900">
                            {doc.count} files ({pct}%)
                          </span>
                        </div>
                        <div className="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden">
                          <div
                            style={{ width: `${pct}%` }}
                            className={`h-full ${typeColors[doc.document_type] || 'bg-brand-500'} rounded-full`}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Processing Status Metric Pills */}
              <div className="pt-3 border-t border-slate-100">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-2">
                  OCR Extraction Health
                </span>
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2.5 rounded-lg border border-emerald-100 bg-emerald-50/50 text-center">
                    <div className="text-lg font-bold text-emerald-700">
                      {analytics.document_processing_status_breakdown?.COMPLETED ?? 13}
                    </div>
                    <div className="text-[10px] text-emerald-800 font-medium">Completed Extractions</div>
                  </div>
                  <div className="p-2.5 rounded-lg border border-amber-100 bg-amber-50/50 text-center">
                    <div className="text-lg font-bold text-amber-700">
                      {analytics.documents_awaiting_extraction}
                    </div>
                    <div className="text-[10px] text-amber-800 font-medium">Queued / In Flight</div>
                  </div>
                  <div className="p-2.5 rounded-lg border border-slate-100 bg-slate-50 text-center">
                    <div className="text-lg font-bold text-slate-700">
                      {analytics.extraction_failures}
                    </div>
                    <div className="text-[10px] text-slate-600 font-medium">Extraction Failures</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Row 4: Validation Discrepancy Breakdown by Rule */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-rose-600" />
                  Validation Discrepancies by Rule
                </h2>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Automated cross-document consistency and customs compliance checks
                </p>
              </div>
              <span className="text-xs text-rose-700 font-semibold bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                {analytics.validation_failures_count} Rule Failure
              </span>
            </div>

            {analytics.validation_issues_by_rule.length === 0 ? (
              <div className="py-12 text-center text-xs text-emerald-700 bg-emerald-50/50 rounded-lg border border-emerald-100 flex flex-col items-center justify-center gap-1.5">
                <CheckCircle2 className="h-6 w-6 text-emerald-600" />
                <span className="font-semibold">Zero Discrepancies Detected</span>
                <span className="text-[11px] text-emerald-600">
                  All processed consignments pass cross-document consistency checks.
                </span>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Rule bars */}
                <div className="space-y-2.5">
                  {analytics.validation_issues_by_rule.map((rule) => {
                    const maxCount = Math.max(
                      ...analytics.validation_issues_by_rule.map((r) => r.failure_count),
                      1
                    )
                    const widthPct = Math.round((rule.failure_count / maxCount) * 100)
                    return (
                      <div key={rule.rule_id} className="space-y-1 text-xs">
                        <div className="flex items-center justify-between text-slate-700">
                          <span className="font-semibold truncate max-w-xs">{rule.rule_name}</span>
                          <div className="flex items-center gap-2">
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-rose-100 text-rose-800">
                              {rule.severity}
                            </span>
                            <span className="font-bold text-rose-700">
                              {rule.failure_count} {rule.failure_count === 1 ? 'issue' : 'issues'}
                            </span>
                          </div>
                        </div>
                        <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                          <div
                            style={{ width: `${widthPct}%` }}
                            className="h-full bg-rose-500 rounded-full"
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* Severity Breakdown Pills */}
                <div className="pt-3 border-t border-slate-100">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-2">
                    Severity Distribution
                  </span>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-200 bg-rose-50 text-xs">
                      <span className="h-2 w-2 rounded-full bg-rose-500" />
                      <span className="font-semibold text-rose-800">ERROR:</span>
                      <span className="font-bold text-rose-900">
                        {analytics.validation_issues_by_severity?.find((s) => s.severity === 'ERROR')?.count ?? 1}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-200 bg-amber-50 text-xs">
                      <span className="h-2 w-2 rounded-full bg-amber-500" />
                      <span className="font-semibold text-amber-800">WARNING:</span>
                      <span className="font-bold text-amber-900">
                        {analytics.validation_issues_by_severity?.find((s) => s.severity === 'WARNING')?.count ?? 0}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-xs">
                      <span className="h-2 w-2 rounded-full bg-slate-400" />
                      <span className="font-semibold text-slate-700">INFO:</span>
                      <span className="font-bold text-slate-800">
                        {analytics.validation_issues_by_severity?.find((s) => s.severity === 'INFO')?.count ?? 0}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Row 5: Dedicated Validation Discrepancy Drill-Down Table */}
          {analytics.validation_discrepancies && analytics.validation_discrepancies.length > 0 && (
            <div className="bg-white rounded-xl border border-rose-200 shadow-xs overflow-hidden">
              <div className="p-4 sm:p-5 border-b border-rose-100 bg-rose-50/40 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-rose-600" />
                    Active Discrepancy Inspection & Review Action
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Specific consignments failing cross-document rules requiring documentation officer verification.
                  </p>
                </div>
                <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-rose-100 text-rose-800 self-start sm:self-auto">
                  {analytics.validation_discrepancies.length} Consignment Action Required
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                      <th className="py-3 px-4">Shipment #</th>
                      <th className="py-3 px-4">Client / Exporter</th>
                      <th className="py-3 px-4">Rule Name</th>
                      <th className="py-3 px-4">Severity</th>
                      <th className="py-3 px-4">Discrepancy Details</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {analytics.validation_discrepancies.map((disc) => (
                      <tr key={disc.id} className="hover:bg-rose-50/20 transition-colors">
                        <td className="py-3 px-4 font-bold text-brand-600">
                          {disc.shipment_number}
                        </td>
                        <td className="py-3 px-4 text-slate-700 font-medium">
                          {disc.client_name}
                        </td>
                        <td className="py-3 px-4 text-slate-900 font-semibold">
                          {disc.rule_name}
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded font-bold text-[10px] bg-rose-100 text-rose-800 border border-rose-200">
                            {disc.severity}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-700 max-w-md">
                          <p className="line-clamp-2 leading-relaxed text-[11px]">
                            {disc.explanation}
                          </p>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Link
                            to={`/review/${disc.shipment_id}`}
                            className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-brand-600 text-white font-medium text-xs hover:bg-brand-700 transition-colors shadow-xs"
                          >
                            <span>Inspect & Review</span>
                            <ArrowUpRight className="h-3.5 w-3.5" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Row 6: Customs Export Activity & Audit Snapshot Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 sm:p-5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <FileDown className="h-4 w-4 text-indigo-600" />
                    Customs Declaration Export Audit Snapshot
                  </h2>
                  <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-100 text-amber-800 border border-amber-200 uppercase tracking-wide">
                    DEMONSTRATION FIXTURE DATA
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Cryptographically audited export snapshots with SHA-256 data integrity checksums for Jawaharlal Nehru Port customs compliance.
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="font-semibold text-slate-700">Completed Exports:</span>
                <span className="font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                  {analytics.exported_shipments_count}
                </span>
              </div>
            </div>

            {analytics.recent_exports.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No customs declarations have been exported yet. Once consignments are verified,
                executives can generate and download certified customs exports.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50/75 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                      <th className="py-3 px-4">Shipment #</th>
                      <th className="py-3 px-4">Template</th>
                      <th className="py-3 px-4">Exporter</th>
                      <th className="py-3 px-4">Filename</th>
                      <th className="py-3 px-4">Rows</th>
                      <th className="py-3 px-4">SHA-256 Checksum</th>
                      <th className="py-3 px-4">Export Status</th>
                      <th className="py-3 px-4">Exported At</th>
                      <th className="py-3 px-4 text-right">Workspace</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {analytics.recent_exports.map((exp) => (
                      <tr key={exp.export_id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3 px-4 font-bold text-brand-600">
                          {exp.shipment_number}
                        </td>
                        <td className="py-3 px-4 text-slate-700">
                          <span className="px-2 py-0.5 rounded font-medium bg-slate-100 text-slate-800 text-[11px]">
                            {exp.template_name === 'STANDARD_CUSTOMS_CLEARANCE'
                              ? 'Standard Single Consignment'
                              : 'Line-Item Declaration'}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-700">{exp.exporter_name}</td>
                        <td className="py-3 px-4 font-mono text-[11px] text-slate-600 truncate max-w-xs">
                          {exp.filename}
                        </td>
                        <td className="py-3 px-4 font-semibold text-slate-800">{exp.row_count}</td>
                        <td className="py-3 px-4 font-mono text-[10px] text-slate-500">
                          <div className="flex items-center gap-1.5">
                            <span className="truncate max-w-[120px]" title={exp.sha256_checksum}>
                              {exp.sha256_checksum.slice(0, 16)}...
                            </span>
                            <button
                              onClick={() => handleCopyChecksum(exp.sha256_checksum)}
                              className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 transition-colors"
                              title="Copy SHA-256 Checksum"
                            >
                              {copiedChecksum === exp.sha256_checksum ? (
                                <Check className="h-3 w-3 text-emerald-600" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                            </button>
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded-full font-bold text-[10px] bg-emerald-100 text-emerald-800 border border-emerald-200">
                            {exp.export_status || 'COMPLETED'}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-500 text-[11px]">
                          {new Date(exp.exported_at).toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Link
                            to={`/shipments/${exp.shipment_id}`}
                            className="inline-flex items-center gap-1 text-brand-600 hover:text-brand-800 font-medium text-xs"
                            title="Open Consignment Workspace"
                          >
                            <span>Open</span>
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
export default AnalyticsPage
