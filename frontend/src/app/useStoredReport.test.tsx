import { afterEach, describe, expect, it, vi } from "vitest";
import { useEffect } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AnalysisProvider, useAnalysis } from "./AnalysisContext";
import { AuthProvider } from "./AuthContext";
import { WorkflowProvider } from "./WorkflowContext";
import { useStoredReport } from "./useStoredReport";
import type { AnalysisReport, WorkflowRecord } from "../types/api";

/**
 * Persisted-report rehydration contract.
 *
 * The hook prefers the in-memory report, falls back to
 * exactly one stored-report fetch keyed by the latest
 * recorded round, distinguishes loading/empty/error,
 * and adopts the fetched report into the context.
 */

const REPORT_ID = "99999999-9999-9999-9999-999999999999";

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
      analysis_ids: [],
      trace_ids: [],
      input_fingerprints: [],
    },
  ],
  supplied_evidence_ids: [],
  open_requirements: [],
};

const REPORT: AnalysisReport = {
  report_id: REPORT_ID,
  case_id: RECORD.case_id,
  counts: {},
  requirements_with_missing_information: [],
  uncertain_requirement_ids: [],
  requirements_with_conflicting_evidence: [],
  conflicting_evidence_count: 0,
  findings: [],
};

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

const NO_CASES: Array<Record<string, unknown>> = [];

function stubJson(body: unknown, status = 200) {
  const spy = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

function Probe() {
  const { report, status, error } = useStoredReport();
  const { report: contextReport } = useAnalysis();
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="report">{report ? report.report_id : "none"}</p>
      <p data-testid="context">{contextReport ? contextReport.report_id : "none"}</p>
      <p data-testid="error">{error ? "error-present" : "error-absent"}</p>
    </div>
  );
}

function renderProbe(rounds: boolean) {
  const record = rounds ? RECORD : { ...RECORD, rounds: [] };
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  render(
    <MemoryRouter>
      <AuthProvider>
        <WorkflowProvider>
          <AnalysisProvider>
            <Probe />
          </AnalysisProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("useStoredReport", () => {
  it("uses the in-memory report without fetching (Test A)", async () => {
    const spy = stubJson(REPORT);
    // Mount the probe only after the context already
    // holds the report — as when arriving from the
    // analysis screen — so no fetch may fire at all.
    sessionStorage.setItem(
      "xportra.workflow-record.v1",
      JSON.stringify(RECORD),
    );
    function Shell({ showProbe }: { showProbe: boolean }) {
      const { setAnalysis, report } = useAnalysis();
      useEffect(() => {
        setAnalysis(REPORT, NO_CASES);
      }, [setAnalysis]);
      return (
        <>
          <p data-testid="seeded">{report ? report.report_id : "none"}</p>
          {showProbe ? <Probe /> : null}
        </>
      );
    }
    function Tree({ showProbe }: { showProbe: boolean }) {
      return (
        <MemoryRouter>
          <AuthProvider>
            <WorkflowProvider>
              <AnalysisProvider>
                <Shell showProbe={showProbe} />
              </AnalysisProvider>
            </WorkflowProvider>
          </AuthProvider>
        </MemoryRouter>
      );
    }
    const view = render(<Tree showProbe={false} />);
    await waitFor(() => {
      expect(screen.getByTestId("seeded")).toHaveTextContent(REPORT_ID);
    });
    view.rerender(<Tree showProbe={true} />);
    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("ready");
    });
    expect(screen.getByTestId("report")).toHaveTextContent(REPORT_ID);
    expect(spy).not.toHaveBeenCalled();
  });

  it("fetches the persisted report once and adopts it (Test B)", async () => {
    const spy = stubJson(REPORT);
    renderProbe(true);
    expect(screen.getByTestId("status")).toHaveTextContent("loading");
    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("ready");
    });
    expect(screen.getByTestId("report")).toHaveTextContent(REPORT_ID);
    expect(screen.getByTestId("context")).toHaveTextContent(REPORT_ID);
    const urls = spy.mock.calls.map((call) => {
      const [url] = call as unknown as [string, RequestInit];
      return url;
    });
    expect(urls).toEqual([
      `http://localhost:8000/compliance/reports/${REPORT_ID}`,
    ]);
  });

  it("reports empty when no report exists anywhere (Test C)", () => {
    const spy = stubJson(REPORT);
    renderProbe(false);
    expect(screen.getByTestId("status")).toHaveTextContent("empty");
    expect(screen.getByTestId("report")).toHaveTextContent("none");
    expect(spy).not.toHaveBeenCalled();
  });

  it("reports error without claiming absence on fetch failure (Test D)", async () => {
    const spy = stubJson({ error: { code: "unexpected_error", message: "boom" } }, 500);
    renderProbe(true);
    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("error");
    });
    expect(screen.getByTestId("report")).toHaveTextContent("none");
    expect(screen.getByTestId("error")).toHaveTextContent("error-present");
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
