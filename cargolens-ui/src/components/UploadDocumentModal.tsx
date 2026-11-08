import React, { useState, useRef } from 'react'
import {
  X,
  UploadCloud,
  FileText,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from 'lucide-react'
import { DocumentType } from '../types/document'
import { uploadDocument } from '../api/documents'

interface UploadDocumentModalProps {
  shipmentId: string
  shipmentNumber: string
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

const DOCUMENT_TYPES: { value: DocumentType; label: string; description: string }[] = [
  {
    value: 'COMMERCIAL_INVOICE',
    label: 'Commercial Invoice',
    description: 'Valuation, seller/buyer particulars, currency, unit rates',
  },
  {
    value: 'PACKING_LIST',
    label: 'Packing List',
    description: 'Package breakdown, gross/net weights, container markings',
  },
  {
    value: 'BILL_OF_LADING',
    label: 'Bill of Lading',
    description: 'Carrier shipping note, port of loading/discharge, consignee',
  },
]

const MAX_FILE_SIZE = 25 * 1024 * 1024 // 25 MB

export const UploadDocumentModal: React.FC<UploadDocumentModalProps> = ({
  shipmentId,
  shipmentNumber,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [docType, setDocType] = useState<DocumentType>('COMMERCIAL_INVOICE')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  if (!isOpen) return null

  const resetForm = () => {
    setSelectedFile(null)
    setUploadProgress(null)
    setIsSubmitting(false)
    setError(null)
    setSuccess(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  const validateAndSetFile = (file: File) => {
    setError(null)
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    const allowed = ['.pdf', '.jpg', '.jpeg', '.png']
    if (!allowed.includes(ext)) {
      setError(`Unsupported file extension '${ext}'. Allowed formats: PDF, JPG, JPEG, PNG.`)
      return
    }
    if (file.size > MAX_FILE_SIZE) {
      setError(
        `File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds the maximum allowed limit of 25 MB.`
      )
      return
    }
    if (file.size === 0) {
      setError('The selected file is empty (0 bytes).')
      return
    }
    setSelectedFile(file)
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) {
      setError('Please select a document file to upload.')
      return
    }

    setError(null)
    setIsSubmitting(true)
    setUploadProgress(0)

    try {
      await uploadDocument(shipmentId, docType, selectedFile, (pct) => {
        setUploadProgress(pct)
      })
      setSuccess(true)
      setTimeout(() => {
        handleClose()
        onSuccess()
      }, 1000)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
      const status = axiosErr?.response?.status
      const detail = axiosErr?.response?.data?.detail
      if (status === 409) {
        setError(detail || 'This identical document has already been uploaded for this shipment.')
      } else if (status === 413) {
        setError('File size exceeds the 25 MB upload limit.')
      } else {
        setError(detail || 'Failed to upload document. Please verify format and network connection.')
      }
      setUploadProgress(null)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-brand-50 text-brand-600">
              <UploadCloud className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Upload Consignment Document</h3>
              <p className="text-xs text-slate-500 font-mono">Shipment: {shipmentNumber}</p>
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
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3.5 flex items-start gap-2.5 text-xs text-rose-800">
              <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}

          {success && (
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3.5 flex items-center gap-2.5 text-xs text-emerald-800 font-medium">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>Document uploaded successfully! Background ingestion job queued.</span>
            </div>
          )}

          {/* Document Type Selector */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              Document Classification *
            </label>
            <div className="space-y-2">
              {DOCUMENT_TYPES.map((type) => (
                <label
                  key={type.value}
                  className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                    docType === type.value
                      ? 'border-brand-500 bg-brand-50/40 ring-1 ring-brand-500'
                      : 'border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="document_type"
                    value={type.value}
                    checked={docType === type.value}
                    onChange={() => setDocType(type.value)}
                    className="mt-0.5 text-brand-600 focus:ring-brand-500"
                  />
                  <div>
                    <div className="text-xs font-bold text-slate-900">{type.label}</div>
                    <div className="text-[11px] text-slate-500">{type.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* File Dropzone */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              File Attachment (.pdf, .jpg, .jpeg, .png &le; 25 MB) *
            </label>
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors ${
                dragActive
                  ? 'border-brand-500 bg-brand-50/50'
                  : selectedFile
                  ? 'border-emerald-400 bg-emerald-50/30'
                  : 'border-slate-300 hover:border-slate-400 bg-slate-50/50'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
                className="hidden"
              />

              {selectedFile ? (
                <div className="flex items-center justify-center gap-3">
                  <div className="p-2 rounded-lg bg-emerald-100 text-emerald-700">
                    <FileText className="h-6 w-6" />
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-semibold text-slate-900 truncate max-w-xs">
                      {selectedFile.name}
                    </div>
                    <div className="text-xs text-slate-500 font-mono">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  <UploadCloud className="h-8 w-8 text-slate-400 mx-auto" />
                  <div className="text-xs font-semibold text-slate-700">
                    Click to browse or drag and drop document here
                  </div>
                  <p className="text-[11px] text-slate-500">
                    PDF, JPEG, or PNG up to 25 MB. Magic bytes validated.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Progress Bar */}
          {uploadProgress !== null && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-600 font-medium">
                <span>Uploading payload...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-brand-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Actions */}
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
              disabled={isSubmitting || !selectedFile}
              className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : (
                <span>Upload & Ingest</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
