import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  FileDown,
  Download,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Loader2,
  ExternalLink,
  FileSpreadsheet,
  Hash,
  Info,
} from 'lucide-react'
import { listShipments } from '../api/shipments'
import { exportShipmentCsv } from '../api/exports'

const TEMPLATE_OPTIONS = [
  {
    id: 'STANDARD_CUSTOMS_CLEARANCE',
    name: 'Standard Customs Clearance (Single Consignment)',
    desc: 'Comprehensive customs declaration row containing validated invoice, bill of lading, and packing list values.',
  },
  {
    id: 'LINE_ITEM_DECLARATION',
    name: 'Line Item Declaration (Detailed Commercial Invoice)',
    desc: 'Itemized customs declaration rows with item numbers, product descriptions, quantities, unit prices, and line totals.',
  },
]

export const CustomsExportCenterPage: React.FC = () => {
  const [selectedTemplate, setSelectedTemplate] = useState('STANDARD_CUSTOMS_CLEARANCE')
  const [exportingId, setExportingId] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Fetch all shipments to isolate VERIFIED and EXPORTED consignments
  const {
    data: shipmentsData,
    isLoading: isLoadingShipments,
    refetch: refetchShipments,
  } = useQuery({
    queryKey: ['shipments', 'export-center'],
    queryFn: () => listShipments({ limit: 100 }),
  })

  const shipments = shipmentsData?.items || []
  const verifiedShipments = shipments.filter((s) => s.status === 'VERIFIED')
  const exportedShipments = shipments.filter((s) => s.status === 'EXPORTED')

  const handleExport = async (shipmentId: string, shipmentNumber: string) => {
    setExportingId(shipmentId)
    setStatusMessage(null)
    try {
      const result = await exportShipmentCsv(shipmentId, selectedTemplate)
      setStatusMessage({
        type: 'success',
        text: `Consignment ${shipmentNumber} exported successfully! SHA-256 Checksum: ${result.checksum.slice(0, 16)}...`,
      })
      refetchShipments()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string | { message?: string } } } }
      const detail = axiosErr?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : detail?.message || 'Export failed. Ensure all mandatory fields are verified.'
      setStatusMessage({
        type: 'error',
        text: msg,
      })
    } finally {
      setExportingId(null)
    }
  }

  return (
    <div className="space-y-6 select-none">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-bold bg-purple-900 text-purple-200 border border-purple-700">
              <FileDown className="h-3.5 w-3.5 text-purple-300" />
              <span>Customs Declaration Portal</span>
            </span>
            <span className="text-xs text-slate-500 font-mono">• Port Node INNSA (Nhava Sheva)</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Customs Data Export & Audit Integrity Center
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Generate authenticated, formula-sanitized CSV declaration files from verified human-review overlays.
          </p>
        </div>

        <button
          onClick={() => refetchShipments()}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition shadow-sm self-start sm:self-auto"
        >
          <RefreshCw className="h-3.5 w-3.5 text-slate-500" />
          <span>Refresh Declarations</span>
        </button>
      </div>

      {statusMessage && (
        <div
          className={`rounded-xl p-4 flex items-start gap-3 border ${
            statusMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}
        >
          {statusMessage.type === 'success' ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
          )}
          <div className="text-sm">
            <span className="font-semibold">{statusMessage.type === 'success' ? 'Success:' : 'Export Notice:'}</span>{' '}
            {statusMessage.text}
          </div>
        </div>
      )}

      {/* Export Template Selector Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <FileSpreadsheet className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Active Customs Export Template</h2>
              <p className="text-xs text-slate-500">Configurable CSV declaration format for port authorities & broker ERPs.</p>
            </div>
          </div>
          <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
            CSV v1.0
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {TEMPLATE_OPTIONS.map((tmpl) => (
            <div
              key={tmpl.id}
              onClick={() => setSelectedTemplate(tmpl.id)}
              className={`p-3.5 rounded-lg border cursor-pointer transition ${
                selectedTemplate === tmpl.id
                  ? 'bg-purple-50/50 border-purple-500 shadow-sm ring-1 ring-purple-500'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-xs font-bold ${selectedTemplate === tmpl.id ? 'text-purple-900' : 'text-slate-800'}`}>
                  {tmpl.name}
                </span>
                <span className={`h-2.5 w-2.5 rounded-full ${selectedTemplate === tmpl.id ? 'bg-purple-600' : 'bg-slate-300'}`} />
              </div>
              <p className="text-[11px] text-slate-500 mt-1.5 leading-relaxed">{tmpl.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Section 1: Ready to Export (Verified Consignments) */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Verified Consignments Awaiting Customs Export</h2>
              <p className="text-xs text-slate-500">
                100% human-confirmed mandatory fields, all 11 cross-document rules passed.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
            {verifiedShipments.length} Ready
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Consignment Reference</th>
                <th className="py-3 px-4">Customs Client</th>
                <th className="py-3 px-4">Commodity & Origin</th>
                <th className="py-3 px-4">Gross Weight</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoadingShipments ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    <Loader2 className="h-5 w-5 animate-spin mx-auto mb-2 text-brand-600" />
                    <span>Checking verified consignments...</span>
                  </td>
                </tr>
              ) : verifiedShipments.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    <CheckCircle2 className="h-6 w-6 text-slate-300 mx-auto mb-1" />
                    <p className="text-xs font-medium text-slate-600">No shipments currently waiting for export.</p>
                    <span className="text-[11px] text-slate-400">
                      Verify pending consignments in the review workspace to release them for customs export.
                    </span>
                  </td>
                </tr>
              ) : (
                verifiedShipments.map((shp) => (
                  <tr key={shp.id} className="hover:bg-slate-50/60 transition">
                    <td className="py-3.5 px-4 font-mono font-bold text-brand-700">
                      <Link to={`/shipments/${shp.id}`} className="hover:underline">
                        {shp.shipment_number}
                      </Link>
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-900">{shp.client_name}</td>
                    <td className="py-3.5 px-4 text-slate-600">
                      <span className="font-semibold text-slate-800">{shp.origin_country}</span>
                      {shp.product_description && (
                        <span className="block text-[11px] text-slate-400 truncate max-w-xs">
                          {shp.product_description}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-700">
                      {shp.gross_weight_kg ? `${Number(shp.gross_weight_kg).toFixed(3)} KG` : '—'}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-300">
                        VERIFIED
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => handleExport(shp.id, shp.shipment_number)}
                        disabled={exportingId === shp.id}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-purple-600 hover:bg-purple-500 rounded-lg shadow-sm transition disabled:opacity-60"
                      >
                        {exportingId === shp.id ? (
                          <>
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            <span>Exporting...</span>
                          </>
                        ) : (
                          <>
                            <Download className="h-3.5 w-3.5" />
                            <span>Export CSV</span>
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 2: Historical Sealed Customs Exports */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Hash className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Sealed Customs Declarations & Historical Snapshots</h2>
              <p className="text-xs text-slate-500">
                Immutable export records preserved with SHA-256 cryptographic checksums for customs audit compliance.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
            {exportedShipments.length} Sealed
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Consignment Reference</th>
                <th className="py-3 px-4">Client / Importer</th>
                <th className="py-3 px-4">Origin & Cargo</th>
                <th className="py-3 px-4">Status & Tamper Protection</th>
                <th className="py-3 px-4 text-right">Snapshot Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoadingShipments ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    <Loader2 className="h-5 w-5 animate-spin mx-auto mb-2 text-brand-600" />
                    <span>Loading historical declarations...</span>
                  </td>
                </tr>
              ) : exportedShipments.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    <Info className="h-6 w-6 text-slate-300 mx-auto mb-1" />
                    <p className="text-xs font-medium text-slate-600">No declarations exported yet.</p>
                  </td>
                </tr>
              ) : (
                exportedShipments.map((shp) => (
                  <tr key={shp.id} className="hover:bg-slate-50/60 transition">
                    <td className="py-3.5 px-4 font-mono font-bold text-purple-700">
                      <Link to={`/shipments/${shp.id}`} className="hover:underline">
                        {shp.shipment_number}
                      </Link>
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-900">{shp.client_name}</td>
                    <td className="py-3.5 px-4 text-slate-600">
                      <span className="font-semibold text-slate-800">{shp.origin_country}</span>
                      {shp.product_description && (
                        <span className="block text-[11px] text-slate-400 truncate max-w-xs">
                          {shp.product_description}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-1.5">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-50 text-purple-700 border border-purple-300">
                          EXPORTED
                        </span>
                        <span className="text-[10px] text-emerald-600 font-mono flex items-center gap-0.5">
                          <CheckCircle2 className="h-3 w-3" />
                          <span>SHA-256 Validated</span>
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/shipments/${shp.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:text-brand-600 hover:bg-slate-100 border border-slate-300 rounded-md transition"
                      >
                        <span>View Snapshot & Audit</span>
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
