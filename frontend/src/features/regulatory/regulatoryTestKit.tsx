import { vi } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { RegulationAdminPage } from "./RegulationAdminPage";

/** Shared fixtures and a deterministic backend for regulatory page tests. */

export const SID = "11111111-1111-1111-1111-111111111111";
export const CID = "33333333-3333-3333-3333-333333333333";
export const AID = "66666666-6666-6666-6666-666666666666";

export const SOURCE = {
  id: SID,
  authority_id: "99999999-9999-9999-9999-999999999999",
  jurisdiction: "NG",
  title: "Export Guidelines 2026",
  version: "1.0",
  status: "draft",
  effective_date: null,
  publication_date: null,
  source_url: null,
  retrieval_timestamp: null,
  supersedes_source_id: null,
  superseded_by_source_id: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
export const ARTIFACT = {
  id: AID,
  source_id: SID,
  content_type: "application/pdf",
  status: "stored",
  acquired_at: "2026-01-02T00:00:00Z",
};
export const jobRow = (over: Record<string, unknown> = {}) => ({
  id: "55555555-5555-5555-5555-555555555555",
  artifact_id: AID,
  source_id: SID,
  status: "completed",
  attempt_number: 1,
  started_at: null,
  completed_at: null,
  error_details: null,
  parser_version: "v1",
  actor_user_id: null,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  ...over,
});
export const CANDIDATE = {
  id: CID,
  source_id: SID,
  artifact_id: AID,
  normalized_document_id: null,
  requirement_text: "Exporters must hold a phytosanitary certificate.",
  requirement_type: "documentation",
  source_location: { page: 2 },
  position: 1,
  actor: null,
  status: "extracted",
  extraction_outcome: "succeeded",
  parser_version: "v1",
  manual_entry: false,
  reviewer_user_id: null,
  reviewed_at: null,
  ingestion_job_id: null,
  created_at: "2026-01-03T00:00:00Z",
  updated_at: "2026-01-03T00:00:00Z",
};

export interface World {
  artifacts: unknown[];
  jobs: () => unknown[];
  candidates: unknown[];
}

/** Deterministic backend for one source; unmatched URLs fail loudly. */
export function backend(world: World) {
  return vi.fn(async (input: string | Request): Promise<Response> => {
    const url = typeof input === "string" ? input : input.url;
    const ok = (body: unknown) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    const page = (items: unknown[]) => ok({ items, limit: 50, offset: 0, total: items.length });
    if (/\/sources\/[^/]+\/artifacts$/.test(url)) return page(world.artifacts);
    if (/\/sources\/[^/]+\/ingestion-jobs$/.test(url)) return page(world.jobs());
    if (/\/sources\/[^/]+\/candidates$/.test(url)) return page(world.candidates);
    if (/\/sources\/[^/]+\/governance-flags$/.test(url)) return page([]);
    if (/\/candidates\/[^/]+\/stage-a\/history$/.test(url)) return page([]);
    if (/\/candidates\/[^/]+\/stage-b\/history$/.test(url)) return page([]);
    if (/\/candidates\/[^/]+\/stage-a$/.test(url))
      return ok({ id: CID, requirement_id: CID, source_id: SID, stage_a_status: "pending", stage_a_reviewer_user_id: null, stage_a_reviewed_at: null, stage_a_rationale: null });
    if (/\/candidates\/[^/]+\/stage-b$/.test(url))
      return ok({ id: CID, requirement_id: CID, source_id: SID, stage_b_status: "pending", stage_b_reviewer_user_id: null, stage_b_reviewed_at: null, stage_b_rationale: null, stage_b_pilot_scope: null });
    if (/\/candidates\/[^/]+\/wording-corrections$/.test(url)) return page([]);
    if (/\/requirements\/[^/]+\/governance-flags$/.test(url)) return page([]);
    if (/\/candidates\/[^/]+$/.test(url)) return ok(CANDIDATE);
    if (/\/sources\/[^/]+$/.test(url)) return ok(SOURCE);
    return new Response(JSON.stringify({ error: { code: "unrouted", message: url } }), { status: 500 });
  });
}

export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <Routes>
          <Route path="/regulatory/*" element={<RegulationAdminPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}
