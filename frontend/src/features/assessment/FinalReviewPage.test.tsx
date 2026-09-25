import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AnalysisProvider } from "../../app/AnalysisContext";
import { AssessmentProvider } from "../../app/AssessmentContext";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { FinalReviewPage } from "./FinalReviewPage";
import type {
  AnalysisFinding,
  AnalysisReport,
  FinalPackage,
  WorkflowRecord,
} from "../../types/api";

const WORKFLOW_ID = "11111111-1111-1111-1111-111111111111";
const REQUIREMENT_ID = "44444444-4444-4444-4444-444444444444";
const EVIDENCE_ID = "77777777-7777-7777-7777-777777777777";
const REPORT_ID = "99999999-9999-9999-9999-999999999999";

const RECORD: WorkflowRecord = {
  id: WORKFLOW_ID,
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: "55555555-5555-5555-5555-555555555555",
  state: "review_required",
  rounds: [
    {
      round_index: 1,
      report_id: REPORT_ID,
      analysis_ids: [],
      trace_ids: [],
      input_fingerprints: [],
    },
  ],
  supplied_evidence_ids: [EVIDENCE_ID],
  open_requirements: [REQUIREMENT_ID],
};

const FINDING: AnalysisFinding = {
  analysis_id: "a-1",
  requirement_id: REQUIREMENT_ID,
  requirement_text: "Present a phytosanitary certificate before export.",
  applicability: "applicable",
  assessment: "unknown",
  explanation: "The filing is not yet evidenced.",
  uncertainty: "uncertain",
  uncertainty_explanation: "",
  evidence_sufficiency: "insufficient",
  sufficiency_explanation: "",
  contradiction_state: "present",
  missing_information: ["Certificate copy missing."],
  supporting_evidence: [{ evidence_id: EVIDENCE_ID, status: "accepted" }],
  conflicting_evidence: [{ evidence_id: "ev-2", status: "rejected" }],
  knowledge_references: [],
  sources: [],
  missing_items: [],
};

const REPORT: AnalysisReport = {
  report_id: REPORT_ID,
  case_id: RECORD.case_id,
  counts: {},
  requirements_with_missing_information: [REQUIREMENT_ID],
  uncertain_requirement_ids: [REQUIREMENT_ID],
  requirements_with_conflicting_evidence: [REQUIREMENT_ID],
  conflicting_evidence_count: 1,
  findings: [FINDING],
};

