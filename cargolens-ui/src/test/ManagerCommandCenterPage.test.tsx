import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ManagerCommandCenterPage } from '../pages/ManagerCommandCenterPage'
import * as shipmentsApi from '../api/shipments'
import * as dashboardApi from '../api/dashboard'
import * as AuthContext from '../context/AuthContext'

vi.mock('../api/shipments', () => ({
  listShipments: vi.fn(),
}))

vi.mock('../api/dashboard', () => ({
  fetchDashboardStats: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

describe('ManagerCommandCenterPage Component', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()

    vi.mocked(AuthContext.useAuth).mockReturnValue({
      user: {
        id: 'mgr-1',
        email: 'manager@cargolens.in',
        full_name: 'Anita Roy',
        role: 'DOCUMENTATION_MANAGER',
        is_active: true,
        created_at: '2026-01-01',
      },
      isAuthenticated: true,
      isManager: true,
      isExecutive: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })

    vi.mocked(shipmentsApi.listShipments).mockResolvedValue({
      items: [
        {
          id: 'shp-001',
          shipment_number: 'SHP-24811',
          client_name: 'Lumileds Global Trading',
          origin_country: 'China',
          product_description: 'LED panel lights',
          quantity: 2400,
          unit_price: 6.8,
          currency: 'USD',
          gross_weight_kg: 3120.0,
          status: 'REVIEW_REQUIRED',
          created_by: 'exec-1',
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
        {
          id: 'shp-002',
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
      ],
      total: 2,
      page: 1,
      limit: 100,
      total_pages: 1,
    })

    vi.mocked(dashboardApi.fetchDashboardStats).mockResolvedValue({} as any)
  })

  it('renders command deck KPIs, priority review queue, and port SLA tracker', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ManagerCommandCenterPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText('Manager Command Deck')).toBeInTheDocument()
    expect(screen.getByText('Clearance Operations & Verification Oversight')).toBeInTheDocument()
    expect(screen.getByText('Awaiting Human Review')).toBeInTheDocument()
    expect(screen.getByText('Verified & Export Ready')).toBeInTheDocument()

    // Priority queue table shows SHP-24811
    expect(await screen.findByText('SHP-24811')).toBeInTheDocument()
    expect(screen.getByText('Lumileds Global Trading')).toBeInTheDocument()

    // Port SLA
    expect(screen.getByText('Nhava Sheva Port Clearance SLA')).toBeInTheDocument()
    expect(screen.getByText('100% Deterministic')).toBeInTheDocument()
  })
})
