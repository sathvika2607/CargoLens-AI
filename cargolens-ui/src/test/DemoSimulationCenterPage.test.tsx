import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DemoSimulationCenterPage } from '../pages/DemoSimulationCenterPage'
import * as simulationApi from '../api/simulation'
import * as AuthContext from '../context/AuthContext'

vi.mock('../api/simulation', () => ({
  getSimulationScenarios: vi.fn(),
  getSimulationStatus: vi.fn(),
  runSimulation: vi.fn(),
  resetSimulation: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

describe('DemoSimulationCenterPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(AuthContext.useAuth).mockReturnValue({
      user: {
        id: 'mgr-1',
        email: 'manager@cargolens.in',
        full_name: 'Anita Roy',
        role: 'DOCUMENTATION_MANAGER',
        is_active: true,
        created_at: '2026-01-01',
      },
      isAuthenticated: true,
      isManager: true,
      isExecutive: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })

    vi.mocked(simulationApi.getSimulationScenarios).mockResolvedValue({
      scenarios: [
        {
          id: 'A',
          code: 'COMPLETE_WORKFLOW',
          name: 'Scenario A: Complete Document Workflow',
          shipment_number: 'SHP-DEMO-001',
          client_name: 'Apex Solar Technologies India [DEMO]',
          description: 'Full triad of Commercial Invoice, Packing List, and Bill of Lading with consistent weights.',
          expected_status: 'REVIEW_REQUIRED',
          expected_validation_outcome: '11/11 Rules Passed (Clean — Awaiting Human Review)',
          triad_documents: ['Commercial Invoice', 'Packing List', 'Bill of Lading'],
        },
        {
          id: 'B',
          code: 'WEIGHT_DISCREPANCY',
          name: 'Scenario B: 45 kg Gross Weight Discrepancy',
          shipment_number: 'SHP-24811',
          client_name: 'Lumileds Global Trading [DEMO]',
          description: 'Commercial Invoice declares 3,120 kg, Packing List declares 3,165 kg.',
          expected_status: 'REVIEW_REQUIRED',
          expected_validation_outcome: 'GrossWeightConsistencyRule Failed (45 kg Mismatch)',
          triad_documents: ['Commercial Invoice', 'Packing List', 'Bill of Lading'],
        },
      ],
      environment: 'development',
      allow_simulation: true,
      anthropic_configured: false,
      anthropic_model: 'claude-sonnet-5-5',
      default_provider: 'fixture',
    })

    vi.mocked(simulationApi.getSimulationStatus).mockResolvedValue({
      environment: 'development',
      allow_simulation: true,
      anthropic_configured: false,
      anthropic_model: 'claude-sonnet-5-5',
      total_demo_shipments: 1,
      demo_shipments: [
        {
          id: 'demo-shp-1',
          shipment_number: 'SHP-24811',
          client_name: 'Lumileds Global Trading [DEMO]',
          status: 'REVIEW_REQUIRED',
          origin_country: 'China',
          product_description: 'LED panel light 40W',
          gross_weight_kg: 3120.0,
          currency: 'USD',
          documents_count: 3,
          exported: false,
          created_at: '2026-10-15T00:00:00Z',
        },
      ],
    })
  })

  it('renders the Demo Simulation Center with title, DEMONSTRATION DATA badge, and scenarios', async () => {
    render(
      <MemoryRouter>
        <DemoSimulationCenterPage />
      </MemoryRouter>
    )

    expect(await screen.findByText(/CargoLens AI — Demo Simulation Center/i)).toBeInTheDocument()
    expect(screen.getByText(/DEMONSTRATION DATA & TEST LAB/i)).toBeInTheDocument()
    expect(await screen.findByText(/Scenario A: Complete Document Workflow/i)).toBeInTheDocument()
    expect(screen.getByText(/Scenario B: 45 kg Gross Weight Discrepancy/i)).toBeInTheDocument()
    expect(screen.getAllByText('SHP-24811').length).toBeGreaterThan(0)
  })

  it('allows manager to execute simulation and displays pipeline results', async () => {
    vi.mocked(simulationApi.runSimulation).mockResolvedValue({
      success: true,
      message: 'Successfully executed demonstration simulation',
      provider_used: 'development-fixture',
      model_used: 'fixture-v1',
      duration_seconds: 1.25,
      results: [
        {
          scenario_type: 'WEIGHT_DISCREPANCY',
          shipment_id: 'demo-shp-1',
          shipment_number: 'SHP-24811',
          client_name: 'Lumileds Global Trading [DEMO]',
          status: 'REVIEW_REQUIRED',
          documents: [
            {
              id: 'doc-1',
              document_type: 'COMMERCIAL_INVOICE',
              filename: 'INV-2026-24811.pdf',
              file_size_bytes: 4096,
              sha256_checksum: 'a'.repeat(64),
              status: 'COMPLETED',
            },
          ],
          extraction: {
            provider: 'development-fixture',
            model: 'fixture-v1',
            status: 'COMPLETED',
            average_confidence: 0.98,
            low_confidence_fields: [],
            missing_fields: [],
          },
          validation: {
            total_rules: 11,
            passed_count: 10,
            failed_count: 1,
            missing_data_count: 0,
            has_blocking_failures: true,
            notable_discrepancy: 'Gross weight mismatch: 45.00 kg difference',
          },
          human_reviews_count: 0,
          verification_ready: false,
          export: null,
          workspace_url: '/shipments/demo-shp-1',
          review_url: '/review/demo-shp-1/doc-1',
        },
      ],
    })

    render(
      <MemoryRouter>
        <DemoSimulationCenterPage />
      </MemoryRouter>
    )

    const startBtn = await screen.findByRole('button', { name: /Start Simulation/i })
    expect(startBtn).toBeInTheDocument()

    fireEvent.click(startBtn)

    await waitFor(() => {
      expect(simulationApi.runSimulation).toHaveBeenCalled()
      expect(screen.getByText(/Latest Simulation Run Results/i)).toBeInTheDocument()
      expect(screen.getByText(/Gross weight mismatch: 45.00 kg difference/i)).toBeInTheDocument()
    })
  })

  it('renders read-only notice when user is an executive', async () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      user: {
        id: 'exec-1',
        email: 'executive@cargolens.in',
        full_name: 'Rohan Sharma',
        role: 'DOCUMENTATION_EXECUTIVE',
        is_active: true,
        created_at: '2026-01-01',
      },
      isAuthenticated: true,
      isManager: false,
      isExecutive: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <MemoryRouter>
        <DemoSimulationCenterPage />
      </MemoryRouter>
    )

    expect(await screen.findByText(/Read-Only/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start Simulation/i })).not.toBeInTheDocument()
  })
})
