import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Anchor, ShieldCheck, Box, Activity, LogOut, LogIn } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export const Navbar: React.FC = () => {
  const location = useLocation()
  const { user, isAuthenticated, logout } = useAuth()

  return (
    <header className="bg-slate-900 border-b border-slate-800 text-white sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo & Port Context */}
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="h-9 w-9 rounded-lg bg-brand-600 flex items-center justify-center text-white shadow-md group-hover:bg-brand-500 transition-colors">
                <Box className="h-5 w-5 stroke-[2.5]" />
              </div>
              <div>
                <span className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                  CargoLens <span className="text-brand-400 font-semibold">AI</span>
                </span>
                <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-mono">
                  Customs Verification Gateway
                </span>
              </div>
            </Link>
            <div className="hidden md:flex items-center ml-4 pl-4 border-l border-slate-700/80">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                <Anchor className="h-3 w-3 text-brand-400" /> Nhava Sheva (JNPT)
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1 sm:gap-2">
            <Link
              to="/"
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                location.pathname === '/'
                  ? 'bg-slate-800 text-brand-400 font-semibold'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Activity className="h-4 w-4" /> System Overview
            </Link>

            {isAuthenticated ? (
              <Link
                to="/shipments"
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  location.pathname.startsWith('/shipments')
                    ? 'bg-slate-800 text-brand-400 font-semibold'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <Box className="h-4 w-4" /> Shipments
              </Link>
            ) : null}
          </nav>

          {/* User Profile & Actions */}
          <div className="flex items-center gap-3">
            {isAuthenticated && user ? (
              <div className="flex items-center gap-3">
                <div className="hidden sm:flex flex-col text-right">
                  <span className="text-xs font-semibold text-white leading-tight">
                    {user.full_name}
                  </span>
                  <span className="text-[10px] font-mono text-brand-400">
                    {user.role === 'DOCUMENTATION_MANAGER' ? 'Manager' : 'Executive'}
                  </span>
                </div>
                <button
                  onClick={() => logout()}
                  title="Sign Out"
                  className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950/60 text-slate-300 hover:text-rose-400 border border-slate-700/80 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white shadow-sm transition-colors"
              >
                <LogIn className="h-3.5 w-3.5" /> Sign In
              </Link>
            )}

            <span className="hidden lg:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700/80">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              v0.3.0
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
