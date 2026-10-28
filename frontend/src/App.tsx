import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider } from "./app/AuthContext";
import { IdentityProvider } from "./app/IdentityContext";
import type { AuthCredentials } from "./api/client";
import { RequireAuth } from "./app/RequireAuth";
import { WorkflowProvider, useWorkflow } from "./app/WorkflowContext";
import { WorkflowSessionSync } from "./app/WorkflowSessionSync";
import { AnalysisProvider } from "./app/AnalysisContext";
import { AssessmentProvider } from "./app/AssessmentContext";
import { LandingPage } from "./features/landing/LandingPage";
import { SessionPage } from "./features/shipment/SessionPage";
import { AuthCallbackPage } from "./features/auth/AuthCallbackPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { SetupPasswordPage } from "./features/auth/SetupPasswordPage";
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
import { RegulationAdminPage } from "./features/regulatory/RegulationAdminPage";
import { AskPage } from "./features/ask/AskPage";

function LegacyWorkspaceRoute() {
  const { record } = useWorkflow();
  const location = useLocation();
  // Only the unqualified route has an unambiguous canonical target.
  // Nested legacy routes remain mounted below for compatibility.
  if (location.pathname === "/workspace" && record?.case_id) {
    return <Navigate to={`/shipments/${encodeURIComponent(record.case_id)}`} replace />;
  }
  return <WorkspacePage />;
}

/**
 * Application routes (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * - `/` — public landing page (dedicated chrome).
 * - `/session` — email magic-link sign-in (plus local-development
 *   tenant field); also served as `/signin`, the public Sign In
 *   destination. Accepts an allow-listed `?next=` return path.
 * - `/auth/callback` — Supabase PKCE callback destination.
 * - `/reset-password` — Supabase password-recovery destination; sets
 *   a new password once the recovery session is established.
 * - `/register` — organization self-service registration (public); also
 *   served as `/signup`. Confirms the email by magic link and creates
 *   an active workspace; it is not a regulatory verification.
 * - `/start` — new shipment (human profile; identifiers generated).
 * - `/settings` — utility surface (session, theme, honest unavailable states).
 * - `/dashboard`, `/shipments`, `/shipments/:caseId`,
 *   `/shipments/:caseId/report` — canonical shipment workspace;
 *   nested `/workspace/*` paths remain compatibility screens. The
 *   unqualified `/workspace` redirects when a saved case is available.
 *   Workspace routes are gated by `RequireAuth` (unauthenticated visitors
 *   return to `/session`, never to external destinations).
 */
export function App({ authInitial }: { authInitial?: Partial<AuthCredentials> }) {
  return (
    <AuthProvider initial={authInitial}>
      <IdentityProvider>
        <WorkflowProvider>
          <AnalysisProvider>
            <AssessmentProvider>
              <WorkflowSessionSync />
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/session" element={<SessionPage />} />
              <Route path="/signin" element={<Navigate to="/session" replace />} />
              <Route path="/auth/callback" element={<AuthCallbackPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/setup-password" element={<SetupPasswordPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/signup" element={<Navigate to="/register" replace />} />
              <Route path="/start" element={<RequireAuth><NewShipmentPage /></RequireAuth>} />
              <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
              <Route
                path="/dashboard"
                element={
                  <RequireAuth>
                    <DashboardPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/regulatory"
                element={
                  <RequireAuth>
                    <AuthenticatedShell crumbs={[{ label: "Regulatory administration" }]}>
                      <RegulationAdminPage />
                    </AuthenticatedShell>
                  </RequireAuth>
                }
              />
              <Route
                path="/shipments"
                element={
                  <RequireAuth>
                    <AuthenticatedShell crumbs={[{ label: "View Shipments" }]}>
                      <ShipmentsPage />
                    </AuthenticatedShell>
                  </RequireAuth>
                }
              />
              <Route
                path="/shipments/:caseId"
                element={
                  <RequireAuth>
                    <ShipmentWorkspacePage />
                  </RequireAuth>
                }
              />
              <Route
                path="/shipments/:caseId/report"
                element={
                  <RequireAuth>
                    <HistoricalReportPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/workspace"
                element={
                  <RequireAuth>
                    <LegacyWorkspaceRoute />
                  </RequireAuth>
                }
              >
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
              <Route path="/ask" element={<RequireAuth><AskPage /></RequireAuth>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AssessmentProvider>
        </AnalysisProvider>
      </WorkflowProvider>
      </IdentityProvider>
    </AuthProvider>
  );
}
