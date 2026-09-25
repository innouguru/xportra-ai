import { describe, expect, it, afterEach } from "vitest";
import { useEffect } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AnalysisProvider, useAnalysis } from "../../app/AnalysisContext";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { WorkspaceOverview } from "./WorkspaceOverview";
import type { AnalysisReport, WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: "44444444-4444-4444-4444-444444444444",
  state: "additional_evidence_requested",
  rounds: [
    {
      round_index: 1,
      report_id: "99999999-9999-9999-9999-999999999999",
      analysis_ids: ["a1"],
      trace_ids: ["t1"],
      input_fingerprints: [],
    },
  ],
  supplied_evidence_ids: ["77777777-7777-7777-7777-777777777777"],
  open_requirements: ["55555555-5555-5555-5555-555555555555"],
};

const NO_CASES: Array<Record<string, unknown>> = [];

function renderOverview(record: WorkflowRecord | null, report: AnalysisReport | null = null) {
  if (record) {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  }
  function Seed() {
    const { setAnalysis } = useAnalysis();
    useEffect(() => {
      if (report) {
        setAnalysis(report, NO_CASES);
      }
    }, [setAnalysis]);
    return <WorkspaceOverview />;
  }
  render(
    <MemoryRouter initialEntries={["/workspace"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <AnalysisProvider>
            <Routes>
              <Route path="/workspace" element={<Seed />}>
                <Route path="info" element={<div>Info screen</div>} />
                <Route path="analysis" element={<div>Analysis screen</div>} />
                <Route path="review" element={<div>Review screen</div>} />
                <Route path="package" element={<div>Package screen</div>} />
                <Route
                  path="additional-evidence"
                  element={<div>Additional evidence screen</div>}
                />
              </Route>
            </Routes>
          </AnalysisProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  sessionStorage.clear();
});

describe("WorkspaceOverview", () => {
  it("leads with shipment identity, not technical identifiers", () => {
    renderOverview(RECORD);
    expect(screen.getByText("Export shipment")).toBeInTheDocument();
    // Human-facing short reference dominates; the full UUID stays secondary.
    expect(screen.getAllByText("44444444…").length).toBeGreaterThan(0);
    expect(screen.getByText("Assessment in progress")).toBeInTheDocument();
    expect(screen.getByText("additional_evidence_requested")).toBeInTheDocument();
  });

  it("presents five assessment areas with honest recorded detail", () => {
    renderOverview(RECORD);
    const strip = screen.getByRole("list", { name: "Assessment areas" });
    expect(strip).toHaveTextContent("Shipment");
    expect(strip).toHaveTextContent("Requirements");
    expect(strip).toHaveTextContent("Evidence");
    expect(strip).toHaveTextContent("Analysis");
    expect(strip).toHaveTextContent("Assessment");
    expect(screen.getByText("1 supplied")).toBeInTheDocument();
    expect(screen.getByText("1 round recorded")).toBeInTheDocument();
    expect(screen.getByText("1 flagged open")).toBeInTheDocument();
  });

  it("surfaces what needs attention with links to existing routes", () => {
    renderOverview(RECORD);
    expect(screen.getByText("Additional evidence requested")).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: "Review now" });
    expect(links.length).toBeGreaterThan(0);
    // Supplying evidence is framed as recording information, never compliance.
    expect(screen.getByText(/does not establish compliance/i)).toBeInTheDocument();
  });

  it("flags re-analysis and review states without inventing verdicts", () => {
    renderOverview({ ...RECORD, state: "reanalysis_required", open_requirements: [] });
    expect(screen.getByText("Re-analysis required")).toBeInTheDocument();
    expect(screen.getByText(/never happens automatically/i)).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/score|verdict|passed|failed/i);
  });

  it("keeps technical identifiers in a secondary disclosure", () => {
    renderOverview(RECORD);
    expect(screen.getByText("Technical details")).toBeInTheDocument();
    expect(screen.getAllByTitle(RECORD.id).length).toBeGreaterThan(0);
  });

  it("presents the terminal workflow as read-only without mutating controls", () => {
    renderOverview({ ...RECORD, state: "assessment_package_ready" });
    expect(screen.getByText("Assessment finalized")).toBeInTheDocument();
    expect(screen.getByText("Finalized — read-only")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open package" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Review now" })).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("asks for a shipment when no workflow record exists", () => {
    renderOverview(null);
    expect(
      screen.getByRole("heading", { name: "No active shipment" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Start a new shipment" }),
    ).toBeInTheDocument();
  });
});
