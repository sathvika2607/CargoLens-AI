import React, { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Anchor,
  Lock,
  Mail,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  FileCheck2,
  Zap,
  Sparkles,
} from 'lucide-react'

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, isAuthenticated } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Redirect if already authenticated
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/shipments'

  React.useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true })
    }
  }, [isAuthenticated, navigate, from])

  React.useEffect(() => {
    const state = location.state as { registered?: boolean; message?: string; email?: string } | undefined
    if (state?.registered) {
      setSuccessMessage(state.message || 'Account created successfully! Please sign in with your credentials.')
      if (state.email) {
        setEmail(state.email)
      }
    }
  }, [location.state])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      setError('Please provide your work email address.')
      return
    }
    if (!password) {
      setError('Please enter your account password.')
      return
    }

    setIsSubmitting(true)
    try {
      await login(trimmedEmail, password)
      navigate(from, { replace: true })
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      const detail = axiosErr?.response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else {
        setError('Authentication failed. Please verify your credentials or server connection.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col lg:flex-row select-none">
      {/* Left Column: Enterprise Terminal Showcase */}
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
              <span>Version 2.4 Production Build • Nhava Sheva Port Hub</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
              Deterministic Pre-Clearance Verification for Customs Operations
            </h1>
            <p className="text-slate-300 text-sm leading-relaxed">
              Automate multi-document validation between Commercial Invoices, Packing Lists, and Ocean Bills of Lading.
              Protect your brokerage from customs penalties, weight discrepancies, and misdeclared valuations.
            </p>
          </div>

          {/* Feature Highlights Grid */}
          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-xl">
            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="h-8 w-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-2.5">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">11 Deterministic Rules</h3>
              <p className="text-xs text-slate-400 mt-1">
                Gross weight tolerances, buyer/seller entity reconciliation, and container consistency.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="h-8 w-8 rounded-lg bg-sky-500/10 text-sky-400 flex items-center justify-center mb-2.5">
                <Zap className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">Strict Arithmetic Guard</h3>
              <p className="text-xs text-slate-400 mt-1">
                Unstated invoice totals are never fabricated; explicit source evidence is required.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="h-8 w-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-2.5">
                <FileCheck2 className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">Human Review Overlay</h3>
              <p className="text-xs text-slate-400 mt-1">
                Immutable audit trail captures field corrections, reviewer identity, and justifications.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="h-8 w-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center mb-2.5">
                <CheckCircle2 className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">SHA-256 Verified Export</h3>
              <p className="text-xs text-slate-400 mt-1">
                Reproducible customs declarations with cryptographic checksums and formula sanitization.
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
          <span className="font-mono text-slate-500">AES-256 • Argon2id • TLS 1.3</span>
        </div>
      </div>

      {/* Right Column: Authentication Card */}
      <div className="lg:w-1/2 p-6 sm:p-12 lg:p-16 flex items-center justify-center bg-slate-900/50">
        <div className="max-w-md w-full space-y-6">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-white">
              Terminal Access
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Enter your authorized credentials to access the CargoLens workspace.
            </p>
          </div>

          {successMessage && (
            <div className="rounded-xl bg-emerald-950/50 border border-emerald-800/80 p-4 flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
              <div className="text-xs text-emerald-200">
                <span className="font-semibold text-emerald-100">Registration Successful:</span> {successMessage}
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-xl bg-rose-950/50 border border-rose-800/80 p-4 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
              <div className="text-xs text-rose-200">
                <span className="font-semibold text-rose-100">Authentication Error:</span> {error}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Work Email Address
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
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="executive@cargolens.in"
                  className="block w-full pl-9 pr-3 py-2.5 text-sm bg-slate-950 border border-slate-800 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="block w-full pl-9 pr-10 py-2.5 text-sm bg-slate-950 border border-slate-800 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-500 hover:text-slate-300"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-sm shadow-lg shadow-brand-600/30 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-60 transition"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Verifying Credentials...</span>
                </>
              ) : (
                <>
                  <span>Sign In to Terminal</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          {/* Registration Navigation Link */}
          <div className="pt-2 text-center">
            <p className="text-xs text-slate-400">
              Don't have an account?{' '}
              <Link
                to="/register"
                className="font-semibold text-brand-400 hover:text-brand-300 underline underline-offset-4 transition"
              >
                Register
              </Link>
            </p>
          </div>

          <div className="pt-4 border-t border-slate-800/80 text-center">
            <p className="text-[11px] text-slate-500">
              Role-Based Access Control enforced: Executives verify consignments; Managers authorize final customs exports.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}