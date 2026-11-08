import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DocumentReviewPage } from '../pages/DocumentReviewPage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as shipmentsApi from '../api/shipments'
import * as documentsApi from '../api/documents'
import * as extractionsApi from '../api/structuredExtractions'
import * as reviewsApi from '../api/reviews'

vi.mock('../api/shipments', () => ({
  getShipment: vi.fn(),
  listShipments: vi.fn(),
}))

vi.mock('../api/documents', () => ({
  listDocuments: vi.fn(),
  fetchDocumentPageImage: vi.fn(),
  downloadDocument: vi.fn(),
}))

vi.mock('../api/structuredExtractions', () => ({
  getLatestStructuredExtraction: vi.fn(),
}))

vi.mock('../api/reviews', () => ({
  fetchShipmentReviews: vi.fn(),
  submitFieldReview: vi.fn(),
}))

vi.mock('../api/validations', () => ({
  runShipmentValidations: vi.fn().mockResolvedValue({}),
}))

describe('DocumentReviewPage Component', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    vi.clearAllMocks()
    vi.mocked(reviewsApi.submitFieldReview).mockResolvedValue({
      id: 'rev-1',
      shipment_id: 'ship-100',
      document_id: 'doc-100',
      extraction_id: 'ext-100',
      field_name: 'invoice_number',
      action: 'CONFIRMED',
      original_value: 'INV-2026-8899',
      corrected_value: null,
      reason: 'Confirmed by human reviewer',
      reviewer_id: 'u-1',
      created_at: new Date().toISOString(),
    })
  })

  it('renders split screen viewer and extracted fields with confirmation buttons', async () => {
    vi.mocked(shipmentsApi.getShipment).mockResolvedValue({
      id: 'ship-100',
      shipment_number: 'SHP-2026-REVIEW-01',
      client_name: 'Tata Steel Global',
      origin_country: 'Japan',
      product_description: null,
      quantity: null,
      unit_price: null,
      currency: null,
      gross_weight_kg: null,
      status: 'REVIEW_REQUIRED',
      created_at: '2026-01-01',
      created_by: 'u-1',
      updated_at: '2026-01-01',
    })

    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [
        {
          id: 'doc-100',
          shipment_id: 'ship-100',
          document_type: 'COMMERCIAL_INVOICE',
          original_filename: 'Invoice_001.pdf',
          mime_type: 'application/pdf',
          file_extension: 'pdf',
          file_size_bytes: 1024,
          sha256_checksum: 'abc1234',
          version: 1,
          uploaded_by: 'u-1',
          processing_status: 'COMPLETED',
          is_active: true,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
      ],
      total: 1,
    })

    vi.mocked(documentsApi.fetchDocumentPageImage).mockResolvedValue({
      imageUrl: 'blob:http://localhost/test-image',
      totalPages: 3,
      currentPage: 1,
    })

    vi.mocked(extractionsApi.getLatestStructuredExtraction).mockResolvedValue({
      id: 'ext-100',
      document_id: 'doc-100',
      document_type: 'COMMERCIAL_INVOICE',
      attempt_number: 1,
      status: 'COMPLETED',
      provider: 'claude',
      model: 'claude-sonnet-5-5',
      extraction_mode: 'vision',
      total_page_count: 3,
      processed_page_count: 3,
      extracted_data: {
        invoice_number: {
          value: 'INV-2026-8899',
          confidence: 0.98,
          source_page_number: 1,
          evidence_text: 'Invoice No: INV-2026-8899',
        },
        grand_total: {
          value: 45000.5,
          confidence: 0.92,
          source_page_number: 2,
          evidence_text: 'Total Amount Payable: USD 45,000.50',
        },
      },
      created_at: '2026-01-01',
    })

    vi.mocked(reviewsApi.fetchShipmentReviews).mockResolvedValue({
      items: [],
      total: 0,
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/review/ship-100/doc-100']}>
          <Routes>
            <Route path="/review/:shipmentId/:documentId" element={<DocumentReviewPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('SHP-2026-REVIEW-01')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
    expect(screen.getByText('invoice_number')).toBeInTheDocument()
    expect(screen.getByText('INV-2026-8899')).toBeInTheDocument()
    expect(screen.getByText('98%')).toBeInTheDocument()
    expect(screen.getByText('grand_total')).toBeInTheDocument()
    expect(screen.getByText('45000.5')).toBeInTheDocument()

    // Test clicking Confirm button
    const confirmButtons = screen.getAllByRole('button', { name: /Confirm/i })
    expect(confirmButtons.length).toBeGreaterThan(0)
    fireEvent.click(confirmButtons[0])

    await waitFor(() => {
      expect(reviewsApi.submitFieldReview).toHaveBeenCalledWith(
        'ship-100',
        'doc-100',
        expect.objectContaining({
          action: 'CONFIRMED',
          field_name: 'invoice_number',
        })
      )
    })
  })

  it('renders multi-page PDF in vertically scrollable container allowing every page to be reached', async () => {
    // Mock scrollIntoView in jsdom
    const scrollIntoViewMock = vi.fn()
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock

    vi.mocked(shipmentsApi.getShipment).mockResolvedValue({
      id: 'ship-100',
      shipment_number: 'SHP-2026-MULTI',
      client_name: 'Tata Steel Global',
      origin_country: 'Japan',
      product_description: null,
      quantity: null,
      unit_price: null,
      currency: null,
      gross_weight_kg: null,
      status: 'REVIEW_REQUIRED',
      created_at: '2026-01-01',
      created_by: 'u-1',
      updated_at: '2026-01-01',
    })

    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [
        {
          id: 'doc-multi-1',
          shipment_id: 'ship-100',
          document_type: 'COMMERCIAL_INVOICE',
          original_filename: 'MultiPage_Invoice.pdf',
          mime_type: 'application/pdf',
          file_extension: 'pdf',
          file_size_bytes: 4096,
          sha256_checksum: 'multihash123',
          version: 1,
          uploaded_by: 'u-1',
          processing_status: 'COMPLETED',
          is_active: true,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
      ],
      total: 1,
    })

    vi.mocked(documentsApi.fetchDocumentPageImage).mockImplementation(async (_sId, _dId, page) => ({
      imageUrl: `blob:http://localhost/test-image-page-${page}`,
      totalPages: 3,
      currentPage: page,
    }))

    vi.mocked(extractionsApi.getLatestStructuredExtraction).mockResolvedValue({
      id: 'ext-multi-1',
      document_id: 'doc-multi-1',
      document_type: 'COMMERCIAL_INVOICE',
      attempt_number: 1,
      status: 'COMPLETED',
      provider: 'claude',
      model: 'claude-sonnet-5-5',
      extraction_mode: 'vision',
      total_page_count: 3,
      processed_page_count: 3,
      extracted_data: {
        invoice_number: {
          value: 'INV-2026-MULTI-01',
          confidence: 0.99,
          source_page_number: 1,
          evidence_text: 'Invoice No: INV-2026-MULTI-01',
        },
        item_summary: {
          value: 'Steel Coils Grade A',
          confidence: 0.95,
          source_page_number: 2,
          evidence_text: 'Description: Steel Coils Grade A',
        },
        grand_total: {
          value: 120000.0,
          confidence: 0.98,
          source_page_number: 3,
          evidence_text: 'Total Amount: USD 120,000.00',
        },
      },
      created_at: '2026-01-01',
    })

    vi.mocked(reviewsApi.fetchShipmentReviews).mockResolvedValue({
      items: [],
      total: 0,
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/review/ship-100/doc-multi-1']}>
          <Routes>
            <Route path="/review/:shipmentId/:documentId" element={<DocumentReviewPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(await screen.findByText('SHP-2026-MULTI')).toBeInTheDocument()

    // 1. Verify scroll container presence and overflow-y styling
    const scrollContainer = screen.getByTestId('pdf-viewer-scroll-container')
    expect(scrollContainer).toBeInTheDocument()
    expect(scrollContainer.className).toContain('overflow-y-auto')
    expect(scrollContainer.className).toContain('pdf-viewer-scroller')

    // 2. Verify all 3 pages are rendered concurrently in the DOM
    const page1 = await screen.findByTestId('pdf-page-1')
    const page2 = await screen.findByTestId('pdf-page-2')
    const page3 = await screen.findByTestId('pdf-page-3')
    expect(page1).toBeInTheDocument()
    expect(page2).toBeInTheDocument()
    expect(page3).toBeInTheDocument()

    // 3. Verify Page Navigation toolbar button triggers scroll
    const nextButton = screen.getByTitle('Next Page')
    expect(nextButton).not.toBeDisabled()
    fireEvent.click(nextButton)
    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })

    // 4. Verify clicking jump to page on extracted field jumps to target page
    const jumpBadge = screen.getByTitle('Jump viewer to Page 3')
    expect(jumpBadge).toBeInTheDocument()
    fireEvent.click(jumpBadge)
    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
  })
})
