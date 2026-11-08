import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Anchor,
  Lock,
  Mail,
  User as UserIcon,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Sparkles,
  Check,
  FileCheck2,
  ShieldAlert,
} from 'lucide-react'
import { register } from '../api/auth'

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const [fieldErrors, setFieldErrors] = useState<{ [key: string]: string }>({})
  const [apiError, setApiError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Password complexity checks
  const hasMinLength = password.length >= 8
  const hasUppercase = /[A-Z]/.test(password)
  const hasLowercase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)
  const hasSpecial = /[!@#$%^&*(),.?":{}|<>\-_=+[\]\\/`~;']/.test(password)
  const isPasswordComplex = hasMinLength && hasUppercase && hasLowercase && hasNumber && hasSpecial

  const validateForm = (): boolean => {
    const errors: { [key: string]: string } = {}

    const trimmedName = fullName.trim()
    if (!trimmedName) {
      errors.fullName = 'Full Name is required.'
    } else if (trimmedName.length < 2) {
      errors.fullName = 'Full Name must be at least 2 characters.'
    }

    const trimmedEmail = email.trim()
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!trimmedEmail) {
      errors.email = 'Work email address is required.'
    } else if (!emailRegex.test(trimmedEmail)) {
      errors.email = 'Please provide a valid work email format (e.g. name@cargolens.in).'
    }

    if (!password) {
      errors.password = 'Password is required.'
    } else if (!isPasswordComplex) {
      errors.password = 'Password must meet all complexity requirements below.'
    }

    if (!confirmPassword) {
      errors.confirmPassword = 'Confirm Password is required.'
    } else if (confirmPassword !== password) {
      errors.confirmPassword = 'Confirm Password must match Password.'
    }

    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setApiError(null)

    if (!validateForm()) {
      return
    }

    setIsSubmitting(true)
    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
        confirm_password: confirmPassword,
      })

      setSuccessMessage('Registration successful! Your Documentation Executive account has been activated.')

      // Redirect to login page with prefilled email and registration success state
      setTimeout(() => {
        navigate('/login', {
          replace: true,
          state: {
            registered: true,
            email: email.trim().toLowerCase(),
            message: 'Account created successfully! Please sign in with your credentials.',
          },
        })
      }, 1200)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
      const status = axiosErr?.response?.status
      const detail = axiosErr?.response?.data?.detail

      if (status === 409) {
        setApiError('A user with this work email already exists. Please log in or use a different address.')
      } else if (typeof detail === 'string') {
        setApiError(detail)
      } else {
        setApiError('Registration failed. Please check your network connection or contact your administrator.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col lg:flex-row select-none">
      {/* Left Column: Enterprise Showcase */}
      <div className="lg:w-1/2 p-8 sm:p-12 lg:p-16 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-slate-800 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950/40 text-white relative overflow-hidden">
        {/* Subtle decorative glow */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          {/* Logo & Header */}
          <div className="flex items-center gap-3">
            <div className="h-11 w-11 rounded-xl bg-gradient-to-tr from-brand-600 to-sky-400 flex items-center justify-center text-white shadow-lg shadow-brand-500/25">
              <Anchor className="h-6 w-6 stroke-[2.2]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-xl text-white tracking-tight">CargoLens</span>
                <span className="text-xs px-2 py-0.5 font-bold uppercase rounded bg-brand-500/20 text-brand-300 border border-brand-500/30">
                  Enterprise AI
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">Nhava Sheva (JNPT) Maritime Customs Intelligence</p>
            </div>
          </div>

          <div className="mt-12 space-y-4 max-w-lg">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-brand-900/60 text-brand-300 border border-brand-700/50">
              <Sparkles className="h-3.5 w-3.5 text-brand-400" />
              <span>Self-Service Executive Onboarding • Nhava Sheva Node</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
              Join the Customs Pre-Clearance Verification Team
            </h1>
            <p className="text-slate-300 text-sm leading-relaxed">
              Register your corporate credentials to begin validating maritime shipping consignments, auditing discrepancies,
              and operating deterministic customs intelligence.
            </p>
          </div>

          {/* Security & Access Highlights */}
          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-xl">
            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="h-8 w-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-2.5">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">Default Executive Tier</h3>
              <p className="text-xs text-slate-400 mt-1">
                New accounts are automatically provisioned as Documentation Executives with verification rights.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="h-8 w-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-2.5">
                <Lock className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">Argon2id Salted Hashes</h3>
              <p className="text-xs text-slate-400 mt-1">
                Zero plaintext storage. Passwords are hash-protected with memory-hard Argon2id cryptography.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="h-8 w-8 rounded-lg bg-sky-500/10 text-sky-400 flex items-center justify-center mb-2.5">
                <FileCheck2 className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">Audit Trail Provenance</h3>
              <p className="text-xs text-slate-400 mt-1">
                Every review, correction, and consignment verification links to your authenticated corporate identity.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="h-8 w-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center mb-2.5">
                <ShieldAlert className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">Privilege Escalation Guard</h3>
              <p className="text-xs text-slate-400 mt-1">
                Manager authorization gates cannot be bypassed; registration strictly enforces the executive tier.
              </p>
            </div>
          </div>
        </div>

        {/* Port Status Footer */}
        <div className="relative z-10 pt-8 mt-8 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Port Node INNSA-01 Online</span>
          </div>
          <span className="font-mono text-slate-500">Argon2id • OWASP Compliant • TLS 1.3</span>
        </div>
      </div>

      {/* Right Column: Registration Card */}
      <div className="lg:w-1/2 p-6 sm:p-12 lg:p-16 flex items-center justify-center bg-slate-900/50">
        <div className="max-w-md w-full space-y-6">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-brand-500/10 text-brand-400 border border-brand-500/20 text-[11px] font-bold mb-2">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Role: Documentation Executive</span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-white">
              Create Corporate Account
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Enter your corporate credentials to register for CargoLens AI pre-clearance terminal access.
            </p>
          </div>

          {/* Success Banner */}
          {successMessage && (
            <div className="rounded-xl bg-emerald-950/50 border border-emerald-800/80 p-4 flex items-start gap-3 animate-fade-in">
              <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
              <div className="text-xs text-emerald-200">
                <span className="font-semibold text-emerald-100">Registration Successful:</span> {successMessage}
              </div>
            </div>
          )}

          {/* Error Banner */}
          {apiError && (
            <div className="rounded-xl bg-rose-950/50 border border-rose-800/80 p-4 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
              <div className="text-xs text-rose-200">
                <span className="font-semibold text-rose-100">Registration Error:</span> {apiError}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* Full Name */}
            <div>
              <label htmlFor="fullName" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Full Name <span className="text-rose-400">*</span>
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <UserIcon className="h-4 w-4" />
                </div>
                <input
                  id="fullName"
                  type="text"
                  autoComplete="name"
                  required
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value)
                    if (fieldErrors.fullName) {
                      setFieldErrors((prev) => ({ ...prev, fullName: '' }))
                    }
                  }}
                  placeholder="e.g. Priya Nair"
                  className={`block w-full pl-9 pr-3 py-2.5 text-sm bg-slate-950 border rounded-lg text-white placeholder-slate-500 transition ${
                    fieldErrors.fullName
                      ? 'border-rose-500 focus:ring-rose-500 focus:border-rose-500'
                      : 'border-slate-800 focus:ring-2 focus:ring-brand-500 focus:border-brand-500'
                  }`}
                />
              </div>
              {fieldErrors.fullName && (
                <p className="mt-1 text-[11px] text-rose-400 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0" />
                  {fieldErrors.fullName}
                </p>
              )}
            </div>

            {/* Work Email */}
            <div>
              <label htmlFor="email" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Work Email Address <span className="text-rose-400">*</span>
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    if (fieldErrors.email) {
                      setFieldErrors((prev) => ({ ...prev, email: '' }))
                    }
                  }}
                  placeholder="priya.nair@cargolens.in"
                  className={`block w-full pl-9 pr-3 py-2.5 text-sm bg-slate-950 border rounded-lg text-white placeholder-slate-500 transition ${
                    fieldErrors.email
                      ? 'border-rose-500 focus:ring-rose-500 focus:border-rose-500'
                      : 'border-slate-800 focus:ring-2 focus:ring-brand-500 focus:border-brand-500'
                  }`}
                />
              </div>
              {fieldErrors.email && (
                <p className="mt-1 text-[11px] text-rose-400 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0" />
                  {fieldErrors.email}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Password <span className="text-rose-400">*</span>
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (fieldErrors.password) {
                      setFieldErrors((prev) => ({ ...prev, password: '' }))
                    }
                  }}
                  placeholder="••••••••••••"
                  className={`block w-full pl-9 pr-10 py-2.5 text-sm bg-slate-950 border rounded-lg text-white placeholder-slate-500 transition ${
                    fieldErrors.password
                      ? 'border-rose-500 focus:ring-rose-500 focus:border-rose-500'
                      : 'border-slate-800 focus:ring-2 focus:ring-brand-500 focus:border-brand-500'
                  }`}
                />
                <button
                  type="button"
                  data-testid="toggle-password-visibility"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-500 hover:text-slate-300 focus:outline-none"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {fieldErrors.password && (
                <p className="mt-1 text-[11px] text-rose-400 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0" />
                  {fieldErrors.password}
                </p>
              )}

              {/* Password Complexity Checklist */}
              <div className="mt-2.5 p-3 rounded-lg bg-slate-950/80 border border-slate-800/80 space-y-1.5">
                <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Password Requirements:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-[11px]">
                  <div className={`flex items-center gap-1.5 ${hasMinLength ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {hasMinLength ? <Check className="h-3 w-3 shrink-0" /> : <span className="h-1.5 w-1.5 rounded-full bg-slate-600 ml-1 mr-0.5" />}
                    <span>At least 8 characters</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${hasUppercase ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {hasUppercase ? <Check className="h-3 w-3 shrink-0" /> : <span className="h-1.5 w-1.5 rounded-full bg-slate-600 ml-1 mr-0.5" />}
                    <span>One uppercase letter (A-Z)</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${hasLowercase ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {hasLowercase ? <Check className="h-3 w-3 shrink-0" /> : <span className="h-1.5 w-1.5 rounded-full bg-slate-600 ml-1 mr-0.5" />}
                    <span>One lowercase letter (a-z)</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${hasNumber ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {hasNumber ? <Check className="h-3 w-3 shrink-0" /> : <span className="h-1.5 w-1.5 rounded-full bg-slate-600 ml-1 mr-0.5" />}
                    <span>One number (0-9)</span>
                  </div>
                  <div className={`flex items-center gap-1.5 col-span-1 sm:col-span-2 ${hasSpecial ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {hasSpecial ? <Check className="h-3 w-3 shrink-0" /> : <span className="h-1.5 w-1.5 rounded-full bg-slate-600 ml-1 mr-0.5" />}
                    <span>One special symbol (!@#$%^&*...)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Confirm Password */}
            <div>
              <label htmlFor="confirmPassword" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Confirm Password <span className="text-rose-400">*</span>
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    if (fieldErrors.confirmPassword) {
                      setFieldErrors((prev) => ({ ...prev, confirmPassword: '' }))
                    }
                  }}
                  placeholder="••••••••••••"
                  className={`block w-full pl-9 pr-10 py-2.5 text-sm bg-slate-950 border rounded-lg text-white placeholder-slate-500 transition ${
                    fieldErrors.confirmPassword
                      ? 'border-rose-500 focus:ring-rose-500 focus:border-rose-500'
                      : 'border-slate-800 focus:ring-2 focus:ring-brand-500 focus:border-brand-500'
                  }`}
                />
                <button
                  type="button"
                  data-testid="toggle-confirm-password-visibility"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  aria-label={showConfirmPassword ? 'Hide password confirmation' : 'Show password confirmation'}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-500 hover:text-slate-300 focus:outline-none"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {fieldErrors.confirmPassword && (
                <p className="mt-1 text-[11px] text-rose-400 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0" />
                  {fieldErrors.confirmPassword}
                </p>
              )}
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-sm shadow-lg shadow-brand-600/30 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-60 transition mt-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Creating Account...</span>
                </>
              ) : (
                <>
                  <span>Complete Executive Registration</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          {/* Already have an account link */}
          <div className="pt-4 border-t border-slate-800/80 text-center space-y-2">
            <p className="text-xs text-slate-400">
              Already have an account?{' '}
              <Link
                to="/login"
                className="font-semibold text-brand-400 hover:text-brand-300 underline underline-offset-4 transition"
              >
                Login
              </Link>
            </p>
            <p className="text-[11px] text-slate-500">
              Protected by role-based customs access policies. Unauthorized access is monitored.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
