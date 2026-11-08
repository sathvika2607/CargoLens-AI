import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DashboardPage } from '../pages/DashboardPage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as AuthContext from '../context/AuthContext'
import * as dashboardApi from '../api/dashboard'

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../api/dashboard', () => ({
  fetchDashboardStats: vi.fn(),
}))

describe('DashboardPage Component', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    vi.clearAllMocks()
  })

  it('renders manager dashboard with port metrics and breakdown', async () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      user: {
        id: '1',
        email: 'mgr@cargolens.local',
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

    vi.mocked(dashboardApi.fetchDashboardStats).mockResolvedValue({
      role: 'DOCUMENTATION_MANAGER',
      manager: {
        total_shipments_count: 42,
        documents_awaiting_review_count: 5,
        validation_failures_count: 3,
        processing_failures_count: 1,
        shipments_by_status: {
          CREATED: 10,
          DOCUMENTS_PENDING: 8,
          PROCESSING: 4,
          REVIEW_REQUIRED: 5,
          VERIFIED: 12,
          EXPORTED: 3,
          FAILED: 0,
        },
        recent_shipments: [
          {
            id: 's-1',
            shipment_number: 'SHP-JNPT-001',
            client_name: 'Adani Ports Logistics',
            origin_country: 'Germany',
            product_description: 'Industrial Equipment',
            quantity: 100,
            unit_price: 250,
            currency: 'USD',
            gross_weight_kg: 1500,
            status: 'REVIEW_REQUIRED',
            created_at: '2026-01-01',
            created_by: 'u-1',
            updated_at: '2026-01-01',
          },
        ],
        recent_activity: [
          {
            id: 'a-1',
            action_type: 'VALIDATION_RUN',
            description: 'Validation failed on Invoice vs Packing List weights',
            actor_name: 'System Worker',
            shipment_number: 'SHP-JNPT-001',
            created_at: new Date().toISOString(),
          },
        ],
      },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('Port Oversight Dashboard')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getAllByText('SHP-JNPT-001').length).toBeGreaterThan(0)
    expect(screen.getByText('Adani Ports Logistics')).toBeInTheDocument()
    expect(screen.getByText('Validation Executed')).toBeInTheDocument()
  })

  it('renders executive dashboard with personal metrics', async () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      user: {
        id: '2',
        email: 'exec@cargolens.local',
        full_name: 'Rohan Sharma',
        role: 'DOCUMENTATION_EXECUTIVE',
        is_active: true,
        created_at: '2026-01-01',
      },
      isAuthenticated: true,
      isManager: false,
      isExecutive: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })

    vi.mocked(dashboardApi.fetchDashboardStats).mockResolvedValue({
      role: 'DOCUMENTATION_EXECUTIVE',
      executive: {
        my_shipments_count: 14,
        documents_uploaded_count: 28,
        processing_in_progress_count: 2,
        documents_awaiting_review_count: 4,
        validation_failures_count: 1,
        recent_shipments: [],
        recent_activity: [],
      },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('Documentation Operations Dashboard')).toBeInTheDocument()
    expect(screen.getByText('My Shipments')).toBeInTheDocument()
    expect(screen.getByText('14')).toBeInTheDocument()
    expect(screen.getByText('Uploaded Docs')).toBeInTheDocument()
    expect(screen.getByText('28')).toBeInTheDocument()
  })
})
