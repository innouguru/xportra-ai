import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ReportPage } from "./ReportPage";
import type { AnalysisFinding, AnalysisReport, WorkflowRecord } from "../../types/api";

const REPORT_ID = "99999999-9999-9999-9999-999999999999";
const REQUIREMENT_ID = "44444444-4444-4444-4444-444444444444";
const OTHER_REQUIREMENT_ID = "55555555-5555-5555-5555-555555555555";
const EVIDENCE_ID = "77777777-7777-7777-7777-777777777777";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "analysis_available",
  rounds: [
    {
      round_index: 1,
      report_id: REPORT_ID,
      analysis_ids: ["a-1"],
      trace_ids: ["t-1"],
      input_fingerprints: [],
    },
  ],
  supplied_evidence_ids: [EVIDENCE_ID],
  open_requirements: [],
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
  contradiction_state: "none",
  missing_information: ["Certificate copy missing."],
  supporting_evidence: [{ evidence_id: EVIDENCE_ID, status: "accepted", uri: "registry://NG-1" }],
  conflicting_evidence: [],
  knowledge_references: [{ regulation: "NG-SON-118" }],
  sources: [{ kind: "authority", identifier: "NG-SON" }],
  missing_items: [],
};

const REPORT: AnalysisReport = {
  report_id: REPORT_ID,
  case_id: RECORD.case_id,
  counts: { findings_recorded: 2 },
  requirements_with_missing_information: [REQUIREMENT_ID],
  uncertain_requirement_ids: [REQUIREMENT_ID],
  requirements_with_conflicting_evidence: [OTHER_REQUIREMENT_ID],
  conflicting_evidence_count: 0,
  findings: [
    FINDING,
    {
      ...FINDING,
      analysis_id: "a-2",
      requirement_id: OTHER_REQUIREMENT_ID,
      requirement_text: "Label goods in English.",
      assessment: "satisfied",
      uncertainty: "determined",
      evidence_sufficiency: "supported",
      contradiction_state: "present",
      missing_information: [],
      supporting_evidence: [],
      conflicting_evidence: [{ evidence_id: "ev-2", status: "rejected" }],
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderPage() {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(RECORD));
  render(
    <MemoryRouter initialEntries={[`/workspace/report/${REPORT_ID}`]}>
      <AuthProvider initial={{ devTenantId: RECORD.tenant_id }}>
        <WorkflowProvider>
          <Routes>
            <Route path="/workspace" element={<Outlet />}>
              <Route path="report/:reportId" element={<ReportPage />} />
              <Route path="package" element={<div>Package screen</div>} />
              <Route path="history" element={<div>History screen</div>} />
            </Route>
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

type FetchCall = [string, RequestInit];

describe("ReportPage", () => {
  it("reads the stored report over GET and presents context first", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(REPORT), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    renderPage();
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe(`http://localhost:8000/compliance/reports/${REPORT_ID}`);
    expect(init.method ?? "GET").toBe("GET");
    expect(await screen.findByTitle(REPORT_ID)).toBeInTheDocument();
    expect(screen.getByText("Assessment context")).toBeInTheDocument();
    expect(screen.getByText("Round 1 of 1 recorded")).toBeInTheDocument();
  });

  it("prioritizes findings, evidence, missing information, and uncertainty", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(REPORT), { status: 200 })),
    );
    renderPage();
    await screen.findByTitle(REPORT_ID);
    expect(
      screen.getByText("Present a phytosanitary certificate before export."),
    ).toBeInTheDocument();
    expect(screen.getByText("Label goods in English.")).toBeInTheDocument();
    // Evidence/support section renders the recorded reference verbatim.
    const support = screen.getByRole("region", { name: "Evidence and support" });
    expect(within(support).getByText("registry://NG-1")).toBeInTheDocument();
    // Missing-information section carries both the identifier and the item.
    expect(screen.getAllByText("Certificate copy missing.").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle(OTHER_REQUIREMENT_ID).length).toBeGreaterThan(0);
    // Authoritative summary stays a package reference, not a reconstruction.
    expect(screen.getByText(/carried by the workflow's final assessment package/i)).toBeInTheDocument();
  });

  it("renders uncertainty and contradictions without reinterpretation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(REPORT), { status: 200 })),
    );
    renderPage();
    await screen.findByTitle(REPORT_ID);
    expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
    expect(screen.getByText(/undecided, not failed/i)).toBeInTheDocument();
    expect(screen.getByText(/never presented as\s+non-compliance/i)).toBeInTheDocument();
    expect(document.querySelectorAll(".badge").length).toBeGreaterThan(0);
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\b\d+\s*%/);
    expect(text).not.toMatch(/overall/i);
    // "failed" only ever appears inside the explicit anti-collapse qualifier.
    const withoutQualifiers = text.split("undecided, not failed").join("");
    expect(withoutQualifiers).not.toMatch(/\bfailed\b/i);
  });

  it("reports a report it cannot load without inventing content", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                code: "not_found",
                message: "The requested record was not found in this workspace.",
              },
            }),
            { status: 404 },
          ),
      ),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The requested record was not found in this workspace.",
    );
  });
});
