import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AnalyticsPage } from '../pages/AnalyticsPage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as analyticsApi from '../api/analytics'
import * as authContext from '../context/AuthContext'

vi.mock('../api/analytics', () => ({
  fetchAnalyticsOverview: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

describe('AnalyticsPage Component', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    vi.clearAllMocks()

    vi.mocked(authContext.useAuth).mockReturnValue({
      user: {
        id: 'u-mgr-1',
        email: 'manager@cargolens.in',
        full_name: 'Vikram Mehta',
        role: 'DOCUMENTATION_MANAGER',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      isAuthenticated: true,
      isLoading: false,
      isManager: true,
      isExecutive: false,
      login: vi.fn(),
      logout: vi.fn(),
    })
  })

  it('renders manager analytics KPI metrics, status distribution, and visible SVG chart bars', async () => {
    vi.mocked(analyticsApi.fetchAnalyticsOverview).mockResolvedValue({
      role: 'DOCUMENTATION_MANAGER',
      total_shipments: 42,
      shipments_by_status: {
        CREATED: 5,
        DOCUMENTS_PENDING: 3,
        PROCESSING: 4,
        REVIEW_REQUIRED: 6,
        VERIFIED: 14,
        EXPORTED: 10,
        FAILED: 0,
      },
      status_distribution: [
        { status: 'VERIFIED', count: 14, percentage: 33.3 },
        { status: 'EXPORTED', count: 10, percentage: 23.8 },
        { status: 'REVIEW_REQUIRED', count: 6, percentage: 14.3 },
        { status: 'CREATED', count: 5, percentage: 11.9 },
        { status: 'PROCESSING', count: 4, percentage: 9.5 },
        { status: 'DOCUMENTS_PENDING', count: 3, percentage: 7.1 },
        { status: 'FAILED', count: 0, percentage: 0.0 },
      ],
      total_documents: 120,
      documents_uploaded_by_type: {
        COMMERCIAL_INVOICE: 42,
        PACKING_LIST: 40,
        BILL_OF_LADING: 38,
      },
      documents_by_type: [
        { document_type: 'COMMERCIAL_INVOICE', count: 42 },
        { document_type: 'PACKING_LIST', count: 40 },
        { document_type: 'BILL_OF_LADING', count: 38 },
      ],
      document_processing_status_breakdown: {
        COMPLETED: 118,
        PROCESSING: 2,
        FAILED: 0,
      },
      documents_awaiting_extraction: 2,
      extraction_failures: 0,
      shipments_awaiting_human_review: 6,
      validation_failures_count: 2,
      distinct_shipments_with_discrepancies: 1,
      missing_data_issues_count: 3,
      validation_issues_by_rule: [
        {
          rule_id: 'RULE_GROSS_WEIGHT',
          rule_name: 'Gross Weight Consistency',
          severity: 'ERROR',
          failure_count: 2,
        },
      ],
      validation_discrepancies: [
        {
          id: 'disc-1',
          shipment_id: 'shp-disc-1',
          shipment_number: 'SHP-24811',
          client_name: 'Lumileds Global Trading [DEMO]',
          rule_id: 'RULE_GROSS_WEIGHT',
          rule_name: 'Gross Weight Consistency',
          severity: 'ERROR',
          explanation: 'Gross weight discrepancy detected: 3165 kg vs 3120 kg.',
          created_at: '2026-11-06T09:29:13Z',
        },
      ],
      verified_shipments_count: 14,
      exported_shipments_count: 10,
      volume_over_time: [
        { date: '2026-04-01', count: 8 },
        { date: '2026-04-02', count: 12 },
      ],
      exports_over_time: [
        { date: '2026-04-01', count: 4 },
        { date: '2026-04-02', count: 6 },
      ],
      recent_exports: [
        {
          export_id: 'exp-101',
          shipment_id: 'shp-101',
          shipment_number: 'SHP-JNPT-001',
          template_name: 'STANDARD_CUSTOMS_CLEARANCE',
          exporter_name: 'Rajesh Sharma',
          filename: 'cargolens_export_SHP-JNPT-001.csv',
          row_count: 1,
          sha256_checksum: 'a8b7c6d5e4f3a8b7c6d5e4f3a8b7c6d5e4f3a8b7c6d5e4f3a8b7c6d5e4f3a8b7',
          export_status: 'COMPLETED',
          is_demo: true,
          exported_at: '2026-04-02T10:30:00Z',
        },
      ],
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AnalyticsPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    // Wait for data to load
    expect(await screen.findByText('Consignment Workflow Status Distribution')).toBeInTheDocument()
    expect(screen.getByText('Manager Operations & Customs Analytics')).toBeInTheDocument()
    expect(screen.getAllByText('42').length).toBeGreaterThanOrEqual(1) // Total consignments
    expect(screen.getAllByText('14').length).toBeGreaterThanOrEqual(1) // Verified
    expect(screen.getAllByText('10').length).toBeGreaterThanOrEqual(1) // Exported
    expect(screen.getAllByText('6').length).toBeGreaterThanOrEqual(1) // Needs review
    expect(screen.getByText('120')).toBeInTheDocument() // Documents ingested

    // Check status distribution
    expect(screen.getByText('Verified Compliant')).toBeInTheDocument()
    expect(screen.getByText('(33.3%)')).toBeInTheDocument()

    // Check validation issue breakdown
    expect(screen.getAllByText('Gross Weight Consistency').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('2 issues')).toBeInTheDocument()

    // Check discrepancy detail table with link
    expect(screen.getByText('SHP-24811')).toBeInTheDocument()
    expect(screen.getByText('Lumileds Global Trading [DEMO]')).toBeInTheDocument()
    expect(screen.getByText('Inspect & Review')).toBeInTheDocument()

    // Check Visible SVG Chart Bars for Volume Over Time
    const volBar0 = screen.getByTestId('volume-bar-0')
    const volBar1 = screen.getByTestId('volume-bar-1')
    expect(volBar0).toBeInTheDocument()
    expect(volBar1).toBeInTheDocument()
    expect(parseFloat(volBar0.getAttribute('height') || '0')).toBeGreaterThan(0)
    expect(parseFloat(volBar1.getAttribute('height') || '0')).toBeGreaterThan(0)
    expect(screen.getAllByText('2026-04-01').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('2026-04-02').length).toBeGreaterThanOrEqual(1)

    // Check Visible SVG Chart Bars for Customs Export Activity
    const expBar0 = screen.getByTestId('export-bar-0')
    const expBar1 = screen.getByTestId('export-bar-1')
    expect(expBar0).toBeInTheDocument()
    expect(expBar1).toBeInTheDocument()
    expect(parseFloat(expBar0.getAttribute('height') || '0')).toBeGreaterThan(0)
    expect(parseFloat(expBar1.getAttribute('height') || '0')).toBeGreaterThan(0)

    // Check Recent customs exports table
    expect(screen.getByText('SHP-JNPT-001')).toBeInTheDocument()
    expect(screen.getByText('cargolens_export_SHP-JNPT-001.csv')).toBeInTheDocument()
    expect(screen.getByText('Rajesh Sharma')).toBeInTheDocument()
    expect(screen.getAllByText('DEMONSTRATION FIXTURE DATA').length).toBeGreaterThanOrEqual(1)
  })

  it('renders honest empty states when no shipments exist in the filter period', async () => {
    vi.mocked(analyticsApi.fetchAnalyticsOverview).mockResolvedValue({
      role: 'DOCUMENTATION_MANAGER',
      total_shipments: 0,
      shipments_by_status: {
        CREATED: 0,
        DOCUMENTS_PENDING: 0,
        PROCESSING: 0,
        REVIEW_REQUIRED: 0,
        VERIFIED: 0,
        EXPORTED: 0,
        FAILED: 0,
      },
      status_distribution: [],
      total_documents: 0,
      documents_uploaded_by_type: {},
      documents_by_type: [],
      document_processing_status_breakdown: {},
      documents_awaiting_extraction: 0,
      extraction_failures: 0,
      shipments_awaiting_human_review: 0,
      validation_failures_count: 0,
      distinct_shipments_with_discrepancies: 0,
      missing_data_issues_count: 0,
      validation_issues_by_rule: [],
      validation_discrepancies: [],
      verified_shipments_count: 0,
      exported_shipments_count: 0,
      volume_over_time: [],
      exports_over_time: [],
      recent_exports: [],
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AnalyticsPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('No shipments found for the selected time period.')).toBeInTheDocument()
    expect(screen.getByText('Manager Operations & Customs Analytics')).toBeInTheDocument()
    expect(screen.getByText('Zero Discrepancies Detected')).toBeInTheDocument()
    expect(screen.getByText('No volume activity recorded for this period.')).toBeInTheDocument()
    expect(screen.getByText('No export activity recorded for this period.')).toBeInTheDocument()
  })

  it('allows switching aggregation interval (daily, weekly, monthly)', async () => {
    vi.mocked(analyticsApi.fetchAnalyticsOverview).mockResolvedValue({
      role: 'DOCUMENTATION_MANAGER',
      total_shipments: 8,
      shipments_by_status: {},
      status_distribution: [],
      total_documents: 14,
      documents_uploaded_by_type: {},
      documents_by_type: [],
      document_processing_status_breakdown: {},
      documents_awaiting_extraction: 0,
      extraction_failures: 0,
      shipments_awaiting_human_review: 0,
      validation_failures_count: 0,
      missing_data_issues_count: 0,
      validation_issues_by_rule: [],
      verified_shipments_count: 1,
      exported_shipments_count: 1,
      volume_over_time: [{ date: '2026-11-06', count: 8 }],
      exports_over_time: [{ date: '2026-11-06', count: 1 }],
      recent_exports: [],
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AnalyticsPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    await screen.findByText('Consignment Workflow Status Distribution')
    const weeklyBtn = screen.getByText('Weekly')
    fireEvent.click(weeklyBtn)

    expect(analyticsApi.fetchAnalyticsOverview).toHaveBeenCalledWith(undefined, undefined, 'weekly')
  })
})
