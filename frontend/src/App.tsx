import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./app/AuthContext";
import { WorkflowProvider } from "./app/WorkflowContext";
import { AnalysisProvider } from "./app/AnalysisContext";
import { AssessmentProvider } from "./app/AssessmentContext";
import { LandingPage } from "./features/landing/LandingPage";
import { SessionPage } from "./features/shipment/SessionPage";
import { NewShipmentPage } from "./features/shipment/NewShipmentPage";
import { WorkspacePage } from "./features/shipment/WorkspacePage";
import { WorkspaceOverview } from "./features/shipment/WorkspaceOverview";
import { ShipmentsPage } from "./features/shipment/ShipmentsPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { HistoricalReportPage } from "./features/shipment/HistoricalReportPage";
import { ShipmentWorkspacePage } from "./features/workspace/ShipmentWorkspacePage";
import { AuthenticatedShell } from "./shell/AuthenticatedShell";
import { DocumentsPage } from "./features/evidence/DocumentsPage";
import { ShipmentInfoPage } from "./features/shipment/ShipmentInfoPage";
import { RequirementsPage } from "./features/requirements/RequirementsPage";
import { EvidencePage } from "./features/evidence/EvidencePage";
import { GapsPage } from "./features/evidence/GapsPage";
import { AdditionalEvidencePage } from "./features/evidence/AdditionalEvidencePage";
import { AnalysisPage } from "./features/analysis/AnalysisPage";
import { FindingsPage } from "./features/analysis/FindingsPage";
import { AssessmentPage } from "./features/assessment/AssessmentPage";
import { FinalReviewPage } from "./features/assessment/FinalReviewPage";
import { PackagePage } from "./features/assessment/PackagePage";
import { ReportPage } from "./features/assessment/ReportPage";
import { HistoryPage } from "./features/assessment/HistoryPage";
import { SettingsPage } from "./features/settings/SettingsPage";

/**
 * Application routes (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * - `/` — public landing page (dedicated chrome).
 * - `/session` — session setup (bearer token or dev tenant); also served
 *   as `/signin`, the public Sign In destination.
 * - `/start` — new shipment (human profile; identifiers generated); also
 *   served as `/signup`, the public Get Started destination.
 * - `/settings` — utility surface (session, theme, honest unavailable states).
 * - `/dashboard` — authenticated resumption workspace.
 * - `/shipments` — searchable archive inside the shell.
 * - `/shipments/:caseId` — shipment workspace.
 * - `/shipments/:caseId/report` — read-only historical report.
 * - `/workspace` — established deep-link tree (legacy shell surfaces
 *   migrate to the shipment workspace progressively).
 */
export function App() {
  return (
    <AuthProvider>
      <WorkflowProvider>
        <AnalysisProvider>
          <AssessmentProvider>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/session" element={<SessionPage />} />
              <Route path="/signin" element={<Navigate to="/session" replace />} />
              <Route path="/start" element={<NewShipmentPage />} />
              <Route path="/signup" element={<Navigate to="/start" replace />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route
                path="/shipments"
                element={
                  <AuthenticatedShell crumbs={[{ label: "View Shipments" }]}>
                    <ShipmentsPage />
                  </AuthenticatedShell>
                }
              />
              <Route path="/shipments/:caseId" element={<ShipmentWorkspacePage />} />
              <Route path="/shipments/:caseId/report" element={<HistoricalReportPage />} />
              <Route path="/workspace" element={<WorkspacePage />}>
                <Route index element={<WorkspaceOverview />} />
                <Route path="shipments" element={<ShipmentsPage />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="requirements" element={<RequirementsPage />} />
                <Route path="assessment" element={<AssessmentPage />} />
                <Route path="info" element={<ShipmentInfoPage />} />
                <Route path="evidence" element={<EvidencePage />} />
                <Route path="gaps" element={<GapsPage />} />
                <Route path="additional-evidence" element={<AdditionalEvidencePage />} />
                <Route path="analysis" element={<AnalysisPage />} />
                <Route path="review" element={<FindingsPage />} />
                <Route path="final-review" element={<FinalReviewPage />} />
                <Route path="package" element={<PackagePage />} />
                <Route path="report/:reportId" element={<ReportPage />} />
                <Route path="history" element={<HistoryPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AssessmentProvider>
        </AnalysisProvider>
      </WorkflowProvider>
    </AuthProvider>
  );
}
