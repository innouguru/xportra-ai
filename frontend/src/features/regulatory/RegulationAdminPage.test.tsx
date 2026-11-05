import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { RegulationAdminPage } from "./RegulationAdminPage";
import * as regulatoryApi from "../../api/regulatory";

afterEach(() => {
  vi.unstubAllGlobals();
  if (typeof sessionStorage !== "undefined" && sessionStorage.clear) {
    sessionStorage.clear();
  }
  vi.restoreAllMocks();
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((onResolve) => {
    resolve = onResolve;
  });
  return { promise, resolve };
}

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
  current_stage: "failed",
  stage_updated_at: "2026-01-02T00:04:00Z",
  actor_user_id: null,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:05:00Z",
};

const ARTIFACT = {
  id: FAILED_JOB.artifact_id,
  source_id: SOURCE.id,
  content_hash: "artifact-hash-123",
  content_length: 128,
  content_type: "text/plain",
  acquisition_channel: "staff_upload",
  acquired_at: "2026-01-02T00:00:00Z",
  status: "available",
  source_version: "2026-01",
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

/** The new attempt row the backend returns for an authorized retry (M4). */
const RETRIED_JOB = {
  ...FAILED_JOB,
  id: "41414141-4141-4141-4141-414141414141",
  status: "pending",
  attempt_number: 2,
  started_at: null,
  completed_at: null,
  error_details: null,
  current_stage: "queued",
  stage_updated_at: "2026-01-06T00:00:00Z",
  updated_at: "2026-01-06T00:00:00Z",
};

/** Withdrawal result as the backend records it (M7). */
const WITHDRAWAL_RESULT = {
  id: "42424242-4242-4242-4242-424242424242",
  source_id: SOURCE.id,
  status: "withdrawn",
  governance_flags_raised: 1,
  updated_at: "2026-01-06T00:00:00Z",
};

const CANDIDATE = {
  id: "33333333-3333-3333-3333-333333333333",
  source_id: SOURCE.id,
  artifact_id: "66666666-6666-6666-6666-666666666666",
  normalized_document_id: null,
  requirement_text: "All cocoa exports require a phytosanitary certificate.",
  requirement_type: "documentation",
  source_location: {
    page_reference: 2,
    supporting_quote: "All cocoa exports require a phytosanitary certificate.",
    reference_status: {
      page: "verified",
      section: "not_returned_by_model",
    },
  },
  position: 1,
  actor: "exporter",
  status: "extracted",
  extraction_outcome: "partial",
  parser_version: "v1",
  manual_entry: false,
  reviewer_user_id: null,
  reviewed_at: null,
  ingestion_job_id: FAILED_JOB.id,
  source_title: SOURCE.title,
  source_jurisdiction: SOURCE.jurisdiction,
  artifact_source_version: ARTIFACT.source_version,
  artifact_content_hash: ARTIFACT.content_hash,
  document_parser_name: "plain-text-v1",
  extraction_history: [
    {
      extraction_run_id: "94949494-9494-4949-9494-949494949494",
      normalized_document_id: "95959595-9595-4959-9595-959595959595",
      artifact_id: ARTIFACT.id,
      source_id: SOURCE.id,
      ingestion_job_id: FAILED_JOB.id,
      artifact_content_hash: ARTIFACT.content_hash,
      artifact_source_version: ARTIFACT.source_version,
      normalized_text_sha256: "a".repeat(64),
      parser_version: "v1",
      extraction_method: "llm_semantic_chunked",
      extraction_version: "v1",
      prompt_version: "requirements-v1",
      configured_model_identifier: "model-id",
      model_identifiers: ["model-id"],
      provider_names: ["provider-name"],
      outcome: "partial",
      failed_chunks: [{ reason: "provider_unavailable" }],
      rejected_candidate_count: 1,
      started_at: "2026-01-02T00:01:00Z",
      completed_at: "2026-01-02T00:02:00Z",
      candidate_index: 0,
      evidence_snapshot: {
        source_location: {
          supporting_quote:
            "All cocoa exports require a phytosanitary certificate.",
          page_reference: 2,
          reference_status: {
            page: "verified",
            section: "not_returned_by_model",
          },
        },
      },
      resolution_status: "persisted",
      is_origin: true,
    },
  ],
  created_at: "2026-01-03T00:00:00Z",
  updated_at: "2026-01-03T00:00:00Z",
};

const JOB_EXTRACTION_HISTORY = {
  job_id: FAILED_JOB.id,
  items: [
    {
      extraction_run_id: "94949494-9494-4949-9494-949494949494",
      normalized_document_id: "95959595-9595-4959-9595-959595959595",
      artifact_id: ARTIFACT.id,
      source_id: SOURCE.id,
      ingestion_job_id: FAILED_JOB.id,
      artifact_content_hash: ARTIFACT.content_hash,
      artifact_source_version: ARTIFACT.source_version,
      normalized_text_sha256: "a".repeat(64),
      parser_version: "v1",
      extraction_method: "llm_semantic_chunked",
      extraction_version: "v1",
      prompt_version: "requirements-v1",
      configured_model_identifier: "model-id",
      model_identifiers: ["model-id"],
      provider_names: ["provider-name"],
      outcome: "partial",
      failed_chunks: [{ reason: "provider_unavailable" }],
      rejected_candidate_count: 1,
      started_at: "2026-01-02T00:01:00Z",
      completed_at: "2026-01-02T00:02:00Z",
      candidate_count: 1,
      persisted_candidate_count: 1,
      candidates: [
        {
          candidate_index: 0,
          candidate_id: CANDIDATE.id,
          evidence_snapshot: {
            requirement_text: CANDIDATE.requirement_text,
            source_location: CANDIDATE.source_location,
          },
          resolution_status: "persisted",
          is_origin: true,
        },
      ],
    },
  ],
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

/** One append-only wording correction (M5). */
const WORDING_CORRECTION = {
  id: "43434343-4343-4343-4343-434343434343",
  requirement_id: CANDIDATE.id,
  source_id: SOURCE.id,
  original_text: CANDIDATE.requirement_text,
  corrected_text:
    "All cocoa exports require a phytosanitary certificate issued within 14 days.",
  rationale: "Extraction dropped the validity window for the certificate.",
  reviewer_user_id: CREDENTIALS.devTenantId,
  created_at: "2026-01-05T01:00:00Z",
};

const NEW_SOURCE = {
  id: "88888888-8888-8888-8888-888888888888",
  authority_id: "99999999-9999-9999-9999-999999999999",
  jurisdiction: "NG",
  title: "National Agency for Food and Drug Administration and Control Act",
  version: "2023.1",
  status: "draft",
  effective_date: "2023-01-01",
  publication_date: null,
  source_url: "https://nafdac.gov.ng/act-2023",
  retrieval_timestamp: null,
  supersedes_source_id: null,
  superseded_by_source_id: null,
  created_at: "2026-01-05T00:00:00Z",
  updated_at: "2026-01-05T00:00:00Z",
};

const AUTHORITY_A = {
  id: "99999999-9999-9999-9999-999999999999",
  name: "National Agency for Food and Drug Administration and Control",
  jurisdiction: "NG",
  authority_type: "government",
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const AUTHORITY_B = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  name: "Nigeria Customs Service",
  jurisdiction: "NG",
  authority_type: "government",
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

/**
 * Route fetch stubs by suffix so every page section receives a
 * deterministic payload. Unmatched URLs fail loudly via 500, keeping
 * tests honest about what the page really requests.
 */
function stubRegulatoryBackend(options: {
  listStatus?: number;
  listBody?: unknown;
  artifactsBody?: unknown;
  jobsBody?: unknown;
  extractionHistoryBody?: unknown;
}) {
  return vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
    const url = typeof input === "string" ? input : input.url;
    const respond = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });

    if (url.endsWith("/regulatory/authorities")) {
      return respond([AUTHORITY_A, AUTHORITY_B], 200);
    }
    if (url.endsWith("/regulatory/sources")) {
      if ((init as RequestInit | undefined)?.method === "POST") {
        return respond(NEW_SOURCE, 201);
      }
      const status = options.listStatus ?? 200;
      return respond(options.listBody ?? { items: [SOURCE], total: 1 }, status);
    }
    if (/\/regulatory\/sources\/[^/]+\/artifacts$/.test(url)) {
      const body = options.artifactsBody ?? { items: [], limit: 50, offset: 0, total: 0 };
      return respond(body);
    }
    if (/\/regulatory\/sources\/[^/]+\/ingestion-jobs$/.test(url)) {
      const body = options.jobsBody ?? { items: [FAILED_JOB], limit: 50, offset: 0, total: 1 };
      return respond(body);
    }
    if (/\/regulatory\/ingestion-jobs\/[^/]+\/extraction-history$/.test(url)) {
      return respond(
        options.extractionHistoryBody ?? { job_id: FAILED_JOB.id, items: [] },
      );
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
    if (/\/regulatory\/candidates\/[^/]+\/wording-corrections$/.test(url)) {
      return respond({ items: [], total: 0 });
    }
    if (/\/regulatory\/ingestion-jobs\/[^/]+\/retry$/.test(url)) {
      return respond(RETRIED_JOB, 201);
    }
    if (/\/regulatory\/sources\/[^/]+\/withdrawal$/.test(url)) {
      return respond(WITHDRAWAL_RESULT, 200);
    }
    return respond({ error: { code: "unexpected_error", message: "unrouted" } }, 500);
  });
}

