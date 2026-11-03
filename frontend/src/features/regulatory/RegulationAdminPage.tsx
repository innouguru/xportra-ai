import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { CandidateReviewPage } from "./CandidateReviewPage";
import { CandidatesTab } from "./CandidatesTab";
import { DetailsTab } from "./DetailsTab";
import { DocumentsTab } from "./DocumentsTab";
import { GovernanceTab } from "./GovernanceTab";
import { IngestionTab } from "./IngestionTab";
import { RegisterSourcePage } from "./RegisterSourcePage";
import { SourceLayout } from "./SourceLayout";
import { SourceListPage } from "./SourceListPage";
import { REGULATORY_BASE, sourcePath } from "./regulatoryUi";
import "./regulatory.css";

/**
 * Regulatory administration surface (authorized staff only).
 *
 * Mount at ``/regulatory/*``. Routes:
 *
 *   /regulatory                              source list
 *   /regulatory/new                          register a source
 *   /regulatory/:sourceId/documents          upload + uploaded files (default)
 *   /regulatory/:sourceId/ingestion          ingestion jobs and retry
 *   /regulatory/:sourceId/candidates         extracted candidates
 *   /regulatory/:sourceId/governance         governance flags
 *   /regulatory/:sourceId/details            provenance + withdrawal
 *   /regulatory/:sourceId/candidates/:id     Stage A / Stage B review
 *
 * The server is the authority for every privileged action: each
 * mutation requires an active global staff grant (``GRANT_MANAGE``,
 * ``STAGE_A_VERIFY`` or ``STAGE_B_APPROVE``) enforced server-side;
 * this surface only reflects the backend's decisions and failures.
 * Authorization denials are surfaced as errors — never mocked as
 * success. All states, supersession links, extraction outcomes, and
 * governance flags are displayed verbatim; nothing is inferred.
 * No operation here publishes a requirement or marks it
 * exporter-applicable.
 */
export function RegulationAdminPage() {
  return (
    <Routes>
      <Route index element={<SourceListPage />} />
      <Route path="new" element={<RegisterSourcePage />} />
      <Route path=":sourceId" element={<SourceLayout />}>
        <Route index element={<DefaultTab />} />
        <Route path="documents" element={<DocumentsTab />} />
        <Route path="ingestion" element={<IngestionTab />} />
        <Route path="candidates" element={<CandidatesTab />} />
        <Route path="governance" element={<GovernanceTab />} />
        <Route path="details" element={<DetailsTab />} />
      </Route>
      <Route
        path=":sourceId/candidates/:candidateId"
        element={<CandidateReviewPage />}
      />
      <Route path="*" element={<Navigate to={REGULATORY_BASE} replace />} />
    </Routes>
  );
}

/** ``/regulatory/:sourceId`` opens on the documents step. */
function DefaultTab() {
  const { sourceId = "" } = useParams();
  return <Navigate to={sourcePath(sourceId, "documents")} replace />;
}
