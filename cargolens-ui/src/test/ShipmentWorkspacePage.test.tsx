import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ShipmentWorkspacePage } from '../pages/ShipmentWorkspacePage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as shipmentsApi from '../api/shipments'
import * as documentsApi from '../api/documents'
import * as validationsApi from '../api/validations'
import * as reviewsApi from '../api/reviews'
import * as workflowApi from '../api/workflow'
import * as exportsApi from '../api/exports'

vi.mock('../api/shipments', () => ({
  getShipment: vi.fn(),
}))

vi.mock('../api/documents', () => ({
  listDocuments: vi.fn(),
}))

vi.mock('../api/validations', () => ({
  getShipmentValidations: vi.fn(),
  runShipmentValidations: vi.fn(),
}))

vi.mock('../api/reviews', () => ({
  fetchShipmentReviewHistory: vi.fn(),
  fetchShipmentReviews: vi.fn(),
  submitFieldReview: vi.fn(),
}))

vi.mock('../api/workflow', () => ({
  fetchVerificationReadiness: vi.fn(),
  verifyShipment: vi.fn(),
}))

vi.mock('../api/exports', () => ({
  fetchExportReadiness: vi.fn(),
  exportShipmentCsv: vi.fn(),
  fetchShipmentExports: vi.fn(),
  downloadExportSnapshot: vi.fn(),
}))

vi.mock('../api/structuredExtractions', () => ({
  getLatestStructuredExtraction: vi.fn(),
}))