function renderAdmin(path = "/regulatory") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={CREDENTIALS}>
        <Routes>
          <Route path="/regulatory/*" element={<RegulationAdminPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

type User = ReturnType<typeof userEvent.setup>;

/** From the list, open the (only) source. Lands on its Documents step. */
async function openSource(user: User) {
  await user.click(await screen.findByRole("link", { name: "Open source" }));
}

/** Switch tabs on a source page (tab names carry a trailing count). */
async function openTab(user: User, name: string) {
  await user.click(
    await screen.findByRole("link", { name: new RegExp(`^${name}`) }),
  );
}

/** List -> source -> Candidates tab -> the candidate's review page. */
async function openCandidateReview(user: User) {
  await openSource(user);
  await openTab(user, "Candidates");
  await user.click(await screen.findByRole("link", { name: "Review candidate" }));
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
    await user.click(screen.getByRole("link", { name: "Open source" }));
    await waitFor(() => {
      expect(fetchStub.mock.calls.some(([url]) =>
        String(url).endsWith(`/regulatory/sources/${SOURCE.id}/ingestion-jobs`),
      )).toBe(true);
    });
    // Failed ingestion stays visible with its recorded failure details.
    await openTab(user, "Ingestion");
    expect(await screen.findByText("failed")).toBeTruthy();
    expect(screen.getByText(/simulated parser failure/)).toBeTruthy();
    // Supersession displayed verbatim as recorded — never inferred away.
    await openTab(user, "Details");
    expect(await screen.findByText("Supersedes (as recorded)")).toBeTruthy();
  });

  it("shows recorded stage progress and lets staff inspect a job's extraction evidence", async () => {
    const processingJob = {
      ...FAILED_JOB,
      id: "56565656-5656-4656-8656-565656565656",
      status: "processing",
      current_stage: "extracting_requirements",
      stage_updated_at: "2026-01-02T00:03:00Z",
      completed_at: null,
      error_details: null,
    };
    const fetchStub = stubRegulatoryBackend({
      artifactsBody: { items: [ARTIFACT], limit: 50, offset: 0, total: 1 },
      jobsBody: { items: [processingJob], limit: 50, offset: 0, total: 1 },
      extractionHistoryBody: {
        ...JOB_EXTRACTION_HISTORY,
        job_id: processingJob.id,
      },
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await openSource(user);
    await openTab(user, "Ingestion");

    expect(await screen.findByText("Extracting requirements")).toBeTruthy();
    expect(screen.getByText("processing")).toBeTruthy();
    expect(screen.getByText(/2026-01/)).toBeTruthy();
    expect(screen.queryByText(/% complete/)).toBeNull();

    await user.click(screen.getByRole("button", { name: "Inspect job" }));
    expect(await screen.findByText("provider_unavailable")).toBeTruthy();
    expect(screen.getByText("model-id")).toBeTruthy();
    expect(
      screen.getAllByText(
        "All cocoa exports require a phytosanitary certificate.",
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Not returned by model")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Inspect candidate and full provenance" }),
    ).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Refresh jobs" }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Hide job details" }),
      ).toBeTruthy();
    });
    expect(screen.getByText("Extracting requirements")).toBeTruthy();
  });

  it("shows a successful empty extraction as zero candidates", async () => {
    const emptyRun = {
      ...JOB_EXTRACTION_HISTORY.items[0],
      outcome: "succeeded",
      candidate_count: 0,
      persisted_candidate_count: 0,
      rejected_candidate_count: 0,
      failed_chunks: [],
      candidates: [],
    };
    const fetchStub = stubRegulatoryBackend({
      extractionHistoryBody: {
        job_id: FAILED_JOB.id,
        items: [emptyRun],
      },
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await openSource(user);
    await openTab(user, "Ingestion");
    await user.click(screen.getByRole("button", { name: "Inspect job" }));

    expect(await screen.findByText("succeeded")).toBeTruthy();
    expect(screen.getByText(/0 candidate snapshots recorded/)).toBeTruthy();
    expect(
      screen.getByText("This persisted run contains no candidate snapshots."),
    ).toBeTruthy();
  });

  it("marks the last loaded job snapshot as stale when refresh fails", async () => {
    const jobsUrl = `/regulatory/sources/${SOURCE.id}/ingestion-jobs`;
    const backend = stubRegulatoryBackend({});
    let jobListCalls = 0;
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.url;
      if (String(url).endsWith(jobsUrl)) {
        jobListCalls += 1;
        if (jobListCalls > 1) {
          return new Response(
            JSON.stringify({
              error: { code: "unexpected_error", message: "Refresh unavailable." },
            }),
            { status: 503, headers: { "Content-Type": "application/json" } },
          );
        }
      }
      return backend(input, init);
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await openSource(user);
    await openTab(user, "Ingestion");
    await user.click(screen.getByRole("button", { name: "Refresh jobs" }));

    expect(
      await screen.findByText(/last successfully loaded snapshot and may be stale/i),
    ).toBeTruthy();
    expect(screen.getByText("failed")).toBeTruthy();
  });

  it("opens candidate review with Stage A and Stage B as distinct actions", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await openCandidateReview(user);
    expect(await screen.findByText("Stage A — source traceability and wording verification")).toBeTruthy();
    expect(screen.getByText("Stage B — pilot-scope applicability approval")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Record Stage A verification" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Record Stage B approval" }),
    ).toBeTruthy();
  });

  it("shows exact candidate evidence, reference status, and extraction provenance", async () => {
    vi.stubGlobal("fetch", stubRegulatoryBackend({}));
    const user = userEvent.setup();
    renderAdmin();
    await openCandidateReview(user);

    expect(
      (await screen.findAllByText(CANDIDATE.requirement_text)).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText(
        "All cocoa exports require a phytosanitary certificate.",
      ).length,
    ).toBeGreaterThan(0);
    for (const text of [
      "2 · verified against supplied source context",
      "Not returned by the model",
      "2026-01",
      "artifact-hash-123",
      "llm_semantic_chunked / v1",
      "model-id",
      "provider_unavailable",
    ]) {
      expect(screen.getAllByText(text).length).toBeGreaterThan(0);
    }
  });

  it("displays the pending governance flag and states it cannot be bypassed", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await openSource(user);
    await openTab(user, "Governance");
    expect(await screen.findByText("Pending flags cannot be cleared from this view. Flag completion follows the governance rules only.")).toBeTruthy();
    await openTab(user, "Candidates");
    await user.click(await screen.findByRole("link", { name: "Review candidate" }));
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
    await openCandidateReview(user);
    const rationale = await screen.findByLabelText("Rationale (required)", {
      selector: "#stage-a-rationale",
    });
    await user.type(rationale, "Source traceability confirmed via artifact reference.");
    const stageAReads = () =>
      fetchStub.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith(`/regulatory/candidates/${CANDIDATE.id}/stage-a`) &&
          (init as RequestInit | undefined)?.method !== "POST",
      ).length;
    const initialStageAReads = stageAReads();
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
    // Successful action refreshes the displayed review state.
    await waitFor(() => {
      expect(stageAReads()).toBeGreaterThan(initialStageAReads);
    });
    // Returning to the source reloads it from the server — a decision
    // recorded on the review page is never shown from a stale copy.
    const jobReads = () =>
      fetchStub.mock.calls.filter(([url]) =>
        String(url).endsWith(`/regulatory/sources/${SOURCE.id}/ingestion-jobs`),
      ).length;
    const jobReadsBefore = jobReads();
    await user.click(screen.getByRole("link", { name: "Back to candidates" }));
    await waitFor(() => {
      expect(jobReads()).toBeGreaterThan(jobReadsBefore);
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
    await openCandidateReview(user);
    await user.click(screen.getByRole("button", { name: "Record Stage A verification" }));
    expect(
      await screen.findByText(/A rationale is required for the Stage A decision/),
    ).toBeTruthy();
    const stageAPosts = fetchStub.mock.calls.filter(([url, init]) =>
      String(url).endsWith("/stage-a") && (init as RequestInit).method === "POST",
    );
    expect(stageAPosts.length).toBe(0);
  });

  it("shows the Register source button and opens the registration form", async () => {
    vi.stubGlobal("fetch", stubRegulatoryBackend({}));
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    expect(screen.getByRole("link", { name: "Register source" })).toBeTruthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    expect(screen.getByLabelText("Regulatory authority (required)")).toBeTruthy();
    expect(screen.getByLabelText("Jurisdiction (required)")).toBeTruthy();
    expect(screen.getByLabelText("Title (required)")).toBeTruthy();
  });

  it("displays authority options by name, not UUID", async () => {
    vi.stubGlobal("fetch", stubRegulatoryBackend({}));
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    const user = userEvent.setup();
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    // Authority options load from the backend
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "National Agency for Food and Drug Administration and Control (NG)" })).toBeTruthy();
    });
    expect(screen.getByRole("option", { name: "Nigeria Customs Service (NG)" })).toBeTruthy();
  });

  it("prevents invalid submission when required fields are empty", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    fireEvent.submit(document.querySelector("form.form") as HTMLFormElement);
    expect(
      await screen.findByRole("alert"),
    ).toBeTruthy();
    // No POST call was made.
    expect(
      fetchStub.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/regulatory/sources") &&
          (init as RequestInit).method === "POST",
      ).length,
    ).toBe(0);
  });

  it("submits a valid registration with the selected authority ID", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
      AUTHORITY_B,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    // Select an authority from the dropdown
    await waitFor(() => {
      expect(
        document.getElementById("register-source-authority-id"),
      ).toBeTruthy();
    });
    const authoritySelect = document.getElementById(
      "register-source-authority-id",
    ) as HTMLSelectElement;
    fireEvent.change(authoritySelect, {
      target: { value: "99999999-9999-9999-9999-999999999999" },
    });
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Test Source");
    await user.click(screen.getByRole("button", { name: "Register source" }));
    await waitFor(() => {
      expect(
        fetchStub.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/regulatory/sources") &&
            (init as RequestInit).method === "POST",
        ),
      ).toBe(true);
    });
    const postCall = fetchStub.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/regulatory/sources") &&
        (init as RequestInit).method === "POST",
    );
    expect(postCall).toBeTruthy();
    const body = JSON.parse(
      String((postCall as unknown as [string, RequestInit])[1].body),
    );
    expect(body).toEqual({
      authority_id: "99999999-9999-9999-9999-999999999999",
      jurisdiction: "NG",
      status: "draft",
      title: "Test Source",
    });
  });

  it("prevents duplicate submissions while registration is pending", async () => {
    const pendingPost = deferred<Response>();
    const fetchStub = stubRegulatoryBackend({});
    const stub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (
        String(url).endsWith("/regulatory/sources") &&
        (init as RequestInit | undefined)?.method === "POST"
      ) {
        return pendingPost.promise;
      }
      return (fetchStub as (i: string | Request, r?: RequestInit) => Promise<Response>)(input, init);
    });
    vi.stubGlobal("fetch", stub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
      AUTHORITY_B,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    await waitFor(() => {
      expect(
        document.getElementById("register-source-authority-id"),
      ).toBeTruthy();
    });
    const authoritySelect = document.getElementById(
      "register-source-authority-id",
    ) as HTMLSelectElement;
    fireEvent.change(authoritySelect, {
      target: { value: "99999999-9999-9999-9999-999999999999" },
    });
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Test Source");
    await user.click(screen.getByRole("button", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Registering…" })).toHaveAttribute("disabled");
    });
    // A second click while pending must not create a second POST.
    await user.click(screen.getByRole("button", { name: "Registering…" }));
    await waitFor(() => {
      expect(
        stub.mock.calls.filter(
          ([url, init]) =>
            String(url).endsWith("/regulatory/sources") &&
            (init as RequestInit).method === "POST",
        ).length,
      ).toBe(1);
    });
    pendingPost.resolve(
      new Response(JSON.stringify(NEW_SOURCE), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    // Success lands on the new source rather than re-showing the form.
    expect(await screen.findByText(/registered\. Next, upload/)).toBeTruthy();
  });

  it("lands on the new source's document step with a confirmation and no extra click", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
      AUTHORITY_B,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    await waitFor(() => {
      expect(document.getElementById("register-source-authority-id")).toBeTruthy();
    });
    fireEvent.change(
      document.getElementById("register-source-authority-id") as HTMLSelectElement,
      { target: { value: "99999999-9999-9999-9999-999999999999" } },
    );
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Test Source");
    await user.click(screen.getByRole("button", { name: "Register source" }));
    // The confirmation names the new source and the next step.
    const banner = await screen.findByText(/registered\. Next, upload/);
    expect(banner.textContent).toContain(NEW_SOURCE.title);
    expect(banner.textContent).toContain("upload the original regulatory document");
    // The upload step is already on screen: no "continue" button, no scrolling.
    expect(
      await screen.findByRole("heading", { name: "Upload original regulatory document" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Continue to document upload" })).toBeNull();
    // The source that was just registered is the one loaded.
    expect(
      fetchStub.mock.calls.some(([url]) =>
        String(url).endsWith(`/regulatory/sources/${NEW_SOURCE.id}`),
      ),
    ).toBe(true);
    // The progress stepper shows registration done and the document step current.
    expect(screen.getByLabelText("Source progress")).toBeTruthy();
    expect(screen.getByText("Next: upload the original document")).toBeTruthy();
  });

  it("preserves form input and shows a safe error when registration fails", async () => {
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (url.endsWith("/regulatory/authorities")) {
        return new Response(JSON.stringify([AUTHORITY_A, AUTHORITY_B]), {
          status: 200,
        });
      }
      if (
        String(url).endsWith("/regulatory/sources") &&
        (init as RequestInit | undefined)?.method === "POST"
      ) {
        return new Response(
          JSON.stringify({ error: { code: "server_error", message: "registration failed" } }),
          { status: 500 },
        );
      }
      if (url.endsWith("/regulatory/sources")) {
        return new Response(JSON.stringify({ items: [], total: 0 }), {
          status: 200,
        });
      }
      return new Response(
        JSON.stringify({ error: { code: "unexpected_error", message: "unrouted" } }),
        { status: 500 },
      );
    });
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
      AUTHORITY_B,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("No regulatory sources registered")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    await waitFor(() => {
      expect(document.getElementById("register-source-authority-id")).toBeTruthy();
    });
    const authoritySelect = document.getElementById(
      "register-source-authority-id",
    ) as HTMLSelectElement;
    fireEvent.change(authoritySelect, {
      target: { value: "99999999-9999-9999-9999-999999999999" },
    });
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Failed Source");
    await user.click(screen.getByRole("button", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByText("registration failed")).toBeTruthy();
    });
    // Form inputs are preserved so the user can correct and resubmit.
    expect(
      (document.getElementById("register-source-jurisdiction") as HTMLInputElement).value,
    ).toBe("NG");
    expect(
      (document.getElementById("register-source-title") as HTMLInputElement).value,
    ).toBe("Failed Source");
    // No success state is shown and the person stays on the form.
    expect(screen.queryByText(/registered\. Next, upload/)).toBeNull();
    expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
  });

  it("opens a source directly on its document step from a deep link", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    renderAdmin(`/regulatory/${SOURCE.id}`);
    expect(
      await screen.findByRole("heading", { name: "Upload original regulatory document" }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: SOURCE.title })).toBeTruthy();
  });

  it("displays API validation errors appropriately", async () => {
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (
        String(url).endsWith("/regulatory/sources") &&
        (init as RequestInit | undefined)?.method === "POST"
      ) {
        return new Response(
          JSON.stringify({
            error: { code: "invalid_input", message: "invalid source status: bogus" },
          }),
          { status: 422 },
        );
      }
      if (url.endsWith("/regulatory/sources")) {
        return new Response(JSON.stringify({ items: [SOURCE], total: 1 }), { status: 200 });
      }
      return new Response(JSON.stringify({ error: { code: "unexpected_error", message: "unrouted" } }), { status: 500 });
    });
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
      AUTHORITY_B,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    await waitFor(() => {
      expect(
        document.getElementById("register-source-authority-id"),
      ).toBeTruthy();
    });
    const authoritySelect = document.getElementById(
      "register-source-authority-id",
    ) as HTMLSelectElement;
    fireEvent.change(authoritySelect, {
      target: { value: "99999999-9999-9999-9999-999999999999" },
    });
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Bad Status Source");
    await user.click(screen.getByRole("button", { name: "Register source" }));
    await waitFor(() => {
      expect(
        screen.getByText("invalid source status: bogus"),
      ).toBeTruthy();
    });
  });

  it("handles authorization failure for registration", async () => {
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (
        String(url).endsWith("/regulatory/sources") &&
        (init as RequestInit | undefined)?.method === "POST"
      ) {
        return new Response(
          JSON.stringify({
            error: { code: "permission_denied", message: "Permission denied." },
          }),
          { status: 403 },
        );
      }
      if (url.endsWith("/regulatory/sources")) {
        return new Response(JSON.stringify({ items: [SOURCE], total: 1 }), { status: 200 });
      }
      return new Response(JSON.stringify({ error: { code: "unexpected_error", message: "unrouted" } }), { status: 500 });
    });
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
      AUTHORITY_B,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    await waitFor(() => {
      expect(
        document.getElementById("register-source-authority-id"),
      ).toBeTruthy();
    });
    const authoritySelect = document.getElementById(
      "register-source-authority-id",
    ) as HTMLSelectElement;
    fireEvent.change(authoritySelect, {
      target: { value: "99999999-9999-9999-9999-999999999999" },
    });
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Unauthorized Source");
    await user.click(screen.getByRole("button", { name: "Register source" }));
    await waitFor(() => {
      expect(
        screen.getByText("Your role does not allow this action. Contact a workspace owner."),
      ).toBeTruthy();
    });
  });

  it("registers and opens the new source even when the source list is unavailable", async () => {
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (url.endsWith("/regulatory/authorities")) {
        return new Response(JSON.stringify([AUTHORITY_A, AUTHORITY_B]), { status: 200 });
      }
      if (
        String(url).endsWith("/regulatory/sources") &&
        (init as RequestInit | undefined)?.method === "POST"
      ) {
        return new Response(JSON.stringify(NEW_SOURCE), { status: 201 });
      }
      if (url.endsWith("/regulatory/sources")) {
        return new Response(
          JSON.stringify({ error: { code: "server_error", message: "down" } }),
          { status: 500 },
        );
      }
      // Everything attached to the new source is reachable.
      return (stubRegulatoryBackend({}) as (i: string | Request, r?: RequestInit) => Promise<Response>)(input, init);
    });
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
      AUTHORITY_B,
    ]);
    const user = userEvent.setup();
    // The registration page never reads the list, so its outage is irrelevant.
    renderAdmin("/regulatory/new");
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    await waitFor(() => {
      expect(document.getElementById("register-source-authority-id")).toBeTruthy();
    });
    fireEvent.change(
      document.getElementById("register-source-authority-id") as HTMLSelectElement,
      { target: { value: "99999999-9999-9999-9999-999999999999" } },
    );
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Test Source");
    await user.click(screen.getByRole("button", { name: "Register source" }));
    expect(await screen.findByText(/registered\. Next, upload/)).toBeTruthy();
    expect(
      fetchStub.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/regulatory/sources") &&
          (init as RequestInit | undefined)?.method !== "POST",
      ),
    ).toBe(false);
  });

  it("shows an error when authority retrieval fails", async () => {
    const fetchStub = vi.fn(async (input: string | Request): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (url.endsWith("/regulatory/authorities")) {
        return new Response(
          JSON.stringify({ error: { code: "server_error", message: "down" } }),
          { status: 500 },
        );
      }
      if (url.endsWith("/regulatory/sources")) {
        return new Response(JSON.stringify({ items: [SOURCE], total: 1 }), { status: 200 });
      }
      return new Response(
        JSON.stringify({ error: { code: "unexpected_error", message: "unrouted" } }),
        { status: 500 },
      );
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    // Authority error is surfaced instead of options
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
    });
  });

  it("shows a helpful message when no authorities are registered", async () => {
    const fetchStub = vi.fn(async (input: string | Request): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (url.endsWith("/regulatory/authorities")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/regulatory/sources")) {
        return new Response(JSON.stringify({ items: [SOURCE], total: 1 }), { status: 200 });
      }
      return new Response(
        JSON.stringify({ error: { code: "unexpected_error", message: "unrouted" } }),
        { status: 500 },
      );
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    // Helpful message about registering an authority first
    expect(
      await screen.findByText(/No regulatory authorities are registered/),
    ).toBeTruthy();
  });

  it("rejects submission when authority ID is empty", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
      AUTHORITY_B,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    await user.keyboard("{Tab}"); // keep empty authority
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Empty Auth Source");
    fireEvent.submit(document.querySelector("form.form") as HTMLFormElement);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(
      fetchStub.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/regulatory/sources") &&
          (init as RequestInit | undefined)?.method === "POST",
      ).length,
    ).toBe(0);
  });

  it("rejects submission when authority ID is stale or invalid", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    // Inject a stale authority ID manually
    const authoritySelect = document.getElementById(
      "register-source-authority-id",
    ) as HTMLSelectElement;
    fireEvent.change(authoritySelect, {
      target: { value: "stale-unknown-id-0000-0000-0000-000000000000" },
    });
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Stale Auth Source");
    fireEvent.submit(document.querySelector("form.form") as HTMLFormElement);
    expect(
      await screen.findByRole("alert"),
    ).toBeTruthy();
    expect(
      fetchStub.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/regulatory/sources") &&
          (init as RequestInit | undefined)?.method === "POST",
      ).length,
    ).toBe(0);
  });

  it("submits with a valid authority from the loaded list and sends the correct UUID", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
    ]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    await waitFor(() => {
      expect(
        document.getElementById("register-source-authority-id"),
      ).toBeTruthy();
    });
    const authoritySelect = document.getElementById(
      "register-source-authority-id",
    ) as HTMLSelectElement;
    fireEvent.change(authoritySelect, {
      target: { value: AUTHORITY_A.id },
    });
    await user.click(screen.getByLabelText("Jurisdiction (required)"));
    await user.keyboard("{selectAll}NG");
    await user.click(screen.getByLabelText("Title (required)"));
    await user.keyboard("{selectAll}Valid Auth Source");
    await user.click(screen.getByRole("button", { name: "Register source" }));
    await waitFor(() => {
      expect(
        fetchStub.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/regulatory/sources") &&
            (init as RequestInit).method === "POST",
        ),
      ).toBe(true);
    });
    const postCall = fetchStub.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/regulatory/sources") &&
        (init as RequestInit).method === "POST",
    );
    expect(postCall).toBeTruthy();
    const body = JSON.parse(
      String((postCall as unknown as [string, RequestInit])[1].body),
    );
    expect(body.authority_id).toBe(AUTHORITY_A.id);
  });

  it("disables register button when authority is not selected", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([
      AUTHORITY_A,
    ]);
    renderAdmin();
    await userEvent.setup().click(screen.getByRole("link", { name: "Register source" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Register regulatory source" })).toBeTruthy();
    });
    const submitBtn = screen.getByRole("button", { name: "Register source" });
    expect(submitBtn).toHaveAttribute("disabled");
  });

  it("shows upload section and selects a file", async () => {
    vi.stubGlobal("fetch", stubRegulatoryBackend({}));
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    const user = userEvent.setup();
    await user.click(screen.getByRole("link", { name: "Open source" }));
    await waitFor(() => {
      expect(screen.getByText("Artifacts")).toBeTruthy();
    });
    expect(screen.getByText("Upload original regulatory document")).toBeTruthy();
    expect(screen.getByLabelText("Choose file")).toBeTruthy();
  });

  it("uploads an artifact and displays it", async () => {
    const artifactsUrl = `/regulatory/sources/${SOURCE.id}/artifacts`;
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (url.endsWith("/regulatory/authorities")) {
        return new Response(JSON.stringify([AUTHORITY_A]), { status: 200 });
      }
      if (String(url).endsWith("/regulatory/sources") && (init as RequestInit | undefined)?.method === "GET") {
        return new Response(JSON.stringify({ items: [SOURCE], total: 1 }), { status: 200 });
      }
      if (String(url).endsWith("/regulatory/sources") && (init as RequestInit | undefined)?.method === "POST") {
        return new Response(JSON.stringify(NEW_SOURCE), { status: 201 });
      }
      if (String(url).endsWith(artifactsUrl)) {
        if ((init as RequestInit | undefined)?.method === "POST") {
          return new Response(
            JSON.stringify({
              id: "artifact-123",
              source_id: SOURCE.id,
              content_hash: "abc123",
              content_length: 1024,
              content_type: "application/pdf",
              acquisition_channel: "manual_upload",
              acquired_at: "2026-10-30T00:00:00Z",
              status: "validated",
              source_version: null,
              created_at: "2026-10-30T00:00:00Z",
              updated_at: "2026-10-30T00:00:00Z",
            }),
            { status: 201 },
          );
        }
        return new Response(JSON.stringify({ items: [], limit: 50, offset: 0, total: 0 }), { status: 200 });
      }
      return stubRegulatoryBackend({})(input, init);
    });
    vi.stubGlobal("fetch", fetchStub);
    vi.spyOn(regulatoryApi, "listRegulatoryAuthorities").mockResolvedValue([AUTHORITY_A]);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Open source" }));
    await waitFor(() => {
      expect(screen.getByText("Upload original regulatory document")).toBeTruthy();
    });
    const fileInput = screen.getByLabelText("Choose file") as HTMLInputElement;
    const pdfFile = new File([new Uint8Array(1024)], "test.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", {
      value: [pdfFile],
      writable: false,
    });
    fireEvent.change(fileInput);
    await waitFor(() => {
      expect(fileInput.files?.[0].name).toBe("test.pdf");
    });
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    await waitFor(() => {
      expect(screen.getByText(/Artifact.*uploaded/)).toBeTruthy();
    });
    // The POST body matches the backend contract, including the
    // browser-reported MIME type and the source's recorded version.
    const uploadPost = fetchStub.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith(artifactsUrl) &&
        (init as RequestInit).method === "POST",
    );
    expect(uploadPost).toBeTruthy();
    const uploadBody = JSON.parse(
      String((uploadPost as unknown as [string, RequestInit])[1].body),
    );
    expect(uploadBody.content_type).toBe("application/pdf");
    expect(uploadBody.source_version).toBe("1.0");
    expect(typeof uploadBody.content_base64).toBe("string");
    expect(uploadBody.content_base64.length).toBeGreaterThan(0);
    // Upload succeeded; artifacts refresh should converge.
    await waitFor(() => {
      expect(screen.getByText(/Artifact.*uploaded/)).toBeTruthy();
    });
  });

  it("uploads supported artifacts with an empty browser MIME via extension mapping", async () => {
    const artifactsUrl = `/regulatory/sources/${SOURCE.id}/artifacts`;
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (String(url).endsWith(artifactsUrl) && (init as RequestInit | undefined)?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "artifact-txt",
            source_id: SOURCE.id,
            content_hash: "hash-txt",
            content_length: 16,
            content_type: "text/plain",
            acquisition_channel: "manual_upload",
            acquired_at: "2026-10-30T00:00:00Z",
            status: "validated",
            source_version: "1.0",
            created_at: "2026-10-30T00:00:00Z",
            updated_at: "2026-10-30T00:00:00Z",
          }),
          { status: 201 },
        );
      }
      return stubRegulatoryBackend({})(input, init);
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Open source" }));
    await waitFor(() => {
      expect(screen.getByText("Upload original regulatory document")).toBeTruthy();
    });
    const fileInput = screen.getByLabelText("Choose file") as HTMLInputElement;
    // Browsers often report no MIME type for .txt uploads.
    const txtFile = new File([new Uint8Array(16)], "notes.txt", { type: "" });
    Object.defineProperty(fileInput, "files", {
      value: [txtFile],
      writable: false,
    });
    fireEvent.change(fileInput);
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    await waitFor(() => {
      expect(screen.getByText(/Artifact.*uploaded/)).toBeTruthy();
    });
    // The empty MIME is resolved against the extension so the backend
    // receives a type it actually accepts.
    const uploadPost = fetchStub.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith(artifactsUrl) &&
        (init as RequestInit).method === "POST",
    );
    expect(uploadPost).toBeTruthy();
    const uploadBody = JSON.parse(
      String((uploadPost as unknown as [string, RequestInit])[1].body),
    );
    expect(uploadBody.content_type).toBe("text/plain");
    expect(uploadBody.source_version).toBe("1.0");
    expect(uploadBody.content_base64.length).toBeGreaterThan(0);
  });

  it("rejects unsupported and oversized files without uploading", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Open source" }));
    await waitFor(() => {
      expect(screen.getByText("Upload original regulatory document")).toBeTruthy();
    });
    const fileInput = screen.getByLabelText("Choose file") as HTMLInputElement;
    // A file type the backend does not accept is refused at selection.
    const pngFile = new File([new Uint8Array(8)], "scan.png", { type: "image/png" });
    Object.defineProperty(fileInput, "files", {
      value: [pngFile],
      configurable: true,
    });
    fireEvent.change(fileInput);
    expect(
      await screen.findByText(/not a supported artifact format/),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Upload document" })).toHaveAttribute("disabled");
    // An oversized supported file is refused as well.
    const oversizedFile = new File(
      [new Uint8Array(10 * 1024 * 1024 + 1)],
      "big.pdf",
      { type: "application/pdf" },
    );
    Object.defineProperty(fileInput, "files", {
      value: [oversizedFile],
      configurable: true,
    });
    fireEvent.change(fileInput);
    expect(
      await screen.findByText(/over the 10 MB limit/),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Upload document" })).toHaveAttribute("disabled");
    // Neither rejection ever reached the backend.
    expect(
      fetchStub.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith(`/regulatory/sources/${SOURCE.id}/artifacts`) &&
          (init as RequestInit).method === "POST",
      ).length,
    ).toBe(0);
  });

  it("records an authorized retry for a terminally failed ingestion job", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await openSource(user);
    await openTab(user, "Ingestion");
    const jobsCallsBefore = fetchStub.mock.calls.filter(([url]) =>
      String(url).endsWith(`/regulatory/sources/${SOURCE.id}/ingestion-jobs`),
    ).length;
    await user.click(await screen.findByRole("button", { name: "Retry failed job" }));
    await waitFor(() => {
      expect(
        fetchStub.mock.calls.some(([url, init]) =>
          String(url).endsWith(`/regulatory/ingestion-jobs/${FAILED_JOB.id}/retry`) &&
          (init as RequestInit).method === "POST",
        ),
      ).toBe(true);
    });
    // The success message reports the new attempt as recorded, never
    // as already ingested — the worker still has to process it.
    expect(
      await screen.findByText(/Retry recorded as attempt 2/),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Retry failed job" }),
    ).toBeNull();
    await waitFor(() => {
      const jobsCallsAfter = fetchStub.mock.calls.filter(([url]) =>
        String(url).endsWith(`/regulatory/sources/${SOURCE.id}/ingestion-jobs`),
      ).length;
      expect(jobsCallsAfter).toBeGreaterThan(jobsCallsBefore);
    });
  });

  it("offers the retry action only for terminally failed jobs", async () => {
    const jobsUrl = `/regulatory/sources/${SOURCE.id}/ingestion-jobs`;
    const completedJob = {
      ...FAILED_JOB,
      id: "45454545-4545-4545-4545-454545454545",
      status: "completed",
      attempt_number: 1,
      error_details: null,
    };
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (String(url).endsWith(jobsUrl)) {
        return new Response(
          JSON.stringify({ items: [completedJob], limit: 50, offset: 0, total: 1 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return stubRegulatoryBackend({})(input, init);
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await user.click(screen.getByRole("link", { name: "Open source" }));
    expect(
      await screen.findAllByText("Regulation (EU) 2019/1793"),
    ).toBeTruthy();
    expect(
      fetchStub.mock.calls.some(([url]) => String(url).endsWith(jobsUrl)),
    ).toBe(true);
    expect(screen.queryByRole("button", { name: "Retry failed job" })).toBeNull();
  });

  it("does not offer retry for an older failed attempt after a later attempt exists", async () => {
    const jobsUrl = `/regulatory/sources/${SOURCE.id}/ingestion-jobs`;
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (String(url).endsWith(jobsUrl)) {
        return new Response(
          JSON.stringify({
            items: [FAILED_JOB, RETRIED_JOB],
            limit: 50,
            offset: 0,
            total: 2,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return stubRegulatoryBackend({})(input, init);
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await openSource(user);
    await openTab(user, "Ingestion");

    expect(await screen.findByText("failed")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry failed job" })).toBeNull();
  });

  it("records a wording correction together with a verified Stage A decision", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await openCandidateReview(user);
    const rationale = await screen.findByLabelText("Rationale (required)", {
      selector: "#stage-a-rationale",
    });
    fireEvent.change(rationale, {
      target: { value: "Wording did not match the artifact scan." },
    });
    const corrected = screen.getByLabelText(
      "Corrected requirement wording (optional, verified decisions only)",
    );
    fireEvent.change(corrected, {
      target: {
        value:
          "All cocoa exports require a phytosanitary certificate issued within 14 days.",
      },
    });
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
    const body = JSON.parse(
      String((stageACall as unknown as [string, RequestInit])[1].body),
    );
    expect(body).toEqual({
      stage_a_status: "verified",
      rationale: "Wording did not match the artifact scan.",
      corrected_requirement_text:
        "All cocoa exports require a phytosanitary certificate issued within 14 days.",
    });
  });

  it("does not send corrected wording with a non-verified decision", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await openCandidateReview(user);
    fireEvent.change(
      document.getElementById("stage-a-decision") as HTMLSelectElement,
      { target: { value: "rejected" } },
    );
    const rationale = await screen.findByLabelText("Rationale (required)", {
      selector: "#stage-a-rationale",
    });
    fireEvent.change(rationale, {
      target: { value: "Traceability could not be confirmed." },
    });
    const corrected = screen.getByLabelText(
      "Corrected requirement wording (optional, verified decisions only)",
    );
    fireEvent.change(corrected, {
      target: {
        value: "Wording that would not be allowed to accompany a rejection.",
      },
    });
    await user.click(screen.getByRole("button", { name: "Record Stage A verification" }));
    expect(
      await screen.findByText(
        /Corrected wording can only be recorded with a verified decision/,
      ),
    ).toBeTruthy();
    expect(
      fetchStub.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/stage-a") &&
          (init as RequestInit).method === "POST",
      ).length,
    ).toBe(0);
  });

  it("lists recorded wording corrections append-only", async () => {
    const correctionsUrl = `/regulatory/candidates/${CANDIDATE.id}/wording-corrections`;
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (String(url).endsWith(correctionsUrl)) {
        return new Response(
          JSON.stringify({ items: [WORDING_CORRECTION], total: 1 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return stubRegulatoryBackend({})(input, init);
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await openCandidateReview(user);
    // Both wordings are shown verbatim: the preserved original and the
    // operative corrected text.
    expect(
      await screen.findByText(
        "Original: All cocoa exports require a phytosanitary certificate.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Corrected: All cocoa exports require a phytosanitary certificate issued within 14 days.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Rationale: Extraction dropped the validity window for the certificate.",
      ),
    ).toBeTruthy();
  });

  it("withdraws a source with a mandatory rationale and records flags raised", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await openSource(user);
    await openTab(user, "Details");
    const rationale = await screen.findByLabelText("Withdrawal rationale (required)");
    fireEvent.change(rationale, {
      target: { value: "Authority retracted the regulation." },
    });
    await user.click(screen.getByRole("button", { name: "Withdraw source" }));
    await waitFor(() => {
      expect(
        fetchStub.mock.calls.some(([url, init]) =>
          String(url).endsWith(`/regulatory/sources/${SOURCE.id}/withdrawal`) &&
          (init as RequestInit).method === "POST",
        ),
      ).toBe(true);
    });
    const withdrawalCall = fetchStub.mock.calls.find(([url, init]) =>
      String(url).endsWith(`/regulatory/sources/${SOURCE.id}/withdrawal`) &&
      (init as RequestInit).method === "POST",
    );
    expect(
      JSON.parse(String((withdrawalCall as unknown as [string, RequestInit])[1].body)),
    ).toEqual({ rationale: "Authority retracted the regulation." });
    // The result is reported exactly as the backend records it: status
    // and governance flags raised, never as a fabricated retraction.
    expect(
      await screen.findByText(
        /Source withdrawn as recorded\. Status: withdrawn; 1 pending withdrawal governance flag/,
      ),
    ).toBeTruthy();
  });

  it("requires a rationale before withdrawal", async () => {
    const fetchStub = stubRegulatoryBackend({});
    vi.stubGlobal("fetch", fetchStub);
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    const user = userEvent.setup();
    await openSource(user);
    await openTab(user, "Details");
    const withdrawButton = (await screen.findByRole("button", {
      name: "Withdraw source",
    })) as HTMLButtonElement;
    // No rationale, no withdrawal: the action is not even sendable.
    expect(withdrawButton.disabled).toBe(true);
    expect(
      fetchStub.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/withdrawal") &&
          (init as RequestInit).method === "POST",
      ).length,
    ).toBe(0);
  });

  it("does not offer withdrawal for an already withdrawn source", async () => {
    const sourceUrl = `/regulatory/sources/${SOURCE.id}`;
    const withdrawnSource = { ...SOURCE, status: "withdrawn" };
    const fetchStub = vi.fn(async (input: string | Request, init?: RequestInit): Promise<Response> => {
      const url = typeof input === "string" ? input : input.url;
      if (String(url).endsWith(sourceUrl)) {
        return new Response(JSON.stringify(withdrawnSource), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return stubRegulatoryBackend({})(input, init);
    });
    vi.stubGlobal("fetch", fetchStub);
    const user = userEvent.setup();
    renderAdmin();
    await waitFor(() => {
      expect(screen.getByText("Regulation (EU) 2019/1793")).toBeTruthy();
    });
    await openSource(user);
    await openTab(user, "Details");
    expect(
      await screen.findByText(
        /already withdrawn\. The backend refuses a further withdrawal/,
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Withdraw source" })).toBeNull();
  });
});