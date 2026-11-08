import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CreateShipmentPage } from '../pages/CreateShipmentPage'
import * as shipmentsApi from '../api/shipments'

vi.mock('../api/shipments', () => ({
  createShipment: vi.fn(),
}))

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

describe('CreateShipmentPage Component', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  it('renders all sections, inputs, and auto-generates a reference number', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <CreateShipmentPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText('Register New Import Consignment')).toBeInTheDocument()
    expect(screen.getByText('1. Consignment Identity & Parties')).toBeInTheDocument()
    expect(screen.getByText('2. Commodity Description & Valuation')).toBeInTheDocument()
    expect(screen.getByText('3. Physical Cargo & Weight Specification')).toBeInTheDocument()
    expect(screen.getByText('Next Step: Document Triad Ingestion')).toBeInTheDocument()

    // Test Auto-Generate button
    const autoGenBtn = screen.getByRole('button', { name: /Auto-Generate/i })
    expect(autoGenBtn).toBeInTheDocument()
    fireEvent.click(autoGenBtn)

    const refInput = screen.getByPlaceholderText('e.g. SHP-24818') as HTMLInputElement
    expect(refInput.value).toMatch(/^SHP-\d{5}$/)
  })

  it('validates mandatory fields and submits payload on completion', async () => {
    vi.mocked(shipmentsApi.createShipment).mockResolvedValue({
      id: 'shp-new-uuid-001',
      shipment_number: 'SHP-99123',
      client_name: 'Test Client India Ltd',
      origin_country: 'Germany',
      product_description: 'Industrial ball valves',
      quantity: 180,
      unit_price: 42.5,
      currency: 'EUR',
      gross_weight_kg: 1460.0,
      status: 'CREATED',
      created_by: 'user-01',
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <CreateShipmentPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    const refInput = screen.getByPlaceholderText('e.g. SHP-24818')
    const clientInput = screen.getByPlaceholderText('e.g. Schneider Electric India Pvt Ltd')
    const submitBtn = screen.getByRole('button', { name: /Register Consignment & Proceed to Uploads/i })

    // Fill form
    fireEvent.change(refInput, { target: { value: 'SHP-99123' } })
    fireEvent.change(clientInput, { target: { value: 'Test Client India Ltd' } })

    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(shipmentsApi.createShipment).toHaveBeenCalledWith(
        expect.objectContaining({
          shipment_number: 'SHP-99123',
          client_name: 'Test Client India Ltd',
          origin_country: 'China',
        })
      )
    })
  })
})
