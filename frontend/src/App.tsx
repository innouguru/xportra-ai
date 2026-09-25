import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./app/AuthContext";
import { WorkflowProvider } from "./app/WorkflowContext";
import { AnalysisProvider } from "./app/AnalysisContext";
import { AssessmentProvider } from "./app/AssessmentContext";
import { SessionPage } from "./features/shipment/SessionPage";
import { NewShipmentPage } from "./features/shipment/NewShipmentPage";
import { WorkspacePage } from "./features/shipment/WorkspacePage";
import { WorkspaceOverview } from "./features/shipment/WorkspaceOverview";
import { ShipmentInfoPage } from "./features/shipment/ShipmentInfoPage";
import { RequirementsPage } from "./features/requirements/RequirementsPage";
import { EvidencePage } from "./features/evidence/EvidencePage";
import { GapsPage } from "./features/evidence/GapsPage";
import { AdditionalEvidencePage } from "./features/evidence/AdditionalEvidencePage";
import { AnalysisPage } from "./features/analysis/AnalysisPage";
import { FindingsPage } from "./features/analysis/FindingsPage";
import { FinalReviewPage } from "./features/assessment/FinalReviewPage";
import { PackagePage } from "./features/assessment/PackagePage";
import { ReportPage } from "./features/assessment/ReportPage";
import { HistoryPage } from "./features/assessment/HistoryPage";

/**
 * Application routes (Passes 1–3).
 *
 * - `/` — New shipment (Screen 1).
 * - `/session` — session setup (bearer token or dev tenant).
 * - `/workspace` — shipment workspace shell; `info`,
 *   `requirements`, `evidence`, `gaps`,
 *   `additional-evidence`, `analysis`, `review`,
 *   `final-review`, `package`, `report/:reportId`,
 *   and `history` sections.
 */
export function App() {
  return (
    <AuthProvider>
      <WorkflowProvider>
        <AnalysisProvider>
          <AssessmentProvider>
            <Routes>
              <Route path="/" element={<NewShipmentPage />} />
              <Route path="/session" element={<SessionPage />} />
              <Route path="/workspace" element={<WorkspacePage />}>
                <Route index element={<WorkspaceOverview />} />
                <Route path="info" element={<ShipmentInfoPage />} />
                <Route path="requirements" element={<RequirementsPage />} />
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
