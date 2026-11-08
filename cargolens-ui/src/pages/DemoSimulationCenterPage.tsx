import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Play,
  RotateCcw,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  ExternalLink,
  ShieldAlert,
  Sparkles,
  Database,
  Download,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import {
  getSimulationScenarios,
  getSimulationStatus,
  runSimulation,
  resetSimulation,
} from '../api/simulation'
import type {
  SimulationScenarioItem,
  SimulationStatusResponse,
  SimulationRunResult,
} from '../types/simulation'

export const DemoSimulationCenterPage: React.FC = () => {
  const { isManager } = useAuth()

  const [scenarios, setScenarios] = useState<SimulationScenarioItem[]>([])
  const [statusData, setStatusData] = useState<SimulationStatusResponse | null>(null)
  const [selectedScenario, setSelectedScenario] = useState<string>('ALL')
  const [providerType, setProviderType] = useState<string>('fixture')

  const [loading, setLoading] = useState<boolean>(true)
  const [simulating, setSimulating] = useState<boolean>(false)
  const [resetting, setResetting] = useState<boolean>(false)
  const [simulationResults, setSimulationResults] = useState<SimulationRunResult[]>([])
  const [simulationMessage, setSimulationMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Simulation step ticker
  const [currentStep, setCurrentStep] = useState<string>('')

  const loadData = async () => {
    try {
      setLoading(true)
      setErrorMessage(null)
      const [scenariosRes, statusRes] = await Promise.all([
        getSimulationScenarios(),
        getSimulationStatus(),
      ])
      setScenarios(scenariosRes.scenarios)
      setStatusData(statusRes)
    } catch (err: any) {
      console.error('Failed to load simulation data:', err)
      setErrorMessage(err.response?.data?.detail || 'Failed to load simulation center data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleStartSimulation = async () => {
    if (!isManager) return
    try {
      setSimulating(true)
      setErrorMessage(null)
      setSimulationMessage(null)
      setSimulationResults([])
      setCurrentStep('Executing pipeline: document synthesis, OCR, structured extraction & validation...')

      const resp = await runSimulation({
        scenario_type: selectedScenario,
        provider_type: providerType,
      })

      setSimulationResults(resp.results)
      setSimulationMessage(resp.message)
      setCurrentStep('Simulation completed successfully.')

      // Refresh persisted list
      const updatedStatus = await getSimulationStatus()
      setStatusData(updatedStatus)
    } catch (err: any) {
      console.error('Simulation execution failed:', err)
      setErrorMessage(err.response?.data?.detail || 'Simulation execution failed.')
    } finally {
      setSimulating(false)
    }
  }

  const handleReset = async () => {
    if (!isManager) return
    if (!window.confirm('Are you sure you want to clean all demonstration consignments? Real consignments will not be touched.')) {
      return
    }
    try {
      setResetting(true)
      setErrorMessage(null)
      const resp = await resetSimulation()
      setSimulationMessage(resp.message)
      setSimulationResults([])
      const updatedStatus = await getSimulationStatus()
      setStatusData(updatedStatus)
    } catch (err: any) {
      console.error('Reset failed:', err)
      setErrorMessage(err.response?.data?.detail || 'Failed to clean demonstration consignments.')
    } finally {
      setResetting(false)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'EXPORTED':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">EXPORTED</span>
      case 'VERIFIED':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">VERIFIED</span>
      case 'REVIEW_REQUIRED':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">REVIEW REQUIRED</span>
      case 'PROCESSING':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300">PROCESSING</span>
      case 'DOCUMENTS_PENDING':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-300">DOCUMENTS PENDING</span>
      default:
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-800 border border-gray-300">{status}</span>
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header with Badges */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              CargoLens AI — Demo Simulation Center
            </h1>
            <span className="inline-flex items-center px-3 py-1 rounded-md text-xs font-bold bg-amber-500 text-white shadow-sm tracking-wide">
              DEMONSTRATION DATA & TEST LAB
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            End-to-end customs verification workflow generator powered by genuine application services.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={loading || simulating}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          {isManager && (
            <button
              onClick={handleReset}
              disabled={resetting || simulating}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition shadow-sm disabled:opacity-50"
            >
              <RotateCcw className={`w-4 h-4 ${resetting ? 'animate-spin' : ''}`} />
              Reset Demo Data
            </button>
          )}
        </div>
      </div>

      {/* Safety Notice & Integrity Banner */}
      <div className="bg-gradient-to-r from-slate-900 to-indigo-950 rounded-xl p-5 text-white shadow-md">
        <div className="flex items-start gap-4">
          <div className="p-2.5 bg-white/10 rounded-lg shrink-0">
            <Database className="w-6 h-6 text-indigo-300" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              Authentic Pipeline Execution — No Mock Screens or Hardcoded Metrics
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Every simulation below creates authentic database records, synthesizes realistic single-page PDF files using PyMuPDF, queues background OCR ingestion jobs, runs structured document extraction, executes all 11 cross-document validation rules, and halts at REVIEW_REQUIRED awaiting genuine human review.
            </p>
            <div className="flex flex-wrap items-center gap-4 pt-2 text-xs text-slate-400">
              <span>Environment: <strong className="text-emerald-400">{statusData?.environment || 'development'}</strong></span>
              <span>•</span>
              <span>
                Claude Vision: {statusData?.anthropic_configured ? (
                  <strong className="text-emerald-400">Configured ({statusData.anthropic_model})</strong>
                ) : (
                  <strong className="text-amber-400">Not Configured (Requires ANTHROPIC_API_KEY)</strong>
                )}
              </span>
              <span>•</span>
              <span>Active Demo Consignments in DB: <strong className="text-white">{statusData?.total_demo_shipments || 0}</strong></span>
            </div>
          </div>
        </div>
      </div>

      {/* Role Banner if not manager */}
      {!isManager && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-3 text-amber-800 text-sm">
          <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0" />
          <span>
            You are viewing the Simulation Center in <strong>Read-Only</strong> mode as a Documentation Executive. Executing organization-wide demonstration simulations requires <strong>Documentation Manager</strong> authorization.
          </span>
        </div>
      )}

      {/* Error or Success alerts */}
      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {simulationMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-800 flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span>{simulationMessage}</span>
        </div>
      )}

      {/* Simulation Control Deck */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Configure Demonstration Simulation</h2>
            <p className="text-xs text-slate-500">Select target scenario and AI extraction modality</p>
          </div>
          {isManager && (
            <button
              onClick={handleStartSimulation}
              disabled={simulating}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition shadow-sm disabled:opacity-50"
            >
              <Play className={`w-4 h-4 ${simulating ? 'animate-pulse' : ''}`} />
              {simulating ? 'Executing Pipeline...' : 'Start Simulation'}
            </button>
          )}
        </div>

        {/* Live Stepper indicator when simulating */}
        {simulating && (
          <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-lg space-y-2">
            <div className="flex items-center gap-2 text-indigo-900 font-semibold text-sm">
              <RefreshCw className="w-4 h-4 animate-spin text-indigo-600" />
              <span>{currentStep}</span>
            </div>
            <div className="w-full bg-indigo-200 h-1.5 rounded-full overflow-hidden">
              <div className="bg-indigo-600 h-full rounded-full animate-pulse w-3/4"></div>
            </div>
          </div>
        )}

        {/* Settings row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Provider Selection */}
          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              AI Structured Extraction Provider
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label
                className={`flex items-start gap-3 p-3.5 border rounded-lg cursor-pointer transition ${
                  providerType === 'fixture'
                    ? 'border-indigo-600 bg-indigo-50/50'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <input
                  type="radio"
                  name="provider"
                  value="fixture"
                  checked={providerType === 'fixture'}
                  onChange={() => setProviderType('fixture')}
                  className="mt-0.5 text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <div className="text-xs font-semibold text-slate-900 flex items-center gap-1.5">
                    <span>Deterministic Fixture</span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-indigo-100 text-indigo-800 rounded font-bold">REPRODUCIBLE</span>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Local deterministic provider. Tests all schemas and validations offline.
                  </p>
                </div>
              </label>

              <label
                className={`flex items-start gap-3 p-3.5 border rounded-lg cursor-pointer transition ${
                  providerType === 'claude'
                    ? 'border-indigo-600 bg-indigo-50/50'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <input
                  type="radio"
                  name="provider"
                  value="claude"
                  checked={providerType === 'claude'}
                  onChange={() => setProviderType('claude')}
                  className="mt-0.5 text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <div className="text-xs font-semibold text-slate-900 flex items-center gap-1.5">
                    <span>Claude Vision</span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-700 rounded font-bold">LIVE AI</span>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Live multimodal extraction using Claude Sonnet 5.5 (requires ANTHROPIC_API_KEY).
                  </p>
                </div>
              </label>
            </div>
          </div>

          {/* Human Review Governance Guard */}
          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              Verification & Clearance Policy
            </label>
            <div className="p-3.5 border border-slate-200 rounded-lg bg-slate-50/50 h-[88px] flex flex-col justify-center">
              <div className="flex items-center gap-2 text-indigo-900 font-semibold text-xs">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Strict Human Approval Gate Enforced</span>
              </div>
              <p className="text-[11px] text-slate-600 mt-1 leading-snug">
                Simulations halt at <strong className="text-slate-800">REVIEW_REQUIRED</strong>. To verify and export, open the review interface and confirm or correct mandatory fields as an authorized reviewer.
              </p>
            </div>
          </div>
        </div>

        {/* Scenario Selection Grid */}
        <div className="space-y-3 pt-2">
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
            Select Scenario To Simulate
          </label>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* All in One */}
            <div
              onClick={() => setSelectedScenario('ALL')}
              className={`p-4 border rounded-xl cursor-pointer transition ${
                selectedScenario === 'ALL'
                  ? 'border-indigo-600 bg-indigo-50/40 shadow-sm ring-1 ring-indigo-600'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-indigo-600" />
                  <h4 className="text-sm font-bold text-slate-900">Run Full Demonstration Suite</h4>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-indigo-100 text-indigo-800">
                  5 SCENARIOS
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Simulates all 5 scenarios together, establishing a complete demonstration environment in seconds.
              </p>
            </div>

            {/* Individual Scenarios */}
            {scenarios.map((sc) => (
              <div
                key={sc.code}
                onClick={() => setSelectedScenario(sc.code)}
                className={`p-4 border rounded-xl cursor-pointer transition ${
                  selectedScenario === sc.code
                    ? 'border-indigo-600 bg-indigo-50/40 shadow-sm ring-1 ring-indigo-600'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-900 truncate pr-2">{sc.name}</h4>
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-slate-100 text-slate-700">
                    {sc.shipment_number}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1.5 line-clamp-2">{sc.description}</p>
                <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">Target State:</span>
                  <span className="font-semibold text-slate-700">{sc.expected_status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Latest Simulation Results */}
      {simulationResults.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              Latest Simulation Run Results
            </h2>
            <span className="text-xs text-slate-500 font-mono">
              {simulationResults.length} scenario(s) processed
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {simulationResults.map((r, idx) => (
              <div key={idx} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-100">
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-sm text-slate-900 bg-slate-100 px-2.5 py-1 rounded">
                      {r.shipment_number}
                    </span>
                    <h3 className="font-semibold text-slate-800 text-sm">{r.client_name}</h3>
                    {getStatusBadge(r.status)}
                  </div>

                  <div className="flex items-center gap-2">
                    <Link
                      to={r.workspace_url}
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2.5 py-1.5 rounded-md hover:bg-indigo-100 transition"
                    >
                      <span>Open Workspace</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Link>

                    {r.review_url && (
                      <Link
                        to={r.review_url}
                        className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 hover:text-amber-800 bg-amber-50 px-2.5 py-1.5 rounded-md hover:bg-amber-100 transition"
                      >
                        <span>Human Review</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
                  {/* Generated Docs */}
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1.5">
                    <span className="font-bold text-slate-600 uppercase tracking-wide text-[10px]">
                      Synthetic Triad Docs ({r.documents.length})
                    </span>
                    <div className="space-y-1">
                      {r.documents.map((d) => (
                        <div key={d.id} className="flex items-center justify-between text-slate-700">
                          <span className="truncate max-w-[140px]">{d.filename}</span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {(d.file_size_bytes / 1024).toFixed(1)} KB
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Extraction */}
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1.5">
                    <span className="font-bold text-slate-600 uppercase tracking-wide text-[10px]">
                      Extraction Modality
                    </span>
                    <div className="text-slate-700 space-y-0.5">
                      <div>Provider: <strong className="font-mono text-slate-900">{r.extraction?.provider}</strong></div>
                      <div>Model: <strong className="font-mono text-slate-900">{r.extraction?.model}</strong></div>
                      {r.extraction?.average_confidence && (
                        <div>Confidence: <strong>{(r.extraction.average_confidence * 100).toFixed(1)}%</strong></div>
                      )}
                      {r.extraction && r.extraction.low_confidence_fields.length > 0 && (
                        <div className="text-amber-600 font-semibold">
                          {r.extraction.low_confidence_fields.length} low-confidence field(s)
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Validation Engine */}
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1.5">
                    <span className="font-bold text-slate-600 uppercase tracking-wide text-[10px]">
                      11-Rule Validation Engine
                    </span>
                    <div className="text-slate-700 space-y-0.5">
                      <div>Passed: <strong className="text-emerald-700">{r.validation?.passed_count}</strong> / {r.validation?.total_rules}</div>
                      <div>Failed: <strong className="text-red-700">{r.validation?.failed_count}</strong></div>
                      {r.validation?.notable_discrepancy && (
                        <p className="text-[11px] text-amber-700 font-medium mt-1 leading-snug">
                          {r.validation.notable_discrepancy}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Export Status */}
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1.5">
                    <span className="font-bold text-slate-600 uppercase tracking-wide text-[10px]">
                      Customs Export Snapshot
                    </span>
                    {r.export ? (
                      <div className="text-slate-700 space-y-1">
                        <div className="text-emerald-700 font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Sealed & Exported</span>
                        </div>
                        <div className="truncate font-mono text-[10px] text-slate-500" title={r.export.sha256_checksum || ''}>
                          SHA: {r.export.sha256_checksum?.slice(0, 16)}...
                        </div>
                        {r.export.download_url && (
                          <a
                            href={r.export.download_url}
                            download
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-800"
                          >
                            <Download className="w-3 h-3" />
                            <span>Download CSV</span>
                          </a>
                        )}
                      </div>
                    ) : (
                      <div className="text-slate-400 text-[11px]">
                        Export gated (Pending verification or mandatory reviews).
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Persisted Demo Shipments in Database */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Database className="w-4 h-4 text-slate-500" />
              Persisted Demonstration Consignments
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Live records residing in PostgreSQL. Any change made in Human Review or Workspace reflects here.
            </p>
          </div>
          <span className="text-xs font-mono font-semibold px-2.5 py-1 bg-slate-100 text-slate-700 rounded-md">
            {statusData?.demo_shipments.length || 0} active
          </span>
        </div>

        {statusData?.demo_shipments && statusData.demo_shipments.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Shipment #</th>
                  <th className="py-3 px-4">Client Name</th>
                  <th className="py-3 px-4">Origin</th>
                  <th className="py-3 px-4">Gross Weight</th>
                  <th className="py-3 px-4">Docs</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Export SHA-256</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {statusData.demo_shipments.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900 flex items-center gap-1.5">
                      <span>{s.shipment_number}</span>
                      <span className="text-[9px] px-1.5 py-0.2 bg-amber-100 text-amber-800 rounded font-bold">DEMO</span>
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-800 max-w-[200px] truncate">
                      {s.client_name}
                    </td>
                    <td className="py-3 px-4 text-slate-600">{s.origin_country}</td>
                    <td className="py-3 px-4 font-mono">
                      {s.gross_weight_kg ? `${s.gross_weight_kg.toLocaleString()} kg` : '—'}
                    </td>
                    <td className="py-3 px-4 font-semibold">{s.documents_count}</td>
                    <td className="py-3 px-4">{getStatusBadge(s.status)}</td>
                    <td className="py-3 px-4 font-mono text-[10px] text-slate-400">
                      {s.export_sha256 ? `${s.export_sha256.slice(0, 12)}...` : '—'}
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <Link
                        to={`/shipments/${s.id}`}
                        className="text-indigo-600 hover:text-indigo-800 font-medium hover:underline"
                      >
                        Workspace
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-slate-500 text-xs">
            No demonstration consignments currently in database. Click <strong>Start Simulation</strong> above to generate authentic test workflows.
          </div>
        )}
      </div>
    </div>
  )
}
