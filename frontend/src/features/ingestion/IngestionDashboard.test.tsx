import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { IngestionDashboard } from "./IngestionDashboard";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const CREDENTIALS = {
  devTenantId: "22222222-2222-2222-2222-222222222222",
};

const SOURCE_A = {
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
  supersedes_source_id: null,
  superseded_by_source_id: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const SOURCE_B = {
  ...SOURCE_A,
  id: "44444444-4444-4444-4444-444444444444",
  title: "Regulation (EU) 2025/1441",
};

const FAILED_JOB = {
  id: "55555555-5555-5555-5555-555555555555",
  artifact_id: "66666666-6666-6666-6666-666666666666",
  source_id: SOURCE_A.id,
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
  source_id: SOURCE_A.id,
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((onResolve) => {
    resolve = onResolve;
  });
  return { promise, resolve };
}

/**
 * Route fetch stubs by suffix so every page section receives a
 * deterministic payload. Unmatched URLs fail loudly via 500, keeping
 * tests honest about what the dashboard really requests.
 */
function stubRegulatoryBackend(options: {
  listStatus?: number;
  listBody?: unknown;
  sources?: typeof SOURCE_A[];
}) {
  const sources = options.sources ?? [SOURCE_A, SOURCE_B];
  const stub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
    void init;
    const url = typeof input === "string" ? input : input.url;
    const respond = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });

    if (url.endsWith("/regulatory/sources")) {
      const status = options.listStatus ?? 200;
      return respond(options.listBody ?? { items: sources, total: sources.length }, status);
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
      return respond({ items: [], limit: 50, offset: 0, total: 0 });
    }
    if (/\/regulatory\/candidates\/[^/]+\/stage-a\/history$/.test(url)) {
      return respond({ items: [], limit: 50, offset: 0, total: 0 });
    }
    if (/\/regulatory\/candidates\/[^/]+\/stage-a$/.test(url)) {
      return respond({
        id: CANDIDATE.id,
        requirement_id: CANDIDATE.id,
        source_id: SOURCE_A.id,
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
        source_id: SOURCE_A.id,
        stage_b_status: "pending",
        stage_b_reviewer_user_id: null,
        stage_b_reviewed_at: null,
        stage_b_rationale: null,
        stage_b_pilot_scope: null,
      });
    }
    if (/\/regulatory\/requirements\/[^/]+\/governance-flags$/.test(url)) {
      return respond({ items: [], limit: 50, offset: 0, total: 0 });
    }
    if (/\/regulatory\/candidates\/[^/]+$/.test(url)) {
      return respond(CANDIDATE);
    }
    const sourceMatch = /\/regulatory\/sources\/([^/]+)$/.exec(url);
    if (sourceMatch) {
      const source = sources.find((entry) => entry.id === decodeURIComponent(sourceMatch[1]));
      if (source) {
        return respond(source);
      }
    }
    return respond({ error: { code: "unexpected_error", message: "unrouted" } }, 500);
  });
  return stub;
}

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={["/regulatory-ingestion"]}>
      <AuthProvider initial={CREDENTIALS}>
        <Routes>
          <Route path="/regulatory-ingestion" element={<IngestionDashboard />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function openCandidateReview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getAllByRole("button", { name: "Inspect source" })[0]);
  await user.click(await screen.findByRole("button", { name: "Review candidate" }));
  await screen.findByText("Stage A — source traceability and wording verification");
}

