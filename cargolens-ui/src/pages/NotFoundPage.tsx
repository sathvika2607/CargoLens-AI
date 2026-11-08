import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-6">
      <div className="text-6xl font-black text-slate-300 font-mono">404</div>
      <h1 className="text-xl font-bold text-slate-800 mt-2">Page Not Found</h1>
      <p className="text-sm text-slate-500 mt-1 max-w-sm">
        The requested customs view does not exist or has been relocated.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-500 transition-colors shadow-sm"
      >
        <ArrowLeft className="h-4 w-4" /> Return to Dashboard
      </Link>
    </div>
  )
}
