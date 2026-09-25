import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AssessmentProvider } from "../../app/AssessmentContext";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { PackagePage } from "./PackagePage";
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
  state: "assessment_package_ready",
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
  contradiction_state: "none",
  missing_information: ["Certificate copy missing."],
  supporting_evidence: [{ evidence_id: EVIDENCE_ID, status: "accepted" }],
  conflicting_evidence: [],
  knowledge_references: [],
  sources: [],
  missing_items: [],
};

const REPORT: AnalysisReport = {
  report_id: REPORT_ID,
  case_id: RECORD.case_id,
  counts: { findings_recorded: 1 },
  requirements_with_missing_information: [REQUIREMENT_ID],
  uncertain_requirement_ids: [REQUIREMENT_ID],
  requirements_with_conflicting_evidence: [],
  conflicting_evidence_count: 0,
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
  decision_summary: { summary_note: "Hold pending certificate." },
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderPage(pkg?: FinalPackage, spy?: ReturnType<typeof vi.fn>) {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(RECORD));
  vi.stubGlobal(
    "fetch",
    spy ?? vi.fn(async () => new Response(JSON.stringify(pkg ?? PACKAGE), { status: 200 })),
  );
  render(
    <MemoryRouter initialEntries={["/workspace/package"]}>
      <AuthProvider initial={{ devTenantId: RECORD.tenant_id }}>
        <WorkflowProvider>
          <AssessmentProvider>
            <Routes>
              <Route path="/workspace" element={<Outlet />}>
                <Route path="package" element={<PackagePage />} />
                <Route path="final-review" element={<div>Review screen</div>} />
                <Route path="history" element={<div>History screen</div>} />
                <Route path="report/:reportId" element={<div>Report screen</div>} />
              </Route>
            </Routes>
          </AssessmentProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
  return;
}

type FetchCall = [string, RequestInit];

describe("PackagePage", () => {
  it("reads the stored package and renders its fields from the DTO", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(PACKAGE), { status: 200 }));
    renderPage(undefined, spy);
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/package");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ workflow: RECORD });
    expect(await screen.findByTitle(WORKFLOW_ID)).toBeInTheDocument();
    expect(screen.getByTitle(REPORT_ID)).toBeInTheDocument();
    expect(
      screen.getByText("Present a phytosanitary certificate before export."),
    ).toBeInTheDocument();
    expect(screen.getByText("Hold pending certificate.")).toBeInTheDocument();
    expect(screen.getByText("findings recorded")).toBeInTheDocument();
    // The open-requirement snapshot is preserved exactly, not rewritten.
    const snapshot = screen.getByRole("region", { name: "Open requirements at finalization" });
    expect(within(snapshot).getByTitle(REQUIREMENT_ID)).toBeInTheDocument();
  });

  it("presents the terminal state through text with no mutating controls", async () => {
    renderPage();
    expect(
      await screen.findByText(
        "Assessment package finalized — this workflow is permanently closed",
      ),
    ).toBeInTheDocument();
    for (const name of [
      "Finalize assessment package",
      "Review complete",
      "Run analysis",
      "Re-run analysis",
      "Supply to workflow",
      "Request additional evidence",
      "Register evidence reference",
    ]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    expect(screen.getByRole("link", { name: "Open stored report" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View workflow history" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review record" })).toBeInTheDocument();
  });

  it("shows counts as informational receipts with no invented verdict", async () => {
    renderPage();
    await screen.findByTitle(WORKFLOW_ID);
    expect(screen.getByText(/informational receipt counts/i)).toBeInTheDocument();
    expect(screen.getByText(/never shown as failure/i)).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\b\d+\s*%/);
    expect(text).not.toMatch(/overall/i);
    expect(text).not.toMatch(/verdict/i);
  });

  it("renders an empty open-requirement snapshot as empty, not as compliant", async () => {
    renderPage({ ...PACKAGE, open_requirements: [] });
    expect(
      await screen.findByText(/recorded as an empty snapshot, not as compliance/i),
    ).toBeInTheDocument();
  });
});
