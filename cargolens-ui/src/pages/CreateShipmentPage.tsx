import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Box,
  Building2,
  Globe2,
  DollarSign,
  Scale,
  FileText,
  AlertCircle,
  Loader2,
  CheckCircle2,
  HelpCircle,
  Sparkles,
} from 'lucide-react'
import { createShipment } from '../api/shipments'
import { ShipmentCreatePayload } from '../types/shipment'

const COMMON_ORIGINS = [
  'China',
  'Germany',
  'Japan',
  'South Korea',
  'Singapore',
  'United States',
  'United Arab Emirates',
  'France',
  'United Kingdom',
  'Italy',
  'Vietnam',
  'Netherlands',
]

const COMMON_CURRENCIES = ['USD', 'EUR', 'INR', 'JPY', 'GBP', 'AED', 'SGD', 'CNY']

export const CreateShipmentPage: React.FC = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Form State
  const [shipmentNumber, setShipmentNumber] = useState('')
  const [clientName, setClientName] = useState('')
  const [originCountry, setOriginCountry] = useState('China')
  const [productDescription, setProductDescription] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [quantity, setQuantity] = useState<string>('')
  const [unitPrice, setUnitPrice] = useState<string>('')
  const [grossWeightKg, setGrossWeightKg] = useState<string>('')
  const [formError, setFormError] = useState<string | null>(null)

  const generateShipmentNumber = () => {
    const randomSuffix = Math.floor(10000 + Math.random() * 90000)
    setShipmentNumber(`SHP-${randomSuffix}`)
  }

  // Calculate live valuation
  const qtyNum = parseFloat(quantity)
  const priceNum = parseFloat(unitPrice)
  const calculatedTotal = !isNaN(qtyNum) && !isNaN(priceNum) && qtyNum >= 0 && priceNum >= 0
    ? (qtyNum * priceNum).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : null

  const createMutation = useMutation({
    mutationFn: (payload: ShipmentCreatePayload) => createShipment(payload),
    onSuccess: (newShipment) => {
      queryClient.invalidateQueries({ queryKey: ['shipments'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      // Navigate straight to Screen 6: Document Upload Center
      navigate(`/shipments/${newShipment.id}/documents`)
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      const detail = axiosErr?.response?.data?.detail
      if (typeof detail === 'string') {
        setFormError(detail)
      } else {
        setFormError('Failed to register consignment. Please verify all required fields.')
      }
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    const trimmedNum = shipmentNumber.trim()
    const trimmedClient = clientName.trim()
    const trimmedOrigin = originCountry.trim()

    if (!trimmedNum) {
      setFormError('Consignment reference number is mandatory.')
      return
    }
    if (!trimmedClient) {
      setFormError('Customs Client / Consignee entity name is mandatory.')
      return
    }
    if (!trimmedOrigin) {
      setFormError('Origin country of dispatch is mandatory.')
      return
    }

    const payload: ShipmentCreatePayload = {
      shipment_number: trimmedNum,
      client_name: trimmedClient,
      origin_country: trimmedOrigin,
      product_description: productDescription.trim() || undefined,
      currency: currency || undefined,
      quantity: !isNaN(qtyNum) && qtyNum > 0 ? qtyNum : undefined,
      unit_price: !isNaN(priceNum) && priceNum >= 0 ? priceNum : undefined,
      gross_weight_kg: grossWeightKg ? parseFloat(grossWeightKg) : undefined,
    }

    createMutation.mutate(payload)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 select-none">
      {/* Top Breadcrumb & Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <Link
            to="/shipments"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition mb-2"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Consignment Registry</span>
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <span>Register New Import Consignment</span>
            <span className="text-xs px-2 py-0.5 rounded font-mono font-bold bg-brand-50 text-brand-700 border border-brand-200">
              JNPT Port Hub
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Initiate a customs pre-clearance verification workspace. Once registered, you will upload the customs triad (Commercial Invoice, Packing List, Bill of Lading).
          </p>
        </div>
      </div>

      {formError && (
        <div className="rounded-xl bg-rose-50 border border-rose-200 p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="text-sm text-rose-800">
            <span className="font-semibold">Registration Blocked:</span> {formError}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Card 1: Consignment Identity */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
            <div className="h-8 w-8 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center">
              <Box className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">1. Consignment Identity & Parties</h2>
              <p className="text-xs text-slate-500">Unique tracking reference and primary customs entity.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Consignment Reference <span className="text-rose-500">*</span>
                </label>
                <button
                  type="button"
                  onClick={generateShipmentNumber}
                  className="text-[11px] font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1"
                >
                  <Sparkles className="h-3 w-3" />
                  <span>Auto-Generate</span>
                </button>
              </div>
              <input
                type="text"
                required
                value={shipmentNumber}
                onChange={(e) => setShipmentNumber(e.target.value)}
                placeholder="e.g. SHP-24818"
                className="block w-full px-3 py-2 text-sm font-mono border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 placeholder-slate-400"
              />
              <span className="text-[11px] text-slate-400 mt-1 block">
                Standard format: SHP-XXXXX matching broker filing dossier.
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Customs Client / Consignee <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Building2 className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  required
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  placeholder="e.g. Schneider Electric India Pvt Ltd"
                  className="block w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 placeholder-slate-400"
                />
              </div>
              <span className="text-[11px] text-slate-400 mt-1 block">
                Official importer of record recognized under Indian ICEGATE records.
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Country of Export / Origin <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Globe2 className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  list="origins-list"
                  required
                  value={originCountry}
                  onChange={(e) => setOriginCountry(e.target.value)}
                  placeholder="Select or enter country"
                  className="block w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 placeholder-slate-400"
                />
                <datalist id="origins-list">
                  {COMMON_ORIGINS.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Port of Discharge
              </label>
              <input
                type="text"
                disabled
                value="Nhava Sheva (INNSA), JNPT Terminal"
                className="block w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg text-slate-600 cursor-not-allowed font-medium"
              />
            </div>
          </div>
        </div>

        {/* Card 2: Commodity & Declared Valuation */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
            <div className="h-8 w-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <DollarSign className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">2. Commodity Description & Valuation</h2>
              <p className="text-xs text-slate-500">Commercial declaration figures to be cross-verified against invoice items.</p>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              Goods / Commodity Trade Description
            </label>
            <input
              type="text"
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="e.g. Industrial Conveyor Belts Heat Resistant 500mm EP400"
              className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 placeholder-slate-400"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Invoice Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 bg-white"
              >
                {COMMON_CURRENCIES.map((cur) => (
                  <option key={cur} value={cur}>
                    {cur}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Declared Quantity
              </label>
              <input
                type="number"
                step="any"
                min="0"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="e.g. 2400"
                className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 placeholder-slate-400 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Declared Unit Price
              </label>
              <input
                type="number"
                step="0.0001"
                min="0"
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                placeholder="e.g. 6.80"
                className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 placeholder-slate-400 font-mono"
              />
            </div>
          </div>

          {calculatedTotal && (
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
              <span className="text-slate-600 font-medium">Calculated Estimated Consignment Value:</span>
              <span className="font-mono font-bold text-slate-900 text-sm">
                {currency} {calculatedTotal}
              </span>
            </div>
          )}
        </div>

        {/* Card 3: Logistics & Weight */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
            <div className="h-8 w-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
              <Scale className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">3. Physical Cargo & Weight Specification</h2>
              <p className="text-xs text-slate-500">Subject to the 1.0 kg tolerance rule against packing list & bill of lading.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Gross Weight (KG)
              </label>
              <div className="relative">
                <input
                  type="number"
                  step="0.001"
                  min="0"
                  value={grossWeightKg}
                  onChange={(e) => setGrossWeightKg(e.target.value)}
                  placeholder="e.g. 3120.000"
                  className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 placeholder-slate-400 font-mono"
                />
                <span className="absolute inset-y-0 right-0 pr-3 flex items-center text-xs font-semibold text-slate-400">
                  KG
                </span>
              </div>
              <span className="text-[11px] text-slate-400 mt-1 block">
                Stored in 3-decimal precision (0.001 kg = 1 gram).
              </span>
            </div>

            <div className="p-3.5 rounded-lg bg-amber-50/60 border border-amber-200/80 text-xs text-amber-900 flex items-start gap-2.5">
              <HelpCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Automated Verification Notice:</span>
                <p className="mt-0.5 text-amber-800">
                  CargoLens AI evaluates Gross Weight across the Commercial Invoice and Packing List. Any variance exceeding 1.0 kg will trigger a blocking discrepancy (Rule 8).
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Card 4: Required Pre-Clearance Triad Preview */}
        <div className="bg-slate-900 text-white rounded-xl p-6 border border-slate-800 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-brand-400" />
            <h3 className="text-sm font-bold text-white">Next Step: Document Triad Ingestion</h3>
          </div>
          <p className="text-xs text-slate-300">
            Upon creating this consignment, you will be taken to the Document Upload Center to ingest the three required customs files:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 text-xs">
              <div className="font-semibold text-sky-400">1. Commercial Invoice</div>
              <p className="text-[11px] text-slate-400 mt-1">Invoice number, line items, prices, and grand total.</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 text-xs">
              <div className="font-semibold text-emerald-400">2. Packing List</div>
              <p className="text-[11px] text-slate-400 mt-1">Package counts, container references, and gross weights.</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 text-xs">
              <div className="font-semibold text-purple-400">3. Ocean Bill of Lading</div>
              <p className="text-[11px] text-slate-400 mt-1">Carrier B/L number, shipper, consignee, and port stamps.</p>
            </div>
          </div>
        </div>

        {/* Submit Bar */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
          <Link
            to="/shipments"
            className="px-4 py-2 text-sm font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white font-semibold text-sm rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-60 transition"
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Registering Consignment...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" />
                <span>Register Consignment & Proceed to Uploads</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
