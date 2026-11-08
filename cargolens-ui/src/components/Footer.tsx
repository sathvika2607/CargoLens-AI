import React from 'react'

export const Footer: React.FC = () => {
  return (
    <footer className="bg-white border-t border-slate-200 mt-auto py-6">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
        <div>
          <span className="font-semibold text-slate-700">CargoLens AI</span> — Intelligent Import Documentation & Verification Platform
        </div>
        <div className="flex items-center gap-6 font-mono text-[11px]">
          <span>FastAPI + Python 3.12</span>
          <span>PostgreSQL 16</span>
          <span>React 18 + Vite</span>
        </div>
      </div>
    </footer>
  )
}