const PACKAGE: FinalPackage = {
  workflow_id: WORKFLOW_ID,
  tenant_id: RECORD.tenant_id,
  case_id: RECORD.case_id,
  shipment_id: RECORD.shipment_id,
  state: "assessment_package_ready",
  round_count: 1,
  open_requirements: [REQUIREMENT_ID],
  report: REPORT,
  decision_summary: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderPage(record: WorkflowRecord = RECORD) {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  render(
    <MemoryRouter initialEntries={["/workspace/final-review"]}>
      <AuthProvider initial={{ devTenantId: RECORD.tenant_id }}>
        <WorkflowProvider>
          <AnalysisProvider>
            <AssessmentProvider>
              <Routes>
                <Route path="/workspace" element={<Outlet />}>
                  <Route path="final-review" element={<FinalReviewPage />} />
                  <Route path="package" element={<div>Package screen</div>} />
                  <Route path="analysis" element={<div>Analysis screen</div>} />
                  <Route path="history" element={<div>History screen</div>} />
                </Route>
              </Routes>
            </AssessmentProvider>
          </AnalysisProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function routeRefused(url: string, init?: RequestInit): Promise<Response> {
  void init;
  if (url.startsWith("http://localhost:8000/compliance/reports/")) {
    return Promise.resolve(new Response(JSON.stringify(REPORT), { status: 200 }));
  }
  return Promise.resolve(
    new Response(
      JSON.stringify({
        error: {
          code: "not_ready",
          message: "workflow is not ready: shipment is not bound",
          details: {
            reasons: [{ code: "shipment_unbound", detail: "no shipment reference is bound" }],
          },
        },
      }),
      { status: 409 },
    ),
  );
}

function routeFinalized(url: string, init?: RequestInit): Promise<Response> {
  void init;
  if (url.startsWith("http://localhost:8000/compliance/reports/")) {
    return Promise.resolve(new Response(JSON.stringify(REPORT), { status: 200 }));
  }
  return Promise.resolve(
    new Response(
      JSON.stringify({
        workflow: { ...RECORD, state: "assessment_package_ready" },
        package: PACKAGE,
      }),
      { status: 201 },
    ),
  );
}

describe("FinalReviewPage", () => {
  const reasonCallBodies = new Set<string>();
  void reasonCallBodies;

  async function route(url: string, init?: RequestInit): Promise<Response> {
    const body = init?.body ? String(init.body) : "";
    reasonCallBodies.add(`${init?.method ?? "GET"} ${url} ${body}`);
    if (url.startsWith("http://localhost:8000/compliance/reports/")) {
      return new Response(JSON.stringify(REPORT), { status: 200 });
    }
    return finalizeWorkflow(url, body);
  }

  async function finalizeWorkflow(url: string, body: string): Promise<Response> {
    if (url.endsWith("/compliance/workflows/finalize") && body) {
      return new Response(
        JSON.stringify({
          workflow: { ...RECORD, state: "assessment_package_ready" },
          package: PACKAGE,
        }),
        { status: 201 },
      );
    }
    return routeRefused(url);
  }

  it("presents the package contents from the DTO without inventing a verdict", async () => {
    vi.stubGlobal("fetch", route as typeof fetch);
    renderPage();
    expect(
      await screen.findByText("What the finalized package will contain"),
    ).toBeInTheDocument();
    expect(await screen.findByTitle(WORKFLOW_ID)).toBeInTheDocument();
    const contents = screen.getByRole("region", { name: "What the package will contain" });
    expect(within(contents).getAllByTitle(REQUIREMENT_ID).length).toBeGreaterThan(0);
    expect(
      screen.getByText("Present a phytosanitary certificate before export."),
    ).toBeInTheDocument();
    expect(screen.getByText("Certificate copy missing.")).toBeInTheDocument();
    expect(screen.getByText(/no verdict, score/i)).toBeInTheDocument();
    // Undecided states are shown verbatim, never collapsed into failure.
    expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\d+\s*%/);
    expect(text).not.toMatch(/\bpassed\b|\bfailed\b/i);
    expect(text).not.toMatch(/overall compliance/i);
  });

  it("presents backend readiness blockers when finalization is refused", async () => {
    const finalizeCalls: string[] = [];
    vi.stubGlobal(
      "fetch",
      (async (url: string, init?: RequestInit) => {
        if (url.startsWith("http://localhost:8000/compliance/reports/")) {
          return new Response(JSON.stringify(REPORT), { status: 200 });
        }
        finalizeCalls.push(String(init?.body ?? ""));
        return routeRefused(url, init);
      }) as typeof fetch,
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByTitle(WORKFLOW_ID);
    expect(
      screen.getByText("Present a phytosanitary certificate before export."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Review complete" }));
    const panel = screen.getByRole("group", { name: "Finalization confirmation" });
    expect(panel).toHaveTextContent(/finalization is permanent/i);
    expect(panel).toHaveTextContent(/no reopen or versioning operation/i);
    await user.click(screen.getByRole("button", { name: "Finalize assessment package" }));
    expect(
      await screen.findByText(/not ready for this action yet/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Readiness blockers reported by the backend" }),
    ).toBeInTheDocument();
    expect(screen.getByText("shipment_unbound")).toBeInTheDocument();
    expect(screen.getByText("no shipment reference is bound")).toBeInTheDocument();
    // The workflow is untouched: no package screen, and confirmation is dismissed.
    expect(screen.queryByText("Package screen")).toBeNull();
    expect(screen.queryByRole("button", { name: "Back to review" })).toBeNull();
    expect(finalizeCalls).toHaveLength(1);
    expect(JSON.parse(finalizeCalls[0])).toEqual({ workflow: RECORD });
  });

  it("finalizes only on explicit confirmation and stores the returned package", async () => {
    const finalizeCalls: Array<[string, RequestInit | undefined]> = [];
    vi.stubGlobal(
      "fetch",
      (async (url: string, init?: RequestInit) => {
        if (url.startsWith("http://localhost:8000/compliance/reports/")) {
          return new Response(JSON.stringify(REPORT), { status: 200 });
        }
        finalizeCalls.push([url, init]);
        return routeFinalized(url, init);
      }) as typeof fetch,
    );
    const user = userEvent.setup();
    renderPage();
    // The stored report loads once for the latest recorded round.
    await screen.findByTitle(WORKFLOW_ID);
    // Nothing terminal happens until the user confirms twice.
    await user.click(screen.getByRole("button", { name: "Review complete" }));
    expect(finalizeCalls).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Finalize assessment package" }));
    await waitFor(() => expect(screen.getByText("Package screen")).toBeInTheDocument());
    expect(finalizeCalls).toHaveLength(1);
    const [url, init] = finalizeCalls[0];
    expect(url).toBe("http://localhost:8000/compliance/workflows/finalize");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ workflow: RECORD });
    const stored = JSON.parse(
      sessionStorage.getItem("xportra.workflow-record.v1") ?? "{}",
    ) as WorkflowRecord;
    expect(stored.state).toBe("assessment_package_ready");
  });

  it("offers no finalization control once the workflow is terminal", () => {
    renderPage({ ...RECORD, state: "assessment_package_ready" });
    expect(
      screen.getByText(/finalized — the final review is closed/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Review complete" })).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Finalize assessment package" }),
    ).toBeNull();
    expect(screen.getByText(/already finalized/i)).toBeInTheDocument();
  });

  it("reads the latest stored report when the session holds none", async () => {
    const spy = vi.fn(
      async () => new Response(JSON.stringify(REPORT), { status: 200 }),
    );
    vi.stubGlobal("fetch", spy);
    renderPage(RECORD);
    expect(
      await screen.findByText("Present a phytosanitary certificate before export."),
    ).toBeInTheDocument();
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`http://localhost:8000/compliance/reports/${REPORT_ID}`);
    expect(init.method ?? "GET").toBe("GET");
    expect(screen.getByText(/analysis round 1/i)).toBeInTheDocument();
  });
});
