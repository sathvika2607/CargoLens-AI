import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ShipmentListPage } from './pages/ShipmentListPage'
import { CreateShipmentPage } from './pages/CreateShipmentPage'
import { ShipmentWorkspacePage } from './pages/ShipmentWorkspacePage'
import { DocumentReviewPage } from './pages/DocumentReviewPage'
import { ValidationIssuesPage } from './pages/ValidationIssuesPage'
import { AuditHistoryPage } from './pages/AuditHistoryPage'
import { ManagerCommandCenterPage } from './pages/ManagerCommandCenterPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { CustomsExportCenterPage } from './pages/CustomsExportCenterPage'
import { DemoSimulationCenterPage } from './pages/DemoSimulationCenterPage'
import { SettingsPage } from './pages/SettingsPage'
import { NotFoundPage } from './pages/NotFoundPage'

// Create TanStack Query client with standard enterprise defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public Auth Routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Screen 2: Executive Operations Dashboard */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <DashboardPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 3: Shipment Registry */}
            <Route
              path="/shipments"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <ShipmentListPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 4: Dedicated Create Consignment Screen */}
            <Route
              path="/shipments/create"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <CreateShipmentPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 5, 6, 7, 9, 10, 13: Shipment Workspace & Sub-Routes */}
            <Route
              path="/shipments/:id"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <ShipmentWorkspacePage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            <Route
              path="/shipments/:id/:tab"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <ShipmentWorkspacePage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 8: Human Review Workspace */}
            <Route
              path="/review"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <DocumentReviewPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            <Route
              path="/review/:shipmentId"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <DocumentReviewPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            <Route
              path="/review/:shipmentId/:documentId"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <DocumentReviewPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 9: Cross-Document Validation Issues Center */}
            <Route
              path="/validations"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <ValidationIssuesPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 10: Review History & Audit Trail */}
            <Route
              path="/audit-history"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <AuditHistoryPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 11: Manager Command Center (Manager Only) */}
            <Route
              path="/manager"
              element={
                <ProtectedRoute requiredRole="DOCUMENTATION_MANAGER">
                  <AppShell>
                    <ManagerCommandCenterPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 12: Operations & Customs Analytics */}
            <Route
              path="/analytics"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <AnalyticsPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 13: Customs Export Center */}
            <Route
              path="/exports"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <CustomsExportCenterPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 15: Demo Simulation Center */}
            <Route
              path="/simulation"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <DemoSimulationCenterPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Screen 14: System Settings & Infrastructure */}
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <SettingsPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />

            {/* Fallback 404 Route */}
            <Route
              path="*"
              element={
                <AppShell>
                  <NotFoundPage />
                </AppShell>
              }
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
