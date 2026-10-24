import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { RegulationAdminPage } from "./RegulationAdminPage";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const CREDENTIALS = {
  devTenantId: "22222222-2222-2222-2222-222222222222",
};

const SOURCE = {
  id: "11111111-1111-1111-1111-111111111111",
  authority_id: "99999999-9999-9999-9999-999999999999",
  jurisdiction: "EU",
  title: "Regulation (EU) 2019/1793",
  version: "1.0",
  status: "active",
  effective_date: "2026-01-01",
  publication_date: null,
  source_url: "https://eur-lex.example/regulation",
  retrieval_timestamp: null,
  supersedes_source_id: "22222222-2222-2222-2222-222222222222",
  superseded_by_source_id: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const FAILED_JOB = {
  id: "55555555-5555-5555-5555-555555555555",
  artifact_id: "66666666-6666-6666-6666-666666666666",
  source_id: SOURCE.id,
  status: "failed",
  attempt_number: 1,
  started_at: "2026-01-02T00:00:00Z",
  completed_at: "2026-01-02T00:05:00Z",
  error_details: "simulated parser failure",
  parser_version: "v1",
  actor_user_id: null,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:05:00Z",
};

const CANDIDATE = {
  id: "33333333-3333-3333-3333-333333333333",
  source_id: SOURCE.id,
  artifact_id: "66666666-6666-6666-6666-666666666666",
  normalized_document_id: null,
  requirement_text: "All cocoa exports require a phytosanitary certificate.",
  requirement_type: "documentation",
  source_location: { page: 2 },
  position: 1,
  actor: "exporter",
  status: "extracted",
  extraction_outcome: "partial",
  parser_version: "v1",
  manual_entry: false,
  reviewer_user_id: null,
  reviewed_at: null,
  ingestion_job_id: FAILED_JOB.id,
  created_at: "2026-01-03T00:00:00Z",
  updated_at: "2026-01-03T00:00:00Z",
};

const PENDING_FLAG = {
  id: "77777777-7777-7777-7777-777777777777",
  requirement_id: CANDIDATE.id,
  trigger_source_id: SOURCE.id,
  trigger_type: "supersession",
  status: "pending_review",
  actor_user_id: SOURCE.authority_id,
  rationale: "Source superseded by a newer version.",
  created_at: "2026-01-04T00:00:00Z",
  updated_at: "2026-01-04T00:00:00Z",
};

/**
 * Route fetch stubs by suffix so every page section receives a
 * deterministic payload. Unmatched URLs fail loudly via 500, keeping
 * tests honest about what the page really requests.
 */
function stubRegulatoryBackend(options: {
  listStatus?: number;
  listBody?: unknown;
}) {
  return vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
    void init;
    const url = typeof input === "string" ? input : input.url;
    const respond = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });

    if (url.endsWith("/regulatory/sources")) {
      const status = options.listStatus ?? 200;
      return respond(options.listBody ?? { items: [SOURCE], total: 1 }, status);
    }
    if (/\/regulatory\/sources\/[^/]+\/artifacts$/.test(url)) {
      return respond({ items: [], limit: 50, offset: 0, total: 0 });
    }
    if (/\/regulatory\/sources\/[^/]+\/ingestion-jobs$/.test(url)) {
      return respond({ items: [FAILED_JOB], limit: 50, offset: 0, total: 1 });
    }
    if (/\/regulatory\/sources\/[^/]+\/candidates$/.test(url)) {
      return respond({ items: [CANDIDATE], limit: 50, offset: 0, total: 1 });
    }
    if (/\/regulatory\/sources\/[^/]+\/governance-flags$/.test(url)) {
      return respond({ items: [PENDING_FLAG], total: 1 });
    }
    if (/\/regulatory\/candidates\/[^/]+\/stage-a\/history$/.test(url)) {
      return respond({ items: [], limit: 50, offset: 0, total: 0 });
    }
    if (/\/regulatory\/candidates\/[^/]+\/stage-a$/.test(url)) {
      return respond({
        id: CANDIDATE.id,
        requirement_id: CANDIDATE.id,
        source_id: SOURCE.id,
        stage_a_status: "pending",
        stage_a_reviewer_user_id: null,
        stage_a_reviewed_at: null,
        stage_a_rationale: null,
      });
    }
    if (/\/regulatory\/candidates\/[^/]+\/stage-b\/history$/.test(url)) {
      return respond({ items: [], limit: 50, offset: 0, total: 0 });
    }
    if (/\/regulatory\/candidates\/[^/]+\/stage-b$/.test(url)) {
      return respond({
        id: CANDIDATE.id,
        requirement_id: CANDIDATE.id,
        source_id: SOURCE.id,
        stage_b_status: "pending",
        stage_b_reviewer_user_id: null,
        stage_b_reviewed_at: null,
        stage_b_rationale: null,
        stage_b_pilot_scope: null,
      });
    }
    if (/\/regulatory\/requirements\/[^/]+\/governance-flags$/.test(url)) {
      return respond({ items: [PENDING_FLAG], total: 1 });
    }
    if (/\/regulatory\/candidates\/[^/]+$/.test(url)) {
      return respond(CANDIDATE);
    }
    if (/\/regulatory\/sources\/[^/]+$/.test(url)) {
      return respond(SOURCE);
    }
    return respond({ error: { code: "unexpected_error", message: "unrouted" } }, 500);
  });
}

