import React from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Box,
  FileCheck2,
  AlertTriangle,
  History,
  Settings,
  LogOut,
  Shield,
  UserCheck,
  Anchor,
  ChevronRight,
  BarChart3,
  PlusCircle,
  FileDown,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

interface NavItem {
  label: string
  path: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
  badgeClass?: string
}

export const Sidebar: React.FC<{ onCloseMobile?: () => void }> = ({ onCloseMobile }) => {
  const { user, isManager, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const navItems: NavItem[] = [
    { label: 'Operations Dashboard', path: '/', icon: LayoutDashboard },
    ...(isManager
      ? [
          {
            label: 'Manager Command Deck',
            path: '/manager',
            icon: ShieldAlert,
            badge: 'MGR',
            badgeClass: 'bg-indigo-900/80 text-indigo-300 border-indigo-700',
          },
        ]
      : []),
    { label: isManager ? 'Manager Analytics' : 'Operations Analytics', path: '/analytics', icon: BarChart3 },
    { label: 'Shipment Registry', path: '/shipments', icon: Box },
    { label: 'Register Consignment', path: '/shipments/create', icon: PlusCircle },
    { label: 'Document Review', path: '/review', icon: FileCheck2 },
    { label: 'Validation Issues', path: '/validations', icon: AlertTriangle },
    { label: 'Customs Export Portal', path: '/exports', icon: FileDown },
    { label: 'Audit & History', path: '/audit-history', icon: History },
    {
      label: 'Simulation Center',
      path: '/simulation',
      icon: Sparkles,
      badge: 'DEMO',
      badgeClass: 'bg-amber-900/80 text-amber-300 border-amber-700',
    },
    { label: 'System Settings', path: '/settings', icon: Settings },
  ]

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const getInitials = (name?: string) => {
    if (!name) return 'CL'
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/'
    }
    return location.pathname === path || (path !== '/shipments' && location.pathname.startsWith(path))
  }

  return (
    <aside className="w-64 h-screen bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 select-none text-slate-300">
      {/* Top Branding & Navigation */}
      <div className="flex flex-col min-h-0 flex-1">
        {/* Logo Banner */}
        <div className="p-4 sm:p-5 border-b border-slate-800/80 shrink-0">
          <Link
            to="/"
            onClick={onCloseMobile}
            className="flex items-center gap-3 group focus:outline-none"
          >
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-brand-600 to-sky-400 flex items-center justify-center text-white shadow-md shadow-brand-500/20 group-hover:scale-105 transition-transform">
              <Anchor className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-base text-white tracking-tight">CargoLens</span>
                <span className="text-xs px-1.5 py-0.5 font-bold uppercase rounded bg-brand-500/20 text-brand-300 border border-brand-500/30">
                  AI
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium flex items-center gap-1 mt-0.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                Nhava Sheva Port Hub
              </p>
            </div>
          </Link>
        </div>

        {/* Role Badge Indicator */}
        <div className="px-5 py-2.5 border-b border-slate-800/50 bg-slate-950/40 shrink-0">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 font-medium text-[11px]">Access Tier:</span>
            {isManager ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-950 text-indigo-300 border border-indigo-800">
                <Shield className="h-3 w-3 text-indigo-400" />
                Doc Manager
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-950 text-sky-300 border border-sky-800">
                <UserCheck className="h-3 w-3 text-sky-400" />
                Doc Executive
              </span>
            )}
          </div>
        </div>

        {/* Scrollable Navigation Links */}
        <nav className="p-2.5 space-y-1 overflow-y-auto flex-1 custom-scrollbar">
          {navItems.map((item) => {
            const active = isActive(item.path)
            const Icon = item.icon
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onCloseMobile}
                className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  active
                    ? 'bg-brand-600 text-white shadow-sm font-semibold'
                    : 'text-slate-300 hover:bg-slate-800/70 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon
                    className={`h-4 w-4 shrink-0 ${
                      active ? 'text-white' : 'text-slate-400 group-hover:text-slate-200'
                    }`}
                  />
                  <span className="truncate">{item.label}</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0 ml-1">
                  {item.badge && (
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-mono font-bold border ${
                        item.badgeClass || 'bg-slate-800 text-slate-300 border-slate-700'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                  {active && <ChevronRight className="h-3.5 w-3.5 text-white/70" />}
                </div>
              </Link>
            )
          })}
        </nav>
      </div>

      {/* User Card & Logout Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/60 shrink-0">
        <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/80 border border-slate-800">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="h-8 w-8 rounded-full bg-brand-700/60 text-brand-200 border border-brand-500/40 flex items-center justify-center text-xs font-bold shrink-0">
              {getInitials(user?.full_name)}
            </div>
            <div className="min-w-0 truncate">
              <p className="text-xs font-semibold text-white truncate">
                {user?.full_name || 'Anonymous User'}
              </p>
              <p className="text-[10px] text-slate-400 truncate">{user?.email || 'user@cargolens.local'}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Sign Out"
            className="p-1.5 rounded-md text-slate-400 hover:text-red-400 hover:bg-red-950/30 transition-colors ml-2 shrink-0"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}
