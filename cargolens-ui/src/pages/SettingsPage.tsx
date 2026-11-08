import React from 'react'
import {
  Shield,
  UserCheck,
  Server,
  Layers,
  KeyRound,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useQuery } from '@tanstack/react-query'
import { fetchApiHealth, fetchDbHealth } from '../api/health'

export const SettingsPage: React.FC = () => {
  const { user, isManager } = useAuth()

  const { data: apiHealth } = useQuery({
    queryKey: ['settingsApiHealth'],
    queryFn: fetchApiHealth,
  })

  const { data: dbHealth } = useQuery({
    queryKey: ['settingsDbHealth'],
    queryFn: fetchDbHealth,
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-slate-200">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          System Settings & Operations Gateway
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Review environment parameters, gateway connectivity, and role authorization policies.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: User & RBAC Permissions */}
        <div className="lg:col-span-2 space-y-6">
          {/* User Profile Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-brand-600" />
              Authenticated Session Particulars
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-400 font-medium">Full Name</span>
                <p className="font-bold text-slate-900 mt-0.5">{user?.full_name}</p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Email Address</span>
                <p className="font-mono text-slate-900 mt-0.5">{user?.email}</p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Assigned Operational Role</span>
                <div className="mt-1">
                  {isManager ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                      <Shield className="h-3 w-3 text-indigo-600" /> Documentation Manager
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200">
                      <UserCheck className="h-3 w-3 text-sky-600" /> Documentation Executive
                    </span>
                  )}
                </div>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Account Status</span>
                <p className="font-bold text-emerald-700 mt-0.5 flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-emerald-500"></span> Active & Verified
                </p>
              </div>
            </div>
          </div>

          {/* RBAC Matrix */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Layers className="h-4 w-4 text-brand-600" />
              Role-Based Access Control (RBAC) Governance Matrix
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase">
                  <tr>
                    <th className="py-2.5 px-3">System Capability</th>
                    <th className="py-2.5 px-3 text-center">Documentation Executive</th>
                    <th className="py-2.5 px-3 text-center">Documentation Manager</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  <tr>
                    <td className="py-2.5 px-3 font-medium">Create & Manage Shipments</td>
                    <td className="py-2.5 px-3 text-center text-emerald-600 font-bold">Own Shipments</td>
                    <td className="py-2.5 px-3 text-center text-emerald-600 font-bold">All Shipments</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 px-3 font-medium">Upload & Version Documents</td>
                    <td className="py-2.5 px-3 text-center text-emerald-600 font-bold">Permitted</td>
                    <td className="py-2.5 px-3 text-center text-emerald-600 font-bold">Permitted</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 px-3 font-medium">Confirm & Correct Extracted Fields</td>
                    <td className="py-2.5 px-3 text-center text-emerald-600 font-bold">Permitted</td>
                    <td className="py-2.5 px-3 text-center text-emerald-600 font-bold">Permitted</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 px-3 font-medium">Execute Verification Workflow</td>
                    <td className="py-2.5 px-3 text-center text-emerald-600 font-bold">Permitted (if ready)</td>
                    <td className="py-2.5 px-3 text-center text-emerald-600 font-bold">Permitted (if ready)</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 px-3 font-medium">Arbitrary Manual Status Patch (VERIFIED/EXPORTED)</td>
                    <td className="py-2.5 px-3 text-center text-rose-600 font-bold">HTTP 403 Forbidden</td>
                    <td className="py-2.5 px-3 text-center text-rose-600 font-bold">HTTP 403 Forbidden</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 px-3 font-medium">Access Global Audit Trail & Port Metrics</td>
                    <td className="py-2.5 px-3 text-center text-slate-400">Scoped</td>
                    <td className="py-2.5 px-3 text-center text-indigo-600 font-bold">Full Port Visibility</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Platform Gateway */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Server className="h-4 w-4 text-emerald-600" />
              Infrastructure Hub
            </h2>
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-slate-600 font-medium">Port Gateway</span>
                <span className="font-bold text-slate-900">Nhava Sheva (JNPT)</span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-slate-600 font-medium">FastAPI Service</span>
                <span
                  className={`font-mono font-bold ${
                    apiHealth?.status === 'healthy' ? 'text-emerald-700' : 'text-rose-700'
                  }`}
                >
                  {apiHealth?.status === 'healthy' ? 'HEALTHY' : 'OFFLINE'}
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-slate-600 font-medium">PostgreSQL 16 Engine</span>
                <span
                  className={`font-mono font-bold ${
                    dbHealth?.status === 'healthy' && dbHealth?.database === 'connected'
                      ? 'text-emerald-700'
                      : 'text-rose-700'
                  }`}
                >
                  {dbHealth?.status === 'healthy' && dbHealth?.database === 'connected'
                    ? 'ONLINE (Port 5432)'
                    : 'OFFLINE'}
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-slate-600 font-medium">OCR Extraction Pipeline</span>
                <span className="font-bold text-slate-900">Tesseract OCR + PyMuPDF</span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-slate-600 font-medium">AI Structured Extraction</span>
                <span className="font-bold text-slate-900">Claude Vision Multi-Modal</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
