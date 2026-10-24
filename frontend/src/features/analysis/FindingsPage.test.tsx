import { describe, expect, it, afterEach, vi } from "vitest";
import { useEffect } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { AnalysisProvider, useAnalysis } from "../../app/AnalysisContext";
import { ConversationProvider } from "../conversation/ConversationContext";
import { FindingsPage } from "./FindingsPage";
import type { AnalysisFinding, AnalysisReport, WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "analysis_available",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: ["44444444-4444-4444-4444-444444444444"],
};

function finding(overrides: Partial<AnalysisFinding> = {}): AnalysisFinding {
  return {
    analysis_id: "a1",
    requirement_id: "44444444-4444-4444-4444-444444444444",
    requirement_text: "File form X before export.",
    applicability: "applicable",
    assessment: "unknown",
    explanation: "The evidence does not yet establish the filing.",
    uncertainty: "uncertain",
    uncertainty_explanation: "",
    evidence_sufficiency: "insufficient",
    sufficiency_explanation: "",
    contradiction_state: "none",
    missing_information: ["Certificate copy missing."],
    supporting_evidence: [{ evidence_id: "ev-1", status: "accepted" }],
    conflicting_evidence: [],
    knowledge_references: [],
    sources: [{ kind: "authority", identifier: "NG-SON" }],
    missing_items: [],
    ...overrides,
  };
}

const REPORT: AnalysisReport = {
  report_id: "99999999-9999-9999-9999-999999999999",
  case_id: RECORD.case_id,
  counts: {},
  requirements_with_missing_information: ["44444444-4444-4444-4444-444444444444"],
  uncertain_requirement_ids: ["44444444-4444-4444-4444-444444444444"],
  requirements_with_conflicting_evidence: [],
  conflicting_evidence_count: 0,
  findings: [
    finding(),
    finding({
      analysis_id: "a2",
      requirement_id: "55555555-5555-5555-5555-555555555555",
      requirement_text: "Label goods in English.",
      assessment: "satisfied",
      uncertainty: "determined",
      evidence_sufficiency: "supported",
      missing_information: [],
      contradiction_state: "present",
      conflicting_evidence: [{ evidence_id: "ev-9", status: "rejected" }],
    }),
  ],
};

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

const NO_CASES: Array<Record<string, unknown>> = [];

