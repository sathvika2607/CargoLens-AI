import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CustomsExportCenterPage } from '../pages/CustomsExportCenterPage'
import * as shipmentsApi from '../api/shipments'
import * as exportsApi from '../api/exports'

vi.mock('../api/shipments', () => ({
  listShipments: vi.fn(),
}))

vi.mock('../api/exports', () => ({
  exportShipmentCsv: vi.fn(),
}))

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

describe('CustomsExportCenterPage Component', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()

    vi.mocked(shipmentsApi.listShipments).mockResolvedValue({
      items: [
        {
          id: 'shp-exp-01',
          shipment_number: 'SHP-24816',
          client_name: 'Siemens Energy Global',
          origin_country: 'Germany',
          product_description: 'Gas Turbine Sensors',
          quantity: 350,
          unit_price: 145.0,
          currency: 'EUR',
          gross_weight_kg: 1120.0,
          status: 'VERIFIED',
          created_by: 'exec-1',
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
        {
          id: 'shp-exp-02',
          shipment_number: 'SHP-24817',
          client_name: 'Schneider Electric Pacific',
          origin_country: 'France',
          product_description: 'Low-Voltage Switchgear',
          quantity: 120,
          unit_price: 280.0,
          currency: 'EUR',
          gross_weight_kg: 1840.0,
          status: 'EXPORTED',
          created_by: 'exec-1',
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
      ],
      total: 2,
      page: 1,
      limit: 100,
      total_pages: 1,
    })
  })

  it('renders template selector, verified consignments, sealed declarations, and triggers export', async () => {
    vi.mocked(exportsApi.exportShipmentCsv).mockResolvedValue({
      filename: 'cargolens_export_SHP-24816.csv',
      checksum: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <CustomsExportCenterPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText('Customs Data Export & Audit Integrity Center')).toBeInTheDocument()
    expect(screen.getByText('Standard Customs Clearance (Single Consignment)')).toBeInTheDocument()
    expect(screen.getByText('Line Item Declaration (Detailed Commercial Invoice)')).toBeInTheDocument()

    // Verified shipment ready for export
    expect(await screen.findByText('SHP-24816')).toBeInTheDocument()
    expect(screen.getByText('Siemens Energy Global')).toBeInTheDocument()

    // Sealed declarations section shows SHP-24817
    expect(screen.getByText('SHP-24817')).toBeInTheDocument()
    expect(screen.getByText('Schneider Electric Pacific')).toBeInTheDocument()
    expect(screen.getByText('SHA-256 Validated')).toBeInTheDocument()

    // Trigger export
    const exportBtn = screen.getByRole('button', { name: /Export CSV/i })
    expect(exportBtn).toBeInTheDocument()
    fireEvent.click(exportBtn)

    await waitFor(() => {
      expect(exportsApi.exportShipmentCsv).toHaveBeenCalledWith(
        'shp-exp-01',
        'STANDARD_CUSTOMS_CLEARANCE'
      )
    })
  })
})
