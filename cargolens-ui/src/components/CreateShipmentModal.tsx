import React, { useState } from 'react'
import { X, AlertCircle, Loader2, PlusCircle } from 'lucide-react'
import { ShipmentCreatePayload } from '../types/shipment'
import { createShipment } from '../api/shipments'

interface CreateShipmentModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export const CreateShipmentModal: React.FC<CreateShipmentModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [shipmentNumber, setShipmentNumber] = useState('')
  const [clientName, setClientName] = useState('')
  const [originCountry, setOriginCountry] = useState('')
  const [productDescription, setProductDescription] = useState('')
  const [quantity, setQuantity] = useState<string>('')
  const [unitPrice, setUnitPrice] = useState<string>('')
  const [currency, setCurrency] = useState('')
  const [grossWeightKg, setGrossWeightKg] = useState<string>('')

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isOpen) return null

  const resetForm = () => {
    setShipmentNumber('')
    setClientName('')
    setOriginCountry('')
    setProductDescription('')
    setQuantity('')
    setUnitPrice('')
    setCurrency('')
    setGrossWeightKg('')
    setError(null)
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const trimmedNumber = shipmentNumber.trim().toUpperCase()
    const trimmedClient = clientName.trim()
    const trimmedOrigin = originCountry.trim()

    // Validations
    if (!trimmedNumber) {
      setError('Shipment identifier is required (e.g. SHP-2026-001).')
      return
    }
    if (!/^[A-Za-z0-9_-]+$/.test(trimmedNumber)) {
      setError('Shipment number may only contain letters, numbers, hyphens, and underscores.')
      return
    }
    if (!trimmedClient) {
      setError('Client or consignee name is required.')
      return
    }
    if (!trimmedOrigin) {
      setError('Origin country is required.')
      return
    }

    const payload: ShipmentCreatePayload = {
      shipment_number: trimmedNumber,
      client_name: trimmedClient,
      origin_country: trimmedOrigin,
      product_description: productDescription.trim() || undefined,
      currency: currency.trim() ? currency.trim().toUpperCase() : undefined,
    }

    if (quantity !== '') {
      const qVal = parseFloat(quantity)
      if (isNaN(qVal) || qVal < 0) {
        setError('Quantity must be a non-negative number.')
        return
      }
      payload.quantity = qVal
    }

    if (unitPrice !== '') {
      const pVal = parseFloat(unitPrice)
      if (isNaN(pVal) || pVal < 0) {
        setError('Unit price must be a non-negative number.')
        return
      }
      payload.unit_price = pVal
    }

    if (grossWeightKg !== '') {
      const wVal = parseFloat(grossWeightKg)
      if (isNaN(wVal) || wVal < 0) {
        setError('Gross weight must be a non-negative number.')
        return
      }
      payload.gross_weight_kg = wVal
    }

    setIsSubmitting(true)
    try {
      await createShipment(payload)
      handleClose()
      onSuccess()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
      if (axiosErr?.response?.status === 409) {
        setError(`A shipment with number "${trimmedNumber}" already exists in the registry.`)
      } else {
        const detail = axiosErr?.response?.data?.detail
        setError(typeof detail === 'string' ? detail : 'Failed to register shipment. Check input fields.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-brand-50 text-brand-600">
              <PlusCircle className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Create Import Shipment</h3>
              <p className="text-xs text-slate-500">Register new consignment for Nhava Sheva customs review</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3.5 flex items-start gap-2.5 text-xs text-rose-800">
              <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Shipment Reference No. *
              </label>
              <input
                type="text"
                required
                value={shipmentNumber}
                onChange={(e) => setShipmentNumber(e.target.value)}
                placeholder="e.g. SHP-24811"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 uppercase font-mono placeholder:normal-case placeholder:font-sans"
              />
              <span className="text-[11px] text-slate-500">Unique identifier, alphanumeric/dash</span>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Client / Consignee *
              </label>
              <input
                type="text"
                required
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="e.g. Acme Industrial Corp Ltd"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Origin Country *
              </label>
              <input
                type="text"
                required
                value={originCountry}
                onChange={(e) => setOriginCountry(e.target.value)}
                placeholder="e.g. United Arab Emirates"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Declared Gross Weight (KG)
              </label>
              <input
                type="number"
                step="0.001"
                min="0"
                value={grossWeightKg}
                onChange={(e) => setGrossWeightKg(e.target.value)}
                placeholder="e.g. 14500.5"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
              Product Description / Commodity
            </label>
            <textarea
              rows={2}
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="e.g. Heavy machinery ball bearings (HSN 8482.10)"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Quantity
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="e.g. 500"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Unit Price
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                placeholder="e.g. 120.00"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 font-medium"
              >
                <option value="">Not Specified (NULL)</option>
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
                <option value="INR">INR (₹)</option>
                <option value="AED">AED (د.إ)</option>
                <option value="GBP">GBP (£)</option>
                <option value="SGD">SGD (S$)</option>
                <option value="JPY">JPY (¥)</option>
              </select>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm disabled:opacity-60 transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Registering...</span>
                </>
              ) : (
                <span>Register Shipment</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
