import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { Sidebar } from '../components/layout/Sidebar'
import * as AuthContext from '../context/AuthContext'

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

describe('Sidebar Component', () => {
  it('renders brand, port hub indicator, and manager tier badge for manager user', () => {
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

    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    )

    expect(screen.getByText('CargoLens')).toBeInTheDocument()
    expect(screen.getByText('Nhava Sheva Port Hub')).toBeInTheDocument()
    expect(screen.getByText('Doc Manager')).toBeInTheDocument()
    expect(screen.getByText('Anita Roy')).toBeInTheDocument()
    expect(screen.getByText('manager@cargolens.local')).toBeInTheDocument()
    expect(screen.getByText('Operations Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Shipment Registry')).toBeInTheDocument()
    expect(screen.getByText('Document Review')).toBeInTheDocument()
    expect(screen.getByText('Validation Issues')).toBeInTheDocument()
    expect(screen.getByText('Audit & History')).toBeInTheDocument()
    expect(screen.getByText('Manager Command Deck')).toBeInTheDocument()
  })

  it('renders executive tier badge for executive user and omits manager-only links', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      user: {
        id: '456',
        email: 'executive@cargolens.local',
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

    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    )

    expect(screen.getByText('Doc Executive')).toBeInTheDocument()
    expect(screen.getByText('Rohan Sharma')).toBeInTheDocument()
    expect(screen.queryByText('Manager Command Deck')).not.toBeInTheDocument()
  })
})