describe('ShipmentWorkspacePage Component', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    vi.clearAllMocks()

    vi.mocked(shipmentsApi.getShipment).mockResolvedValue({
      id: 'shp-workspace-01',
      shipment_number: 'SHP-2026-9999',
      client_name: 'Nhava Sheva Freight Forwarders Ltd',
      origin_country: 'Germany',
      product_description: 'Precision Industrial Valves',
      quantity: 500,
      unit_price: 120.00,
      currency: 'EUR',
      gross_weight_kg: 2500.5,
      status: 'REVIEW_REQUIRED',
      created_at: '2026-01-01',
      created_by: 'u-1',
      updated_at: '2026-01-01',
    })

    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [
        {
          id: 'doc-1',
          shipment_id: 'shp-workspace-01',
          document_type: 'COMMERCIAL_INVOICE',
          original_filename: 'Commercial_Invoice.pdf',
          mime_type: 'application/pdf',
          file_extension: 'pdf',
          file_size_bytes: 2048,
          sha256_checksum: 'checksum1',
          version: 1,
          uploaded_by: 'u-1',
          processing_status: 'COMPLETED',
          is_active: true,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
        {
          id: 'doc-2',
          shipment_id: 'shp-workspace-01',
          document_type: 'PACKING_LIST',
          original_filename: 'Packing_List.pdf',
          mime_type: 'application/pdf',
          file_extension: 'pdf',
          file_size_bytes: 1024,
          sha256_checksum: 'checksum2',
          version: 1,
          uploaded_by: 'u-1',
          processing_status: 'COMPLETED',
          is_active: true,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
        {
          id: 'doc-3',
          shipment_id: 'shp-workspace-01',
          document_type: 'BILL_OF_LADING',
          original_filename: 'Bill_Of_Lading.pdf',
          mime_type: 'application/pdf',
          file_extension: 'pdf',
          file_size_bytes: 1500,
          sha256_checksum: 'checksum3',
          version: 1,
          uploaded_by: 'u-1',
          processing_status: 'COMPLETED',
          is_active: true,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
      ],
      total: 3,
    })

    vi.mocked(workflowApi.fetchVerificationReadiness).mockResolvedValue({
      shipment_id: 'shp-workspace-01',
      current_status: 'REVIEW_REQUIRED',
      is_ready: true,
      all_documents_present: true,
      documents_missing: [],
      documents_present: {
        COMMERCIAL_INVOICE: true,
        PACKING_LIST: true,
        BILL_OF_LADING: true,
      },
      all_extractions_completed: true,
      blocking_validation_failures_count: 0,
      has_blocking_failures: false,
      human_reviews_count: 5,
      missing_requirements: [],
    })

    vi.mocked(validationsApi.getShipmentValidations).mockResolvedValue({
      shipment_id: 'shp-workspace-01',
      run_id: 'run-1',
      total_rules: 8,
      passed_count: 8,
      failed_count: 0,
      missing_data_count: 0,
      not_applicable_count: 0,
      info_count: 0,
      has_blocking_failures: false,
      results: [],
    })

    vi.mocked(reviewsApi.fetchShipmentReviewHistory).mockResolvedValue({
      items: [],
      total: 0,
    })

    vi.mocked(reviewsApi.fetchShipmentReviews).mockResolvedValue({
      items: [],
      total: 0,
    })

    vi.mocked(exportsApi.fetchExportReadiness).mockResolvedValue({
      shipment_id: 'shp-workspace-01',
      shipment_number: 'SHP-2026-9999',
      current_status: 'VERIFIED',
      is_verified: true,
      all_mandatory_fields_reviewed: true,
      has_blocking_failures: false,
      is_ready_to_export: true,
      missing_requirements: [],
      available_templates: [
        {
          template_id: 'STANDARD_CUSTOMS_CLEARANCE',
          name: 'Standard Customs Clearance',
          description: 'Single Consignment',
          columns: ['Shipment Reference', 'Commercial Invoice Number'],
        },
      ],
    })

    vi.mocked(exportsApi.fetchShipmentExports).mockResolvedValue({
      items: [
        {
          id: 'exp-1',
          shipment_id: 'shp-workspace-01',
          exported_by: 'u-1',
          exporter_name: 'Rajesh Sharma',
          exporter_email: 'rajesh@cargolens.in',
          template_name: 'STANDARD_CUSTOMS_CLEARANCE',
          template_version: '1.0',
          filename: 'cargolens_export_SHP-2026-9999.csv',
          sha256_checksum: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
          export_status: 'COMPLETED',
          row_count: 1,
          file_size_bytes: 512,
          exported_at: '2026-04-10T12:00:00Z',
        },
      ],
      total: 1,
    })
  })

  it('renders workspace tabs and triggers verification workflow action', async () => {
    vi.mocked(workflowApi.verifyShipment).mockResolvedValue({
      success: true,
      message: 'Shipment verified',
      shipment: {
        id: 'shp-workspace-01',
        shipment_number: 'SHP-2026-9999',
        client_name: 'Nhava Sheva Freight Forwarders Ltd',
        origin_country: 'Germany',
        product_description: 'Precision Industrial Valves',
        quantity: 500,
        unit_price: 120.00,
        currency: 'EUR',
        gross_weight_kg: 2500.5,
        status: 'VERIFIED',
        created_at: '2026-01-01',
        created_by: 'u-1',
        updated_at: '2026-01-01',
      },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/shipments/shp-workspace-01']}>
          <Routes>
            <Route path="/shipments/:id" element={<ShipmentWorkspacePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    // Check workspace header
    expect(await screen.findByText('SHP-2026-9999')).toBeInTheDocument()
    expect(screen.getByText('Ready for Verification')).toBeInTheDocument()
    expect(screen.getByText('Consignment Overview')).toBeInTheDocument()
    expect(screen.getByText('Documents (3)')).toBeInTheDocument()
    expect(screen.getByText('Validation Issues (0)')).toBeInTheDocument()

    // Test clicking Verify Consignment button
    const verifyBtn = screen.getByRole('button', { name: /Verify Consignment/i })
    expect(verifyBtn).toBeEnabled()
    fireEvent.click(verifyBtn)

    await waitFor(() => {
      expect(workflowApi.verifyShipment).toHaveBeenCalledWith('shp-workspace-01')
    })
  })

  it('renders customs export tab, export readiness checklist and triggers CSV export', async () => {
    vi.mocked(exportsApi.exportShipmentCsv).mockResolvedValue({
      filename: 'cargolens_export_SHP-2026-9999.csv',
      checksum: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/shipments/shp-workspace-01']}>
          <Routes>
            <Route path="/shipments/:id" element={<ShipmentWorkspacePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    // Navigate to Customs Export tab
    const exportTabBtn = await screen.findByRole('button', { name: /Customs Export/i })
    expect(exportTabBtn).toBeInTheDocument()
    fireEvent.click(exportTabBtn)

    // Check readiness checklist elements
    expect(await screen.findByText('Customs Declaration Export Readiness')).toBeInTheDocument()
    expect(screen.getByText('READY FOR EXPORT')).toBeInTheDocument()
    expect(screen.getByText('1. Consignment Verification')).toBeInTheDocument()
    expect(screen.getByText('2. Mandatory Field Reviews')).toBeInTheDocument()
    expect(screen.getByText('3. Discrepancy Integrity')).toBeInTheDocument()

    // Check Export history table rendered past snapshot
    expect(screen.getByText('cargolens_export_SHP-2026-9999.csv')).toBeInTheDocument()
    expect(screen.getByText('Rajesh Sharma')).toBeInTheDocument()

    // Click Generate & Download Verified CSV
    const exportBtn = screen.getByRole('button', { name: /Generate & Download Verified CSV/i })
    expect(exportBtn).toBeEnabled()
    fireEvent.click(exportBtn)

    await waitFor(() => {
      expect(exportsApi.exportShipmentCsv).toHaveBeenCalledWith(
        'shp-workspace-01',
        'STANDARD_CUSTOMS_CLEARANCE'
      )
    })
  })
})
