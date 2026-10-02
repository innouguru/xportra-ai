import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AnalysisProvider } from "../../app/AnalysisContext";
import { AssessmentProvider } from "../../app/AssessmentContext";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ConversationProvider } from "../conversation/ConversationContext";
import { AssessmentPage } from "./AssessmentPage";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "evidence_pending",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderPage(record: WorkflowRecord | null = RECORD) {
  if (record) {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  }
  render(
    <MemoryRouter initialEntries={["/workspace/assessment"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <ConversationProvider>
            <AnalysisProvider>
              <AssessmentProvider>
                <Routes>
                  <Route path="/workspace/assessment" element={<AssessmentPage />} />
                </Routes>
              </AssessmentProvider>
            </AnalysisProvider>
          </ConversationProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AssessmentPage", () => {
  it("asks for a shipment when no workflow record exists", () => {
    renderPage(null);
    expect(
      screen.getByRole("heading", { name: "No active shipment" }),
    ).toBeInTheDocument();
  });

  it("presents assessment as stages of one journey", () => {
    renderPage();
    const tablist = screen.getByRole("tablist", { name: "Assessment stages" });
    expect(tablist).toBeInTheDocument();
    for (const name of [
      "Run analysis",
      "Review findings",
      "Final review",
      "Package",
      "History",
    ]) {
      expect(screen.getByRole("tab", { name })).toBeInTheDocument();
    }
    // No rounds yet, so the journey starts at the run stage.
    expect(screen.getByRole("tab", { name: "Run analysis" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.getByRole("heading", { name: "Analysis readiness" }),
    ).toBeInTheDocument();
  });

  it("moves between stages without losing backend state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            workflow_id: RECORD.id,
            tenant_id: RECORD.tenant_id,
            case_id: RECORD.case_id,
            shipment_id: null,
            state: RECORD.state,
            entries: [],
            supplied_evidence_ids: [],
            open_requirements: [],
            round_count: 0,
            latest_report_id: null,
            decision_summary_present: false,
            readiness: null,
            final_package: null,
          }),
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Final review" }));
    expect(
      screen.getByRole("heading", { name: "Latest analysis not loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "History" }));
    expect(
      await screen.findByRole("heading", { name: /Workflow history/i }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Run analysis" }));
    expect(
      screen.getByRole("heading", { name: "Analysis readiness" }),
    ).toBeInTheDocument();
  });

  it("opens on the package stage for a finalized workflow", () => {
    renderPage({ ...RECORD, state: "assessment_package_ready" });
    expect(screen.getByRole("tab", { name: "Package" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});
