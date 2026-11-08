import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AuditHistoryPage } from '../pages/AuditHistoryPage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as reviewsApi from '../api/reviews'

vi.mock('../api/reviews', () => ({
  fetchGlobalAuditHistory: vi.fn(),
}))

describe('AuditHistoryPage Provenance & Audit Trail Display', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    vi.clearAllMocks()
  })

  it('renders prominent DEMO FIXTURE badge and synthetic attribution for seeded records', async () => {
    vi.mocked(reviewsApi.fetchGlobalAuditHistory).mockResolvedValue({
      total: 2,
      items: [
        {
          id: 'rev-demo-1',
          shipment_id: 'shp-24816-uuid',
          document_id: 'doc-ci-uuid',
          extraction_id: 'ext-ci-uuid',
          field_name: 'invoice_number',
          action: 'CONFIRMED',
          provenance: 'DEMO_SEED',
          original_value: 'INV-SIE-2026-104',
          corrected_value: 'INV-SIE-2026-104',
          reason: null,
          reviewer_id: 'usr-manager-uuid',
          reviewer_name: 'Documentation Manager',
          reviewer_email: 'manager@cargolens.in',
          reviewer_role: 'DOCUMENTATION_MANAGER',
          created_at: '2026-11-06T09:29:13.562743Z',
        },
        {
          id: 'rev-human-1',
          shipment_id: 'shp-live-uuid',
          document_id: 'doc-pl-uuid',
          extraction_id: 'ext-pl-uuid',
          field_name: 'gross_weight_kg',
          action: 'CORRECTED',
          provenance: 'USER_ACTION',
          original_value: '3120.00',
          corrected_value: '3165.00',
          reason: 'Adjusted per weighbridge certificate',
          reviewer_id: 'usr-exec-uuid',
          reviewer_name: 'Rajesh Sharma',
          reviewer_email: 'rajesh@cargolens.in',
          reviewer_role: 'DOCUMENTATION_EXECUTIVE',
          created_at: '2026-11-06T10:15:00.000000Z',
        },
      ],
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AuditHistoryPage />
        </MemoryRouter>
      </QueryClientProvider>
    )

    // Wait for the table to render
    expect(await screen.findByText('Review & Verification Audit Trail')).toBeInTheDocument()

    // 1. Verify seeded record shows DEMO FIXTURE badge
    const demoBadges = await screen.findAllByTestId('demo-fixture-badge')
    expect(demoBadges.length).toBeGreaterThanOrEqual(1)
    expect(demoBadges[0]).toHaveTextContent('DEMO FIXTURE — NOT A REAL HUMAN APPROVAL')

    // 2. Verify synthetic reviewer attribution
    expect(screen.getByText('Demonstration Fixture')).toBeInTheDocument()
    expect(screen.getByText(/Attributed to manager@cargolens\.in/)).toBeInTheDocument()
    expect(screen.getByText('Automated demonstration dataset')).toBeInTheDocument()

    // 3. Verify genuine human review displays Human Review
    expect(screen.getByText('Human Review')).toBeInTheDocument()
    expect(screen.getByText('Rajesh Sharma')).toBeInTheDocument()
    expect(screen.getByText('Adjusted per weighbridge certificate')).toBeInTheDocument()

    // 4. Verify original and corrected values preserved
    expect(screen.getByText('INV-SIE-2026-104')).toBeInTheDocument()
    expect(screen.getByText('3120.00')).toBeInTheDocument()
    expect(screen.getByText('3165.00')).toBeInTheDocument()
  })
})
