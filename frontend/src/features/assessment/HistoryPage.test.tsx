import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { HistoryPage } from "./HistoryPage";
import type { HistoryResponse, WorkflowRecord } from "../../types/api";

const WORKFLOW_ID = "11111111-1111-1111-1111-111111111111";
const EVIDENCE_ID = "77777777-7777-7777-7777-777777777777";
const REPORT_ID = "99999999-9999-9999-9999-999999999999";

const RECORD: WorkflowRecord = {
  id: WORKFLOW_ID,
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: "55555555-5555-5555-5555-555555555555",
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

const HISTORY: HistoryResponse = {
  workflow_id: WORKFLOW_ID,
  tenant_id: RECORD.tenant_id,
  case_id: RECORD.case_id,
  shipment_id: RECORD.shipment_id,
  state: "analysis_available",
  entries: [
    {
      sequence: 0,
      kind: "workflow_created",
      detail: "workflow began",
      references: [
        { label: "workflow_id", value: WORKFLOW_ID },
        { label: "tenant_id", value: RECORD.tenant_id },
        { label: "case_id", value: RECORD.case_id },
      ],
    },
    {
      sequence: 1,
      kind: "shipment_bound",
      detail: "shipment reference bound",
      references: [{ label: "shipment_id", value: RECORD.shipment_id as string }],
    },
    {
      sequence: 2,
      kind: "evidence_supplied",
      detail: "evidence reference supplied",
      references: [
        { label: "evidence_id", value: EVIDENCE_ID },
        { label: "supply_position", value: "0" },
      ],
    },
    {
      sequence: 3,
      kind: "analysis_completed",
      detail: "analysis round completed",
      references: [
        { label: "round_index", value: "1" },
        { label: "report_id", value: REPORT_ID },
        { label: "analysis_id", value: "a-1" },
        { label: "trace_id", value: "t-1" },
      ],
    },
  ],
  supplied_evidence_ids: [EVIDENCE_ID],
  open_requirements: [],
  round_count: 1,
  latest_report_id: REPORT_ID,
  decision_summary_present: false,
  readiness: null,
  final_package: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderPage(history: HistoryResponse = HISTORY) {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(RECORD));
  void history;
  render(
    <MemoryRouter initialEntries={["/workspace/history"]}>
      <AuthProvider initial={{ devTenantId: RECORD.tenant_id }}>
        <WorkflowProvider>
          <Routes>
            <Route path="/workspace" element={<Outlet />}>
              <Route path="history" element={<HistoryPage />} />
              <Route path="report/:reportId" element={<div>Report screen</div>} />
              <Route path="package" element={<div>Package screen</div>} />
            </Route>
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

type FetchCall = [string, RequestInit];

describe("HistoryPage", () => {
  it("fetches the projection and preserves entries with their references", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(HISTORY), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    renderPage();
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/history");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ workflow: RECORD });
    expect(await screen.findAllByTitle(WORKFLOW_ID)).not.toHaveLength(0);
    expect(screen.getAllByText(/Workflow created/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Shipment bound/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Evidence supplied/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Analysis completed/).length).toBeGreaterThan(0);
    expect(screen.getByText("workflow began")).toBeInTheDocument();
    expect(screen.getByText("analysis round completed")).toBeInTheDocument();
    // References are preserved exactly, including every identifier.
    const expectedReferences = [EVIDENCE_ID, REPORT_ID, WORKFLOW_ID];
    for (const expected of expectedReferences) {
      expect(screen.getAllByTitle(expected).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("supply position")).toBeInTheDocument();
    // The latest report links to the stored report route.
    const reportLink = screen.getByRole("link", { name: new RegExp(REPORT_ID.slice(0, 8)) });
    expect(reportLink.getAttribute("href")).toBe(`/workspace/report/${REPORT_ID}`);
  });

  it("invents no timestamps and keeps entries in recorded order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(HISTORY), { status: 200 })),
    );
    renderPage();
    await screen.findAllByTitle(WORKFLOW_ID);
    const kinds = Array.from(document.querySelectorAll(".history-entry .eyebrow")).map(
      (node) => node.textContent,
    );
    expect(kinds).toEqual([
      "1 · Workflow created",
      "2 · Shipment bound",
      "3 · Evidence supplied",
      "4 · Analysis completed",
    ]);
    expect(document.querySelectorAll("time")).toHaveLength(0);
    expect(screen.getByText(/stores no timestamps/i)).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:/);
    expect(text).not.toMatch(/seconds|minutes|hours|days|weeks|months|years/i);
    expect(text).not.toContain("ago");
  });

  it("says plainly when the projection reports nothing more", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(HISTORY), { status: 200 })),
    );
    renderPage();
    await screen.findAllByTitle(WORKFLOW_ID);
    expect(screen.getAllByText(/not reported in this projection/i).length).toBeGreaterThan(0);
  });

  it("renders readiness and the final package when the backend provides them", async () => {
    const enriched: HistoryResponse = {
      ...HISTORY,
      decision_summary_present: true,
      readiness: {
        readiness_state: "partially_ready",
        required_information: 2,
        known_information: 1,
        missing_information_count: 1,
        gaps: [],
      },
      final_package: {
        workflow_id: WORKFLOW_ID,
        report_id: REPORT_ID,
        round_count: 1,
        decision_summary_present: true,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(enriched), { status: 200 })),
    );
    renderPage();
    await screen.findAllByTitle(WORKFLOW_ID);
    expect(screen.getByText("Readiness in this projection")).toBeInTheDocument();
    expect(screen.getByText("partially_ready")).toBeInTheDocument();
    expect(screen.getByText("Reported as carried on the latest result.")).toBeInTheDocument();
    expect(screen.getByText(/Referenced as ready/i)).toBeInTheDocument();
  });

  it("keeps history readable when the backend refuses the read", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                code: "tenant_mismatch",
                message: "This shipment belongs to a different workspace.",
              },
            }),
            { status: 403 },
          ),
      ),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This shipment belongs to a different workspace.",
    );
  });
});
