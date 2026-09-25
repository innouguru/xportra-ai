import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { AnalysisProvider } from "../../app/AnalysisContext";
import { AnalysisPage } from "./AnalysisPage";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "applicability_determined",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

const REPORT = {
  report_id: "99999999-9999-9999-9999-999999999999",
  case_id: RECORD.case_id,
  counts: {},
  requirements_with_missing_information: [],
  uncertain_requirement_ids: [],
  requirements_with_conflicting_evidence: [],
  conflicting_evidence_count: 0,
  findings: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderWithRecord(record: WorkflowRecord = RECORD) {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  render(
    <MemoryRouter initialEntries={["/workspace/analysis"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <AnalysisProvider>
            <Routes>
              <Route path="/workspace" element={<Outlet />}>
                <Route path="analysis" element={<AnalysisPage />} />
                <Route path="review" element={<div>Review screen</div>} />
              </Route>
            </Routes>
          </AnalysisProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AnalysisPage", () => {
  it("labels first runs and re-runs from round history", () => {
    renderWithRecord();
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeInTheDocument();
  });

  it("shows re-run wording once rounds exist", () => {
    renderWithRecord({ ...RECORD, rounds: [{
      round_index: 1,
      report_id: "r1",
      analysis_ids: [],
      trace_ids: [],
      input_fingerprints: [],
    }] });
    expect(screen.getByRole("button", { name: "Re-run analysis" })).toBeInTheDocument();
  });

  it("runs analysis, stores the report, and navigates to review", async () => {
    const spy = vi.fn(async () =>
      new Response(
        JSON.stringify({
          workflow: { ...RECORD, state: "analysis_available", rounds: [] },
          report: REPORT,
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", spy);
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Requirement ID"), "req-1");
    await user.type(screen.getByLabelText("Requirement text"), "File form X.");
    await user.click(screen.getByRole("button", { name: "Run analysis" }));
    await waitFor(() => expect(screen.getByText("Review screen")).toBeInTheDocument());
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["cases"]).toHaveLength(1);
  });

  it("prevents duplicate submission while a run is in flight", async () => {
    let resolveFetch!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    const spy = vi.fn(async () => pending);
    vi.stubGlobal("fetch", spy);
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Requirement ID"), "req-1");
    await user.type(screen.getByLabelText("Requirement text"), "File form X.");
    await user.click(screen.getByRole("button", { name: "Run analysis" }));
    expect(screen.queryByRole("button", { name: "Run analysis" })).toBeNull();
    resolveFetch(
      new Response(JSON.stringify({ workflow: RECORD, report: REPORT }), { status: 200 }),
    );
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
  });

  it("preserves usable state and surfaces backend failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ error: { code: "invalid_transition", message: "Wrong step." } }),
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Requirement ID"), "req-1");
    await user.type(screen.getByLabelText("Requirement text"), "File form X.");
    await user.click(screen.getByRole("button", { name: "Run analysis" }));
    expect(await screen.findByText(/not available in the shipment's current step/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeEnabled();
  });

  it("shows recorded rounds in order without inventing timestamps", () => {
    renderWithRecord({
      ...RECORD,
      state: "analysis_available",
      rounds: [
        {
          round_index: 1,
          report_id: "11111111-2222-3333-4444-555555555555",
          analysis_ids: ["a-1"],
          trace_ids: ["t-1"],
          input_fingerprints: [],
        },
        {
          round_index: 2,
          report_id: "66666666-7777-8888-9999-000000000000",
          analysis_ids: ["a-2"],
          trace_ids: ["t-2"],
          input_fingerprints: [],
        },
      ],
    });
    expect(screen.getByText("Recorded analysis rounds")).toBeInTheDocument();
    expect(screen.getByText(/Reviewing round 2/)).toBeInTheDocument();
    const reportLinks = screen
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"))
      .filter((href) => href?.includes("/report/"));
    expect(reportLinks).toEqual([
      "/workspace/report/11111111-2222-3333-4444-555555555555",
      "/workspace/report/66666666-7777-8888-9999-000000000000",
    ]);
    expect(document.body.textContent).not.toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:/);
    expect(document.querySelectorAll("time")).toHaveLength(0);
  });

  it("never runs analysis without an explicit user action", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const user = userEvent.setup();
    renderWithRecord({
      ...RECORD,
      state: "reanalysis_required",
      rounds: [
        {
          round_index: 1,
          report_id: "11111111-2222-3333-4444-555555555555",
          analysis_ids: [],
          trace_ids: [],
          input_fingerprints: [],
        },
      ],
    });
    // Supplying evidence (which produced this state) starts nothing.
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText(/never automatic/i)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Requirement ID"), "req-1");
    await user.type(screen.getByLabelText("Requirement text"), "File form X.");
    await user.click(screen.getByRole("button", { name: "Re-run analysis" }));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const [url] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/compliance/workflows/analyze");
  });

  it("restores the new round from the response for later review", async () => {
    const secondRound = {
      round_index: 2,
      report_id: "66666666-7777-8888-9999-000000000000",
      analysis_ids: [],
      trace_ids: [],
      input_fingerprints: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            workflow: {
              ...RECORD,
              state: "analysis_available",
              rounds: [secondRound],
            },
            report: { ...REPORT, report_id: secondRound.report_id },
          }),
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithRecord({
      ...RECORD,
      state: "reanalysis_required",
      rounds: [
        {
          round_index: 1,
          report_id: "11111111-2222-3333-4444-555555555555",
          analysis_ids: [],
          trace_ids: [],
          input_fingerprints: [],
        },
      ],
    });
    await user.type(screen.getByLabelText("Requirement ID"), "req-1");
    await user.type(screen.getByLabelText("Requirement text"), "File form X.");
    await user.click(screen.getByRole("button", { name: "Re-run analysis" }));
    await waitFor(() => {
      const stored = JSON.parse(
        sessionStorage.getItem("xportra.workflow-record.v1") ?? "{}",
      ) as { rounds?: unknown[] };
      expect(stored.rounds).toHaveLength(1);
      expect((stored.rounds?.[0] as { round_index?: number }).round_index).toBe(2);
    });
  });

  it("closes analysis controls when the workflow is terminal", () => {
    renderWithRecord({
      ...RECORD,
      state: "assessment_package_ready",
      rounds: [
        {
          round_index: 1,
          report_id: "11111111-2222-3333-4444-555555555555",
          analysis_ids: [],
          trace_ids: [],
          input_fingerprints: [],
        },
      ],
    });
    expect(screen.queryByRole("button", { name: "Re-run analysis" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Run analysis" })).toBeNull();
    expect(
      screen.getByText(/analysis cannot be rerun/i),
    ).toBeInTheDocument();
  });
});