describe("IngestionDashboard", () => {
  it("renders sources on the ingestion route and inspects the selected source", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText(SOURCE_A.title)).toBeTruthy();
      expect(screen.getByText(SOURCE_B.title)).toBeTruthy();
    });
    await user.click(screen.getAllByRole("button", { name: "Inspect source" })[0]);
    await waitFor(() => {
      expect(
        fetchStub.mock.calls.some(([url]) =>
          String(url).endsWith(`/regulatory/sources/${SOURCE_A.id}/ingestion-jobs`),
        ),
      ).toBe(true);
      expect(
        fetchStub.mock.calls.some(([url]) =>
          String(url).endsWith(`/regulatory/sources/${SOURCE_A.id}/candidates`),
        ),
      ).toBe(true);
    });
    // Job lifecycle state, attempts, and failure details render verbatim.
    expect(await screen.findByText("failed")).toBeTruthy();
    expect(screen.getByText(/simulated parser failure/)).toBeTruthy();
    expect(screen.getByText("Review candidate")).toBeTruthy();
  });

  it("surfaces authorization denial as an error instead of a fabricated list", async () => {
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
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
    });
    expect(screen.queryByText(SOURCE_A.title)).toBeNull();
  });

  it("records a Stage A decision with the exact backend payload and refreshes", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText(SOURCE_A.title);
    await openCandidateReview(user);
    await user.type(
      await screen.findByLabelText("Rationale (required)", { selector: "#stage-a-rationale" }),
      "Source traceability confirmed via artifact reference.",
    );
    const postsBefore = fetchStub.mock.calls.filter(
      ([url, init]) => String(url).endsWith("/stage-a") && (init as RequestInit).method === "POST",
    ).length;
    await user.click(screen.getByRole("button", { name: "Record Stage A verification" }));
    await waitFor(() => {
      const stageACall = fetchStub.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith(`/regulatory/candidates/${CANDIDATE.id}/stage-a`) &&
          (init as RequestInit).method === "POST",
      );
      expect(stageACall).toBeTruthy();
      expect(JSON.parse(String((stageACall as unknown as [string, RequestInit])[1].body))).toEqual({
        stage_a_status: "verified",
        rationale: "Source traceability confirmed via artifact reference.",
      });
    });
    // The decision triggered exactly one POST and a refresh of source data.
    const postsAfter = fetchStub.mock.calls.filter(
      ([url, init]) => String(url).endsWith("/stage-a") && (init as RequestInit).method === "POST",
    ).length;
    expect(postsAfter).toBe(postsBefore + 1);
    await waitFor(() => {
      expect(
        fetchStub.mock.calls.some(([url]) =>
          String(url).endsWith(`/regulatory/sources/${SOURCE_A.id}/ingestion-jobs`),
        ),
      ).toBe(true);
    });
  });

  it("prevents duplicate Stage A submissions while the first request is pending", async () => {
    const fetchStub = stubRegulatoryBackend({});
    const pendingPost = deferred<Response>();
    const stub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (
        String(url).endsWith(`/regulatory/candidates/${CANDIDATE.id}/stage-a`) &&
        (init as RequestInit | undefined)?.method === "POST"
      ) {
        return pendingPost.promise;
      }
      return (fetchStub as (i: string | Request, r?: RequestInit) => Promise<Response>)(input, init);
    });
    vi.stubGlobal("fetch", stub);
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText(SOURCE_A.title);
    await openCandidateReview(user);
    await user.type(
      await screen.findByLabelText("Rationale (required)", { selector: "#stage-a-rationale" }),
      "Verified against the recorded artifact.",
    );
    const submit = screen.getByRole("button", { name: /Record Stage A verification/ });
    await user.click(submit);
    // While pending, the action is relabeled and disabled; a duplicate
    // click must not create a second POST.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Recording…" })).toHaveAttribute("disabled");
    });
    fireEvent.click(submit);
    pendingPost.resolve(
      new Response(
        JSON.stringify({
          id: CANDIDATE.id,
          requirement_id: CANDIDATE.id,
          stage_a_status: "verified",
          stage_a_reviewer_user_id: null,
          stage_a_reviewed_at: "2026-01-04T00:00:00Z",
          stage_a_rationale: "Verified against the recorded artifact.",
          audit_id: "88888888-8888-8888-8888-888888888888",
          audit_created_at: "2026-01-04T00:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await waitFor(() => {
      expect(stub.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/stage-a") && (init as RequestInit).method === "POST",
      ).length).toBe(1);
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Record Stage A verification/ })).not.toHaveAttribute("disabled");
    });
  });

  it("requires the mandatory Stage B pilot scope and posts the supported fields only", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText(SOURCE_A.title);
    await openCandidateReview(user);
    await user.type(
      await screen.findByLabelText(/Rationale \(required\)/, { selector: "#stage-b-rationale" }),
      "Pilot scope confirmed with the product owner.",
    );
    await user.click(screen.getByRole("button", { name: "Record Stage B approval" }));
    expect(
      await screen.findByText(/Pilot scope is required for the Stage B decision/),
    ).toBeTruthy();
    expect(
      fetchStub.mock.calls.filter(
        ([url, init]) => String(url).endsWith("/stage-b") && (init as RequestInit).method === "POST",
      ).length,
    ).toBe(0);
    await user.type(
      screen.getByLabelText("Pilot scope (required)", { selector: "#stage-b-pilot-scope" }),
      "sesame EU pilot",
    );
    await user.click(screen.getByRole("button", { name: "Record Stage B approval" }));
    await waitFor(() => {
      const stageBCall = fetchStub.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith(`/regulatory/candidates/${CANDIDATE.id}/stage-b`) &&
          (init as RequestInit).method === "POST",
      );
      expect(stageBCall).toBeTruthy();
      // Only fields accepted by RegulatoryStageBReviewRequest are sent;
      // pilot scope is mandatory and no string evidence list is fabricated.
      expect(JSON.parse(String((stageBCall as unknown as [string, RequestInit])[1].body))).toEqual({
        stage_b_status: "approved",
        rationale: "Pilot scope confirmed with the product owner.",
        pilot_scope: "sesame EU pilot",
      });
    });
  });

  it("does not render publication or exporter-applicability controls", async () => {
    vi.stubGlobal("fetch", stubRegulatoryBackend({}));
    renderDashboard();
    await screen.findByText(SOURCE_A.title);
    expect(screen.queryByText(/Mark as published/i)).toBeNull();
    expect(screen.queryByText(/Mark exporter-applicable/i)).toBeNull();
    expect(screen.queryByText(/Publish requirement/i)).toBeNull();
  });

  it("discards a stale source response after the selection changes", async () => {
    const staleSource = deferred<Response>();
    const fetchStub = stubRegulatoryBackend({});
    const stub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (String(url).endsWith(`/regulatory/sources/${SOURCE_A.id}`) && !/artifacts$|ingestion-jobs$|candidates$|governance-flags$/.test(String(url))) {
        return staleSource.promise;
      }
      return (fetchStub as (i: string | Request, r?: RequestInit) => Promise<Response>)(input, init);
    });
    vi.stubGlobal("fetch", stub);
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText(SOURCE_A.title);
    const inspectButtons = screen.getAllByRole("button", { name: "Inspect source" });
    await user.click(inspectButtons[0]);
    await user.click(inspectButtons[1]);
    expect(await screen.findByRole("heading", { name: SOURCE_B.title })).toBeTruthy();
    // Resolve the previously selected source's detail late; its response
    // arrives stale and must not replace what is displayed.
    staleSource.resolve(SOURCE_A as unknown as Response);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: SOURCE_B.title })).toBeTruthy();
    });
    // The stale response for the previously selected source must not
    // replace the currently displayed source detail.
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: SOURCE_A.title })).toBeNull();
    });
  });

  it("shows the empty state when no sources exist", async () => {
    vi.stubGlobal(
      "fetch",
      stubRegulatoryBackend({ listBody: { items: [], total: 0 } }),
    );
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("No regulatory sources registered")).toBeTruthy();
    });
  });

  it("surfaces an API failure with a retry, without fabricated content", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: { code: "server_error", message: "Regulatory service is unavailable." },
          }),
          { status: 500 },
        ),
      ),
    );
    renderDashboard();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(SOURCE_A.title)).toBeNull();
    expect(screen.getByRole("button", { name: /try again/i })).toBeTruthy();
  });
});
