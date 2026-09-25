import { describe, expect, it, afterEach } from "vitest";
import { useEffect } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { AnalysisProvider, useAnalysis } from "../../app/AnalysisContext";
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
});

const NO_CASES: Array<Record<string, unknown>> = [];

function renderWithReport(report: AnalysisReport | null) {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(RECORD));
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
          <AnalysisProvider>
            <Routes>
              <Route path="/workspace/review" element={<Seed />} />
            </Routes>
          </AnalysisProvider>
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
    expect(screen.getByText("Findings review — 2 requirements reviewed")).toBeInTheDocument();
    // Badges are the only verdict-like UI elements: every badge
    // must carry a verbatim backend value, never an invented one.
    const allowed = new Set([
      "applicable",
      "not_applicable",
      "unknown",
      "satisfied",
      "not_satisfied",
      "supported",
      "insufficient",
      "missing",
      "none",
      "present",
      "determined",
      "uncertain",
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

  it("keeps unknown and contradiction honest", () => {
    renderWithReport(REPORT);
    expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
    expect(screen.getByText("present")).toBeInTheDocument();
    expect(screen.getByText(/shown as recorded, not resolved/i)).toBeInTheDocument();
    // The only "non-compliance" wording present is the explicit
    // anti-collapse qualifier, never a verdict.
    expect(screen.getByText(/not a finding of non-compliance/i)).toBeInTheDocument();
    const text = document.body.textContent?.toLowerCase() ?? "";
    expect(text).not.toMatch(/\bfailed\b/);
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
