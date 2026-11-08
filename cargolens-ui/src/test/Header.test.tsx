import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { Header } from '../components/layout/Header'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as AuthContext from '../context/AuthContext'
import * as healthApi from '../api/health'

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../api/health', () => ({
  fetchApiHealth: vi.fn(),
  fetchDbHealth: vi.fn(),
}))

describe('Header Component', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    vi.clearAllMocks()

    vi.mocked(AuthContext.useAuth).mockReturnValue({
      user: {
        id: '123',
        email: 'manager@cargolens.local',
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
  })

  it('renders dynamic breadcrumbs and operational connectivity badge when both services return healthy', async () => {
    vi.mocked(healthApi.fetchApiHealth).mockResolvedValue({
      status: 'healthy',
      service: 'CargoLens AI API',
      environment: 'development',
      version: '0.1.0',
    })
    vi.mocked(healthApi.fetchDbHealth).mockResolvedValue({
      status: 'healthy',
      database: 'connected',
      dialect: 'postgresql',
      latency_ms: 1.85,
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/shipments/SHP-2026-001']}>
          <Header />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText('Shipments')).toBeInTheDocument()
    expect(screen.getByText('Shipment #SHP-2026-001')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Search shipment number...')).toBeInTheDocument()
    expect(screen.getByText('Anita Roy')).toBeInTheDocument()
    expect(screen.getByText('Documentation Manager')).toBeInTheDocument()

    // Both indicators show operational OK
    expect(await screen.findByText('API: OK • DB: OK')).toBeInTheDocument()
    expect(screen.getByTitle('Services Operational')).toBeInTheDocument()
  })

  it('displays operational status for healthy API', async () => {
    vi.mocked(healthApi.fetchApiHealth).mockResolvedValue({
      status: 'healthy',
      service: 'CargoLens AI API',
      environment: 'development',
      version: '0.1.0',
    })
    vi.mocked(healthApi.fetchDbHealth).mockResolvedValue({
      status: 'healthy',
      database: 'connected',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Header />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText(/API: OK/)).toBeInTheDocument()
  })

  it('displays operational status for healthy database', async () => {
    vi.mocked(healthApi.fetchApiHealth).mockResolvedValue({
      status: 'healthy',
      service: 'CargoLens AI API',
      environment: 'development',
      version: '0.1.0',
    })
    vi.mocked(healthApi.fetchDbHealth).mockResolvedValue({
      status: 'healthy',
      database: 'connected',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Header />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText(/DB: OK/)).toBeInTheDocument()
  })

  it('displays unhealthy status (ERR) when API request fails', async () => {
    vi.mocked(healthApi.fetchApiHealth).mockRejectedValue(new Error('Network connection timeout'))
    vi.mocked(healthApi.fetchDbHealth).mockResolvedValue({
      status: 'healthy',
      database: 'connected',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Header />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('API: ERR • DB: OK')).toBeInTheDocument()
    expect(screen.getByTitle('Degraded Connectivity')).toBeInTheDocument()
  })

  it('displays unhealthy status (ERR) when database request fails', async () => {
    vi.mocked(healthApi.fetchApiHealth).mockResolvedValue({
      status: 'healthy',
      service: 'CargoLens AI API',
      environment: 'development',
      version: '0.1.0',
    })
    vi.mocked(healthApi.fetchDbHealth).mockRejectedValue(new Error('PostgreSQL connection refused'))

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Header />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('API: OK • DB: ERR')).toBeInTheDocument()
    expect(screen.getByTitle('Degraded Connectivity')).toBeInTheDocument()
  })

  it('does not treat unexpected status values like "ok" or "degraded" as healthy', async () => {
    // Backend contract requires "healthy"; legacy or unexpected "ok" must NOT be treated as healthy
    vi.mocked(healthApi.fetchApiHealth).mockResolvedValue({
      status: 'ok',
      service: 'CargoLens AI API',
      environment: 'development',
      version: '0.1.0',
    })
    vi.mocked(healthApi.fetchDbHealth).mockResolvedValue({
      status: 'ok',
      database: 'connected',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Header />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('API: ERR • DB: ERR')).toBeInTheDocument()
    expect(screen.getByTitle('Degraded Connectivity')).toBeInTheDocument()
  })

  it('does not treat disconnected database as healthy even if status string says healthy', async () => {
    vi.mocked(healthApi.fetchApiHealth).mockResolvedValue({
      status: 'healthy',
      service: 'CargoLens AI API',
      environment: 'development',
      version: '0.1.0',
    })
    vi.mocked(healthApi.fetchDbHealth).mockResolvedValue({
      status: 'healthy',
      database: 'disconnected',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Header />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('API: OK • DB: ERR')).toBeInTheDocument()
    expect(screen.getByTitle('Degraded Connectivity')).toBeInTheDocument()
  })
})
