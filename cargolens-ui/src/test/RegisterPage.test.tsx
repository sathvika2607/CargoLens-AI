import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { RegisterPage } from '../pages/RegisterPage'
import * as authApi from '../api/auth'

vi.mock('../api/auth', () => ({
  register: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('RegisterPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders all required form fields, headers, and default executive role badge', () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    // Verify Title & Role Badge
    expect(screen.getByText('Create Corporate Account')).toBeInTheDocument()
    expect(screen.getByText(/Role: Documentation Executive/i)).toBeInTheDocument()

    // Required Inputs
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/work email address/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password/i, { selector: 'input' })).toBeInTheDocument()
    expect(screen.getByLabelText(/^confirm password/i, { selector: 'input' })).toBeInTheDocument()

    // Submit Button
    expect(
      screen.getByRole('button', { name: /complete executive registration/i })
    ).toBeInTheDocument()

    // Login Navigation Link
    const loginLink = screen.getByRole('link', { name: /login/i })
    expect(loginLink).toBeInTheDocument()
    expect(loginLink).toHaveAttribute('href', '/login')
  })

  it('toggles password and confirm password visibility', () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    const passwordInput = screen.getByLabelText(/^password/i, { selector: 'input' }) as HTMLInputElement
    const confirmInput = screen.getByLabelText(/^confirm password/i, { selector: 'input' }) as HTMLInputElement
    const togglePwBtn = screen.getByTestId('toggle-password-visibility')
    const toggleConfirmBtn = screen.getByTestId('toggle-confirm-password-visibility')

    // Initial state: password type
    expect(passwordInput.type).toBe('password')
    expect(confirmInput.type).toBe('password')

    // Toggle password to text
    fireEvent.click(togglePwBtn)
    expect(passwordInput.type).toBe('text')
    fireEvent.click(togglePwBtn)
    expect(passwordInput.type).toBe('password')

    // Toggle confirm password to text
    fireEvent.click(toggleConfirmBtn)
    expect(confirmInput.type).toBe('text')
    fireEvent.click(toggleConfirmBtn)
    expect(confirmInput.type).toBe('password')
  })

  it('validates required fields on empty submission', async () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    const submitBtn = screen.getByRole('button', { name: /complete executive registration/i })
    fireEvent.click(submitBtn)

    expect(screen.getByText('Full Name is required.')).toBeInTheDocument()
    expect(screen.getByText('Work email address is required.')).toBeInTheDocument()
    expect(screen.getByText('Password is required.')).toBeInTheDocument()
    expect(screen.getByText('Confirm Password is required.')).toBeInTheDocument()
    expect(authApi.register).not.toHaveBeenCalled()
  })

  it('validates invalid email format', async () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Arun Kumar' } })
    fireEvent.change(screen.getByLabelText(/work email address/i), { target: { value: 'not-an-email' } })
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'ValidPass123!' } })
    fireEvent.change(screen.getByLabelText(/^confirm password/i, { selector: 'input' }), { target: { value: 'ValidPass123!' } })

    fireEvent.click(screen.getByRole('button', { name: /complete executive registration/i }))

    expect(
      screen.getByText(/please provide a valid work email format/i)
    ).toBeInTheDocument()
    expect(authApi.register).not.toHaveBeenCalled()
  })

  it('validates password complexity requirements', async () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Arun Kumar' } })
    fireEvent.change(screen.getByLabelText(/work email address/i), { target: { value: 'arun@cargolens.in' } })
    // Missing special character and uppercase
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'simple123' } })
    fireEvent.change(screen.getByLabelText(/^confirm password/i, { selector: 'input' }), { target: { value: 'simple123' } })

    fireEvent.click(screen.getByRole('button', { name: /complete executive registration/i }))

    expect(
      screen.getByText(/password must meet all complexity requirements below/i)
    ).toBeInTheDocument()
    expect(authApi.register).not.toHaveBeenCalled()
  })

  it('validates password and confirm password mismatch', async () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Arun Kumar' } })
    fireEvent.change(screen.getByLabelText(/work email address/i), { target: { value: 'arun@cargolens.in' } })
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'ComplexPass2026!' } })
    fireEvent.change(screen.getByLabelText(/^confirm password/i, { selector: 'input' }), { target: { value: 'DifferentPass2026!' } })

    fireEvent.click(screen.getByRole('button', { name: /complete executive registration/i }))

    expect(
      screen.getByText('Confirm Password must match Password.')
    ).toBeInTheDocument()
    expect(authApi.register).not.toHaveBeenCalled()
  })

  it('displays API error when registering duplicate email (409 Conflict)', async () => {
    vi.mocked(authApi.register).mockRejectedValueOnce({
      response: {
        status: 409,
        data: { detail: "A user with email 'arun@cargolens.in' already exists" },
      },
    })

    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Arun Kumar' } })
    fireEvent.change(screen.getByLabelText(/work email address/i), { target: { value: 'arun@cargolens.in' } })
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'ComplexPass2026!' } })
    fireEvent.change(screen.getByLabelText(/^confirm password/i, { selector: 'input' }), { target: { value: 'ComplexPass2026!' } })

    fireEvent.click(screen.getByRole('button', { name: /complete executive registration/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/a user with this work email already exists/i)
      ).toBeInTheDocument()
    })
  })

  it('successfully registers and redirects to login with success state', async () => {
    vi.mocked(authApi.register).mockResolvedValueOnce({
      id: 'mock-user-uuid',
      full_name: 'Priya Nair',
      email: 'priya.nair@cargolens.in',
      role: 'DOCUMENTATION_EXECUTIVE',
      is_active: true,
      created_at: new Date().toISOString(),
    })

    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Priya Nair' } })
    fireEvent.change(screen.getByLabelText(/work email address/i), { target: { value: 'priya.nair@cargolens.in' } })
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'ExecutiveSecret2026!' } })
    fireEvent.change(screen.getByLabelText(/^confirm password/i, { selector: 'input' }), { target: { value: 'ExecutiveSecret2026!' } })

    fireEvent.click(screen.getByRole('button', { name: /complete executive registration/i }))

    await waitFor(() => {
      expect(authApi.register).toHaveBeenCalledWith({
        full_name: 'Priya Nair',
        email: 'priya.nair@cargolens.in',
        password: 'ExecutiveSecret2026!',
        confirm_password: 'ExecutiveSecret2026!',
      })
      expect(
        screen.getByText(/registration successful! your documentation executive account has been activated/i)
      ).toBeInTheDocument()
    })

    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/login', {
          replace: true,
          state: {
            registered: true,
            email: 'priya.nair@cargolens.in',
            message: 'Account created successfully! Please sign in with your credentials.',
          },
        })
      },
      { timeout: 2000 }
    )
  })
})
