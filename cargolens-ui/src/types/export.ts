export interface ExportTemplateInfo {
  template_id: string
  name: string
  description: string
  columns: string[]
}

export interface ExportReadinessResponse {
  shipment_id: string
  shipment_number: string
  current_status: string
  is_verified: boolean
  all_mandatory_fields_reviewed: boolean
  has_blocking_failures: boolean
  is_ready_to_export: boolean
  missing_requirements: string[]
  available_templates: ExportTemplateInfo[]
}

export interface ShipmentExportRecord {
  id: string
  shipment_id: string
  exported_by: string
  exporter_name?: string
  exporter_email?: string
  template_name: string
  template_version: string
  filename: string
  sha256_checksum: string
  export_status: string
  row_count: number
  file_size_bytes: number
  error_message?: string
  exported_at: string
}

export interface ShipmentExportListResponse {
  items: ShipmentExportRecord[]
  total: number
}
