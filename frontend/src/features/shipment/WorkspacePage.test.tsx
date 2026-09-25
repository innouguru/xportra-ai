import { describe, expect, it, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { WorkspacePage } from "./WorkspacePage";
import { Stepper } from "../../components/Stepper";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: "44444444-4444-4444-4444-444444444444",
  state: "evidence_pending",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

afterEach(() => {
  sessionStorage.clear();
});

function renderWorkspace(record: WorkflowRecord | null) {
  if (record) {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  }
  render(
    <MemoryRouter initialEntries={["/workspace"]}>
      <AuthProvider>
        <WorkflowProvider>
          <Routes>
            <Route path="/workspace" element={<WorkspacePage />}>
              <Route index element={<div>Section</div>} />
            </Route>
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("WorkspacePage", () => {
  it("shows the empty state without an active shipment", () => {
    renderWorkspace(null);
    expect(screen.getByRole("heading", { name: "No active shipment" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Start a new shipment" }),
    ).toBeInTheDocument();
  });

  it("shows shipment reference, process state, and section nav", () => {
    renderWorkspace(RECORD);
    expect(screen.getByText("Evidence pending")).toBeInTheDocument();
    expect(
      screen.getByText("process position, not a compliance verdict", { exact: false }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Workspace sections" }),
    ).toBeInTheDocument();
  });

  it("anchors the workspace on the shipment hero", () => {
    renderWorkspace(RECORD);
    expect(screen.getByLabelText("Active shipment")).toBeInTheDocument();
    expect(screen.getByText("Active shipment")).toBeInTheDocument();
  });

  it("groups section navigation into workspace and assessment areas", () => {
    renderWorkspace(RECORD);
    const nav = screen.getByRole("navigation", { name: "Workspace sections" });
    expect(nav).toHaveTextContent("Workspace");
    expect(nav).toHaveTextContent("Assessment");
    // Journey order is preserved within each group.
    expect(
      screen.getByRole("link", { name: "Shipment information" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Final review" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Assessment package" }),
    ).toBeInTheDocument();
    // No rounds recorded yet, so no report link is offered.
    expect(screen.queryByRole("link", { name: "Latest report" })).toBeNull();
  });

  it("links the latest stored report once a round is recorded", () => {
    const reportId = "99999999-9999-9999-9999-999999999999";
    renderWorkspace({
      ...RECORD,
      rounds: [
        {
          round_index: 1,
          report_id: reportId,
          analysis_ids: [],
          trace_ids: [],
          input_fingerprints: [],
        },
      ],
    });
    const link = screen.getByRole("link", { name: "Latest report" });
    expect(link.getAttribute("href")).toContain(encodeURIComponent(reportId));
  });
});

describe("Stepper", () => {
  it("marks the current step with aria-current and no compliance claims", () => {
    render(<Stepper state="evidence_pending" />);
    const list = screen.getByRole("list", { name: "Compliance journey progress" });
    expect(list).toBeInTheDocument();
    const current = screen.getByText("Evidence");
    expect(current.closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.queryByText(/compliant/i)).not.toBeInTheDocument();
  });

  it("numbers each journey step in order", () => {
    const { container } = render(<Stepper state="created" />);
    const numbers = Array.from(container.querySelectorAll(".step-number"));
    // Six spine steps, each carrying a generated ordinal (01–06 via CSS).
    expect(numbers).toHaveLength(6);
    const items = Array.from(container.querySelectorAll("li.step"));
    expect(items).toHaveLength(6);
  });

  it("marks the terminal assessment step as closed, not scored", () => {
    render(<Stepper state="assessment_package_ready" />);
    const assessment = screen.getByText("Assessment");
    const item = assessment.closest("li");
    expect(item?.className).toMatch(/step--terminal/);
    expect(screen.getByText(/closed/i)).toBeInTheDocument();
    expect(screen.queryByText(/compliant|score|percent|verdict/i)).not.toBeInTheDocument();
  });

  it("describes each stage as process position without compliance claims", () => {
    render(<Stepper state="analysis_available" />);
    expect(screen.getByText("References supplied")).toBeInTheDocument();
    expect(screen.getByText("Rounds recorded")).toBeInTheDocument();
    expect(screen.getByText("Findings reviewed")).toBeInTheDocument();
    expect(screen.queryByText(/compliant|score|percent|verdict/i)).not.toBeInTheDocument();
  });
});
