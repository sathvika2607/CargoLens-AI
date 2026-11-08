import React, { useState } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import {
  Menu,
  Search,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  Shield,
  UserCheck,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchApiHealth, fetchDbHealth } from '../../api/health'
import { useAuth } from '../../context/AuthContext'

interface HeaderProps {
  onOpenMobileMenu?: () => void
}

export const Header: React.FC<HeaderProps> = ({ onOpenMobileMenu }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, isManager } = useAuth()
  const [searchValue, setSearchValue] = useState('')

  // Periodic health check probe
  const { data: apiHealth, isError: isApiError } = useQuery({
    queryKey: ['headerApiHealth'],
    queryFn: fetchApiHealth,
    refetchInterval: 30000,
    retry: 1,
  })

  const { data: dbHealth, isError: isDbError } = useQuery({
    queryKey: ['headerDbHealth'],
    queryFn: fetchDbHealth,
    refetchInterval: 30000,
    retry: 1,
  })

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchValue.trim()) {
      navigate(`/shipments?search=${encodeURIComponent(searchValue.trim())}`)
    }
  }

  // Derive breadcrumbs from path
  const getBreadcrumbs = () => {
    const path = location.pathname
    if (path === '/') return [{ label: 'Operations Dashboard', path: '/' }]
    if (path.startsWith('/analytics')) {
      return [
        { label: 'Intelligence', path: '/' },
        { label: 'Manager Operations Analytics', path: '/analytics' },
      ]
    }
    if (path.startsWith('/shipments')) {
      const parts = path.split('/').filter(Boolean)
      if (parts.length === 1) {
        return [
          { label: 'Operations', path: '/' },
          { label: 'Shipment Registry', path: '/shipments' },
        ]
      }
      return [
        { label: 'Shipments', path: '/shipments' },
        { label: `Shipment #${parts[1]}`, path },
      ]
    }
    if (path.startsWith('/review')) {
      return [
        { label: 'Operations', path: '/' },
        { label: 'Document Review Workspace', path: '/review' },
      ]
    }
    if (path.startsWith('/validations')) {
      return [
        { label: 'Operations', path: '/' },
        { label: 'Cross-Document Validation Issues', path: '/validations' },
      ]
    }
    if (path.startsWith('/audit-history')) {
      return [
        { label: 'Governance', path: '/' },
        { label: 'Review Audit History', path: '/audit-history' },
      ]
    }
    if (path.startsWith('/settings')) {
      return [
        { label: 'Configuration', path: '/' },
        { label: 'System Settings & Gateway', path: '/settings' },
      ]
    }
    return [{ label: 'CargoLens AI', path: '/' }]
  }

  const breadcrumbs = getBreadcrumbs()

  const isApiOk = !isApiError && apiHealth?.status === 'healthy'
  const isDbOk = !isDbError && dbHealth?.status === 'healthy' && dbHealth?.database === 'connected'
  const isHealthy = isApiOk && isDbOk

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between gap-4 sticky top-0 z-30 shadow-xs">
      {/* Left: Mobile Toggle & Breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onOpenMobileMenu}
          className="lg:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-none"
          aria-label="Toggle navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        <nav className="flex items-center gap-1.5 text-xs sm:text-sm text-slate-500 font-medium truncate">
          {breadcrumbs.map((bc, idx) => (
            <React.Fragment key={bc.path + idx}>
              {idx > 0 && <ChevronRight className="h-3.5 w-3.5 text-slate-400 shrink-0" />}
              {idx === breadcrumbs.length - 1 ? (
                <span className="font-semibold text-slate-900 truncate">{bc.label}</span>
              ) : (
                <Link
                  to={bc.path}
                  className="hover:text-brand-600 transition-colors truncate"
                >
                  {bc.label}
                </Link>
              )}
            </React.Fragment>
          ))}
        </nav>
      </div>

      {/* Right: Search, Health Indicator, User Info */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Global Quick Search */}
        <form onSubmit={handleSearchSubmit} className="hidden md:flex relative items-center">
          <Search className="h-4 w-4 absolute left-3 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search shipment number..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            className="w-56 lg:w-64 pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-brand-500 focus:border-brand-500 transition-all focus:bg-white"
          />
        </form>

        {/* Real-time Health Status Pill */}
        <div
          title={isHealthy ? 'Services Operational' : 'Degraded Connectivity'}
          className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
            isHealthy
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-rose-50 text-rose-700 border-rose-200'
          }`}
        >
          {isHealthy ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
          ) : (
            <AlertCircle className="h-3.5 w-3.5 text-rose-600" />
          )}
          <span className="tracking-tight text-[11px]">
            API: {isApiOk ? 'OK' : 'ERR'} • DB: {isDbOk ? 'OK' : 'ERR'}
          </span>
        </div>

        {/* User Role Tag */}
        {user && (
          <div className="hidden lg:flex items-center gap-2 pl-2 border-l border-slate-200 text-xs">
            <div className="flex flex-col text-right">
              <span className="font-semibold text-slate-900 leading-tight">{user.full_name}</span>
              <span className="text-[10px] text-slate-500 font-medium">
                {isManager ? 'Documentation Manager' : 'Documentation Executive'}
              </span>
            </div>
            <div className="h-8 w-8 rounded-full bg-slate-100 border border-slate-300 flex items-center justify-center text-slate-700 font-bold text-xs">
              {isManager ? (
                <Shield className="h-4 w-4 text-indigo-600" />
              ) : (
                <UserCheck className="h-4 w-4 text-sky-600" />
              )}
            </div>
          </div>
        )}
      </div>
    </header>
  )
}
