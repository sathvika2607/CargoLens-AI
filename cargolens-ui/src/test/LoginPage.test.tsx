import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { LoginPage } from '../pages/LoginPage'
import * as AuthContext from '../context/AuthContext'

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

describe('LoginPage', () => {
  const mockLogin = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockLogin.mockResolvedValue(undefined)

    vi.mocked(AuthContext.useAuth).mockReturnValue({
      user: null,
      isAuthenticated: false,
      isManager: false,
      isExecutive: false,
      isLoading: false,
      login: mockLogin,
      logout: vi.fn(),
    })
  })

  it('renders the standard login form without exposing demo credentials', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    expect(screen.getByLabelText(/work email address/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()

    expect(screen.queryByText(/1-click demonstration logins/i)).not.toBeInTheDocument()
    expect(screen.queryByText('DemoExecutive2026!')).not.toBeInTheDocument()
    expect(screen.queryByText('DemoManager2026!')).not.toBeInTheDocument()
    expect(screen.queryByTestId('demo-executive-btn')).not.toBeInTheDocument()
    expect(screen.queryByTestId('demo-manager-btn')).not.toBeInTheDocument()
  })

  it('submits the entered credentials through the authentication context', async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/work email address/i), {
      target: { value: 'reviewer@cargolens.in' },
    })

    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'ReviewerSecure2026!' },
    })

    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith(
        'reviewer@cargolens.in',
        'ReviewerSecure2026!'
      )
    })
  })

  it("renders a clear Don't have an account? Register link navigating to /register", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    const registerLink = screen.getByRole('link', { name: /register/i })
    expect(registerLink).toBeInTheDocument()
    expect(registerLink).toHaveAttribute('href', '/register')
    expect(screen.getByText(/don't have an account\?/i)).toBeInTheDocument()
  })

  it('displays a success alert after successful registration', () => {
    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: '/login',
            state: {
              registered: true,
              email: 'newuser@cargolens.in',
              message: 'Account created successfully! Please sign in with your credentials.',
            },
          },
        ]}
      >
        <LoginPage />
      </MemoryRouter>
    )

    expect(screen.getByText(/registration successful:/i)).toBeInTheDocument()
    expect(
      screen.getByText(/account created successfully! please sign in with your credentials/i)
    ).toBeInTheDocument()

    const emailInput = screen.getByLabelText(/work email address/i) as HTMLInputElement
    expect(emailInput.value).toBe('newuser@cargolens.in')
  })
})