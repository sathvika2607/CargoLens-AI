import React, { useState, useEffect } from 'react'
import { X, AlertCircle, Loader2, Edit3 } from 'lucide-react'
import { Shipment, ShipmentUpdatePayload, ShipmentStatus } from '../types/shipment'
import { updateShipment } from '../api/shipments'

interface EditShipmentModalProps {
  shipment: Shipment | null
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

const STATUS_OPTIONS: { value: ShipmentStatus; label: string; isWorkflowOnly?: boolean }[] = [
  { value: 'CREATED', label: 'Created' },
  { value: 'DOCUMENTS_PENDING', label: 'Documents Pending' },
  { value: 'PROCESSING', label: 'Processing' },
  { value: 'REVIEW_REQUIRED', label: 'Review Required' },
  { value: 'VERIFIED', label: 'Verified (Workflow Automated)', isWorkflowOnly: true },
  { value: 'EXPORTED', label: 'Exported (Workflow Automated)', isWorkflowOnly: true },
  { value: 'FAILED', label: 'Failed' },
]

export const EditShipmentModal: React.FC<EditShipmentModalProps> = ({
  shipment,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [clientName, setClientName] = useState('')
  const [originCountry, setOriginCountry] = useState('')
  const [productDescription, setProductDescription] = useState('')
  const [quantity, setQuantity] = useState<string>('')
  const [unitPrice, setUnitPrice] = useState<string>('')
  const [currency, setCurrency] = useState('')
  const [grossWeightKg, setGrossWeightKg] = useState<string>('')
  const [status, setStatus] = useState<ShipmentStatus>('CREATED')

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (shipment) {
      setClientName(shipment.client_name || '')
      setOriginCountry(shipment.origin_country || '')
      setProductDescription(shipment.product_description || '')
      setQuantity(shipment.quantity !== null && shipment.quantity !== undefined ? String(shipment.quantity) : '')
      setUnitPrice(shipment.unit_price !== null && shipment.unit_price !== undefined ? String(shipment.unit_price) : '')
      setCurrency(shipment.currency || '')
      setGrossWeightKg(shipment.gross_weight_kg !== null && shipment.gross_weight_kg !== undefined ? String(shipment.gross_weight_kg) : '')
      setStatus(shipment.status)
      setError(null)
    }
  }, [shipment])

  if (!isOpen || !shipment) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const trimmedClient = clientName.trim()
    const trimmedOrigin = originCountry.trim()

    if (!trimmedClient) {
      setError('Client or consignee name cannot be empty.')
      return
    }
    if (!trimmedOrigin) {
      setError('Origin country cannot be empty.')
      return
    }

    const payload: ShipmentUpdatePayload = {
      client_name: trimmedClient,
      origin_country: trimmedOrigin,
      product_description: productDescription.trim() || undefined,
      currency: currency.trim() ? currency.trim().toUpperCase() : undefined,
      status: status,
    }

    if (quantity !== '') {
      const qVal = parseFloat(quantity)
      if (isNaN(qVal) || qVal < 0) {
        setError('Quantity must be a non-negative number.')
        return
      }
      payload.quantity = qVal
    } else {
      payload.quantity = undefined
    }

    if (unitPrice !== '') {
      const pVal = parseFloat(unitPrice)
      if (isNaN(pVal) || pVal < 0) {
        setError('Unit price must be a non-negative number.')
        return
      }
      payload.unit_price = pVal
    } else {
      payload.unit_price = undefined
    }

    if (grossWeightKg !== '') {
      const wVal = parseFloat(grossWeightKg)
      if (isNaN(wVal) || wVal < 0) {
        setError('Gross weight must be a non-negative number.')
        return
      }
      payload.gross_weight_kg = wVal
    } else {
      payload.gross_weight_kg = undefined
    }

    setIsSubmitting(true)
    try {
      await updateShipment(shipment.id, payload)
      onClose()
      onSuccess()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      const detail = axiosErr?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to update shipment records.')
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
            <div className="p-2 rounded-lg bg-amber-50 text-amber-600">
              <Edit3 className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Edit Shipment: <span className="font-mono text-brand-600">{shipment.shipment_number}</span>
              </h3>
              <p className="text-xs text-slate-500">Update consignment details and customs verification lifecycle</p>
            </div>
          </div>
          <button
            onClick={onClose}
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
                Shipment Reference No.
              </label>
              <input
                type="text"
                disabled
                value={shipment.shipment_number}
                className="w-full px-3 py-2 text-sm bg-slate-100 border border-slate-200 rounded-lg text-slate-500 font-mono cursor-not-allowed"
              />
              <span className="text-[11px] text-slate-400">Reference identifier is immutable</span>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Lifecycle Status
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as ShipmentStatus)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 font-semibold"
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option
                    key={opt.value}
                    value={opt.value}
                    disabled={opt.isWorkflowOnly}
                  >
                    {opt.label}{opt.isWorkflowOnly ? ' (Automated Pipeline Only)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Client / Consignee *
              </label>
              <input
                type="text"
                required
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Origin Country *
              </label>
              <input
                type="text"
                required
                value={originCountry}
                onChange={(e) => setOriginCountry(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900"
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
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-slate-900 font-mono"
            />
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
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
                  <span>Saving...</span>
                </>
              ) : (
                <span>Save Changes</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