function renderWithReport(report: AnalysisReport | null, record: WorkflowRecord = RECORD) {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  function Seed() {
    const { setAnalysis } = useAnalysis();
    useEffect(() => {
      if (report) {
        setAnalysis(report, NO_CASES);
      }
    }, [setAnalysis]);
    return <FindingsPage />;
  }
  render(
    <MemoryRouter initialEntries={["/workspace/review"]}>
      <AuthProvider>
        <WorkflowProvider>
          <ConversationProvider>
          <AnalysisProvider>
            <Routes>
              <Route path="/workspace/review" element={<Seed />} />
            </Routes>
          </AnalysisProvider>
          </ConversationProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("FindingsPage", () => {
  it("asks for an analysis run when no report exists", () => {
    renderWithReport(null);
    expect(screen.getByText("No analysis yet")).toBeInTheDocument();
  });

  it("summarizes counts without scoring or verdicts", () => {
    renderWithReport(REPORT);
    expect(screen.getByRole("heading", { name: "Your analysis results" })).toBeInTheDocument();
    // Primary status labels are plain-language mappings, never raw enums.
    const allowed = new Set([
      "Still checking",
      "Addressed in this analysis",
    ]);
    for (const badge of document.querySelectorAll(".badge")) {
      expect(allowed.has(badge.textContent?.trim() ?? "")).toBe(true);
    }
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\b\d+\s*%/);
  });

  it("renders both findings with full sections", () => {
    renderWithReport(REPORT);
    expect(screen.getByText("File form X before export.")).toBeInTheDocument();
    expect(screen.getByText("Label goods in English.")).toBeInTheDocument();
    expect(screen.getByText("Certificate copy missing.")).toBeInTheDocument();
    expect(document.body.textContent).toContain("NG-SON");
  });

  it("keeps uncertainty and contradiction honest", () => {
    renderWithReport(REPORT);
    expect(screen.getAllByText("Still checking").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Conflicting evidence recorded").length).toBeGreaterThan(0);
    expect(screen.getByText(/shown as recorded, not resolved/i)).toBeInTheDocument();
    expect(screen.getByText(/government decision, or approval to export/i)).toBeInTheDocument();
    const text = document.body.textContent?.toLowerCase() ?? "";
    expect(text).not.toMatch(/\bfailed\b/);
  });

  it("counts overlapping rollups once and prioritizes the next evidence action", () => {
    renderWithReport(REPORT);
    expect(screen.getByText("Distinct requirements in those groups").parentElement).toHaveTextContent("1");
    const next = within(screen.getByRole("region", { name: "Next shipment step" }));
    expect(next.getByRole("link", { name: "Review shipment evidence" })).toHaveAttribute("href", "/evidence");
    const otherActions = screen.getByText("Other shipment actions").closest("details");
    expect(otherActions).not.toHaveAttribute("open");
    expect(within(otherActions as HTMLElement).getByRole("link", { name: "Request additional evidence" })).toHaveAttribute(
      "href",
      "/additional-evidence",
    );
  });

  it("offers the final review as the next step when the latest report has no information gaps", () => {
    const completeReport = {
      ...REPORT,
      requirements_with_missing_information: [],
      uncertain_requirement_ids: [],
      requirements_with_conflicting_evidence: [],
      conflicting_evidence_count: 0,
      findings: [
        finding({
          assessment: "satisfied",
          uncertainty: "determined",
          evidence_sufficiency: "supported",
          contradiction_state: "none",
          missing_information: [],
          conflicting_evidence: [],
        }),
      ],
    };
    renderWithReport(completeReport);
    const next = within(screen.getByRole("region", { name: "Next shipment step" }));
    expect(next.getByRole("link", { name: "Continue to final review" })).toHaveAttribute("href", "/final-review");
  });

  it("prioritizes evidence review for uncertainty or conflict even without missing-information rollups", () => {
    const uncertainReport = {
      ...REPORT,
      requirements_with_missing_information: [],
      uncertain_requirement_ids: [],
      requirements_with_conflicting_evidence: [],
      conflicting_evidence_count: 0,
      findings: [
        finding({
          assessment: "unknown",
          missing_information: [],
          uncertainty: "uncertain",
          contradiction_state: "present",
          conflicting_evidence: [{ evidence_id: "ev-2", status: "rejected" }],
        }),
      ],
    };
    renderWithReport(uncertainReport);
    const next = within(screen.getByRole("region", { name: "Next shipment step" }));
    expect(next.getByRole("link", { name: "Review shipment evidence" })).toHaveAttribute("href", "/evidence");
  });

  it("keeps undetermined support and conflict states on an evidence-review path", () => {
    const unresolvedReport = {
      ...REPORT,
      requirements_with_missing_information: [],
      uncertain_requirement_ids: [],
      requirements_with_conflicting_evidence: [],
      conflicting_evidence_count: 0,
      findings: [
        finding({
          assessment: "satisfied",
          uncertainty: "unknown",
          contradiction_state: "unknown",
          evidence_sufficiency: "unknown",
          missing_information: [],
          conflicting_evidence: [],
        }),
      ],
    };
    renderWithReport(unresolvedReport);
    const next = within(screen.getByRole("region", { name: "Next shipment step" }));
    expect(next.getByRole("link", { name: "Review shipment evidence" })).toHaveAttribute("href", "/evidence");
  });

  it("does not treat an empty findings list as proof of compliance or clearance", () => {
    renderWithReport({
      ...REPORT,
      findings: [],
      requirements_with_missing_information: [],
      uncertain_requirement_ids: [],
      requirements_with_conflicting_evidence: [],
      conflicting_evidence_count: 0,
    });
    expect(screen.getByRole("note")).toHaveTextContent(/does not establish compliance/i);
    expect(screen.getByRole("note")).toHaveTextContent(/cleared for export/i);
  });

  it("keeps a finalized shipment read-only and directs to its package", () => {
    renderWithReport(REPORT, { ...RECORD, state: "assessment_package_ready" });
    const next = within(screen.getByRole("region", { name: "Next shipment step" }));
    expect(next.getByRole("link", { name: "View assessment package" })).toHaveAttribute("href", "/package");
  });

  it("filters findings by recorded group without inventing categories", async () => {
    const user = userEvent.setup();
    renderWithReport(REPORT);
    await screen.findByText("File form X before export.");
    // Group counts come straight from the stored report.
    expect(screen.getByRole("button", { name: "All findings (2)" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Needs information (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Uncertain (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Contradictions (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unresolved (1)" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Uncertain (1)" }));
    expect(screen.getByText("File form X before export.")).toBeInTheDocument();
    expect(screen.queryByText("Label goods in English.")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Contradictions (1)" }));
    expect(screen.getByText("Label goods in English.")).toBeInTheDocument();
    expect(screen.queryByText("File form X before export.")).toBeNull();
  });
});

describe("FindingsPage persisted-report rehydration", () => {
  const ROUNDED_RECORD: WorkflowRecord = {
    ...RECORD,
    state: "analysis_available",
    rounds: [
      {
        round_index: 1,
        report_id: REPORT.report_id,
        analysis_ids: [],
        trace_ids: [],
        input_fingerprints: [],
      },
    ],
  };

  function stubJson(body: unknown, status = 200) {
    const spy = vi.fn(async () => new Response(JSON.stringify(body), { status }));
    vi.stubGlobal("fetch", spy);
    return spy;
  }

  function renderReloaded() {
    sessionStorage.setItem(
      "xportra.workflow-record.v1",
      JSON.stringify(ROUNDED_RECORD),
    );
    // No in-memory seeding: simulates a reload where only
    // the workflow record (with recorded rounds) survives.
    render(
      <MemoryRouter initialEntries={["/workspace/review"]}>
        <AuthProvider>
          <WorkflowProvider>
            <ConversationProvider>
              <AnalysisProvider>
                <Routes>
                  <Route path="/workspace/review" element={<FindingsPage />} />
                </Routes>
              </AnalysisProvider>
            </ConversationProvider>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
  }

  it("renders the persisted report after reload (Test B)", async () => {
    const spy = stubJson(REPORT);
    renderReloaded();
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Your analysis results" }),
      ).toBeInTheDocument();
    });
    const urls = spy.mock.calls.map((call) => {
      const [url] = call as unknown as [string, RequestInit];
      return url;
    });
    expect(urls).toEqual([
      `http://localhost:8000/compliance/reports/${REPORT.report_id}`,
    ]);
    expect(screen.queryByText("No analysis yet")).toBeNull();
  });

  it("shows a loading state before the persisted report arrives", () => {
    let release!: (value: unknown) => void;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => gate.then(() => new Response(JSON.stringify(REPORT), { status: 200 }))),
    );
    renderReloaded();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Reading the stored analysis…",
    );
    expect(screen.queryByText("No analysis yet")).toBeNull();
    release(null);
  });

  it("surfaces load failure distinctly from absence (Test D)", async () => {
    stubJson({ error: { code: "unexpected_error", message: "boom" } }, 500);
    renderReloaded();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.queryByText("No analysis yet")).toBeNull();
    expect(screen.queryByText("Findings review")).toBeNull();
  });

  it("reports a missing stored report distinctly from failure", async () => {
    stubJson({ error: { code: "not_found", message: "gone" } }, 404);
    renderReloaded();
    await waitFor(() => {
      expect(screen.getByText("Report unavailable")).toBeInTheDocument();
    });
    expect(screen.queryByText("No analysis yet")).toBeNull();
  });
});
