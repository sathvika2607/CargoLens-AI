import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { SettingsPage } from '../pages/SettingsPage'
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

describe('SettingsPage Component Health Indicators', () => {
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

  it('renders HEALTHY and ONLINE indicators when backend services return healthy', async () => {
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
          <SettingsPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('HEALTHY')).toBeInTheDocument()
    expect(await screen.findByText('ONLINE (Port 5432)')).toBeInTheDocument()
    expect(screen.getByText('Nhava Sheva (JNPT)')).toBeInTheDocument()
  })

  it('renders OFFLINE when services return unhealthy or unexpected status', async () => {
    vi.mocked(healthApi.fetchApiHealth).mockResolvedValue({
      status: 'ok', // Outdated/unexpected status value
      service: 'CargoLens AI API',
      environment: 'development',
      version: '0.1.0',
    })
    vi.mocked(healthApi.fetchDbHealth).mockResolvedValue({
      status: 'unhealthy',
      database: 'disconnected',
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <SettingsPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    const offlineBadges = await screen.findAllByText('OFFLINE')
    expect(offlineBadges.length).toBe(2) // Both API and DB show OFFLINE
  })
})