function renderAdmin() {
  return render(
    <MemoryRouter initialEntries={["/regulatory"]}>
      <AuthProvider initial={CREDENTIALS}>
        <Routes>
          <Route path="/regulatory" element={<RegulationAdminPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("RegulationAdminPage", () => {
  it("lists registered regulatory sources with their recorded status", async () => {
    vi.stubGlobal("fetch", stubRegulatoryBackend({}));
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    expect(screen.getByText("active")).toBeTruthy();
  });

  it("surfaces authorization denial as an error, never as success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: { code: "permission_denied", message: "Permission denied." },
          }),
          { status: 403 },
        ),
      ),
    );
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
    });
    // No fabricated success state is shown when authorization is missing.
    expect(screen.queryByText("Regulation (EU) 2019/1793")).toBeNull();
  });

  it("shows the empty state when no sources exist", async () => {
    vi.stubGlobal(
      "fetch",
      stubRegulatoryBackend({ listBody: { items: [], total: 0 } }),
    );
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("No regulatory sources registered")).toBeTruthy();
    });
  });

  it("inspects a source: provenance, failed job visibility, and supersession as recorded", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("button", { name: "Inspect source" }));
    await waitFor(() => {
      expect(fetchStub.mock.calls.some(([url]) =>
        String(url).endsWith(`/regulatory/sources/${SOURCE.id}/ingestion-jobs`),
      )).toBe(true);
    });
    // Failed ingestion stays visible with its recorded failure details.
    expect(await screen.findByText("failed")).toBeTruthy();
    expect(screen.getByText(/simulated parser failure/)).toBeTruthy();
    // Supersession displayed verbatim as recorded — never inferred away.
    expect(await screen.findByText("Supersedes (as recorded)")).toBeTruthy();
  });

  it("opens candidate review with Stage A and Stage B as distinct actions", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("button", { name: "Inspect source" }));
    await user.click(await screen.findByRole("button", { name: "Review candidate" }));
    expect(await screen.findByText("Stage A — source traceability and wording verification")).toBeTruthy();
    expect(screen.getByText("Stage B — pilot-scope applicability approval")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Record Stage A verification" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Record Stage B approval" }),
    ).toBeTruthy();
  });

  it("displays the pending governance flag and states it cannot be bypassed", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("button", { name: "Inspect source" }));
    expect(await screen.findByText("Pending flags cannot be cleared from this view. Flag completion follows the governance rules only.")).toBeTruthy();
    await user.click(await screen.findByRole("button", { name: "Review candidate" }));
    expect(
      await screen.findByText(/A pending governance flag exists for this requirement/),
    ).toBeTruthy();
  });

  it("never presents publication or exporter applicability as available", async () => {
    vi.stubGlobal("fetch", stubRegulatoryBackend({}));
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText(/Nothing on this page publishes a requirement/)).toBeTruthy();
    });
    expect(screen.queryByText(/Mark as published/i)).toBeNull();
    expect(screen.queryByText(/Mark exporter-applicable/i)).toBeNull();
  });

  it("records a Stage A decision with the required rationale and refreshes state", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("button", { name: "Inspect source" }));
    await user.click(await screen.findByRole("button", { name: "Review candidate" }));
    const rationale = await screen.findByLabelText("Rationale (required)", {
      selector: "#stage-a-rationale",
    });
    await user.type(rationale, "Source traceability confirmed via artifact reference.");
    const initialJobCalls = fetchStub.mock.calls.filter(([url]) =>
      String(url).endsWith(`/regulatory/sources/${SOURCE.id}/ingestion-jobs`),
    ).length;
    await user.click(screen.getByRole("button", { name: "Record Stage A verification" }));
    await waitFor(() => {
      expect(
        fetchStub.mock.calls.some(([url, init]) =>
          String(url).endsWith(`/regulatory/candidates/${CANDIDATE.id}/stage-a`) &&
          (init as RequestInit).method === "POST",
        ),
      ).toBe(true);
    });
    const stageACall = fetchStub.mock.calls.find(([url, init]) =>
      String(url).endsWith(`/regulatory/candidates/${CANDIDATE.id}/stage-a`) &&
      (init as RequestInit).method === "POST",
    );
    expect(JSON.parse(String((stageACall as unknown as [string, RequestInit])[1].body))).toEqual({
      stage_a_status: "verified",
      rationale: "Source traceability confirmed via artifact reference.",
    });
    // Successful action refreshes the displayed source state.
    await waitFor(() => {
      const jobCallsAfter = fetchStub.mock.calls.filter(([url]) =>
        String(url).endsWith(`/regulatory/sources/${SOURCE.id}/ingestion-jobs`),
      ).length;
      expect(jobCallsAfter).toBeGreaterThan(initialJobCalls);
    });
  });

  it("requires a rationale before submitting a Stage A decision", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("button", { name: "Inspect source" }));
    await user.click(await screen.findByRole("button", { name: "Review candidate" }));
    await user.click(screen.getByRole("button", { name: "Record Stage A verification" }));
    expect(
      await screen.findByText(/A rationale is required for the Stage A decision/),
    ).toBeTruthy();
    const stageAPosts = fetchStub.mock.calls.filter(([url, init]) =>
      String(url).endsWith("/stage-a") && (init as RequestInit).method === "POST",
    );
    expect(stageAPosts.length).toBe(0);
  });
});
