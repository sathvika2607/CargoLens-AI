import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { UserRole } from '../types/auth'
import { ShieldAlert, Loader2 } from 'lucide-react'

interface ProtectedRouteProps {
  children: React.ReactElement
  requiredRole?: UserRole
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, requiredRole }) => {
  const { user, isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center text-slate-500">
        <Loader2 className="h-8 w-8 animate-spin text-brand-600 mb-2" />
        <span className="text-sm font-medium">Verifying authorization...</span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requiredRole && user?.role !== requiredRole) {
    return (
      <div className="max-w-lg mx-auto mt-12 p-6 bg-white border border-rose-200 rounded-xl shadow-sm text-center">
        <div className="h-12 w-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3">
          <ShieldAlert className="h-6 w-6" />
        </div>
        <h2 className="text-lg font-bold text-slate-900">Access Restricted (403 Forbidden)</h2>
        <p className="text-sm text-slate-600 mt-2">
          Your account role (<span className="font-mono font-semibold">{user?.role}</span>) does not possess authorization to access this view.
        </p>
      </div>
    )
  }

  return children
}
