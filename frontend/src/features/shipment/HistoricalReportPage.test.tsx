import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ThemeProvider } from "../../theme/theme";
import type { ShipmentEntry } from "../../lib/shipments";
import type { AnalysisFinding, AnalysisReport, WorkflowRecord } from "../../types/api";
import { HistoricalReportPage } from "./HistoricalReportPage";

/**
 * Phase 10.8G historical report contract.
 *
 * The stored report and evidence details are
 * mocked at the fetch boundary with
 * exact-contract payloads; the registry is
 * seeded for real. Fixtures are test-only.
 */

function workflow(caseId: string, state: string, extra?: Partial<WorkflowRecord>): WorkflowRecord {
  return {
    id: `id-${caseId}`,
    tenant_id: "tenant-1",
    case_id: caseId,
    shipment_id: null,
    state,
    rounds: [],
    supplied_evidence_ids: [],
    open_requirements: [],
    ...extra,
  };
}

function seedEntry(caseId: string, state: string, extra?: Partial<WorkflowRecord>): ShipmentEntry {
  const record = workflow(caseId, state, extra);
  return {
    caseId,
    shipmentId: null,
    profile: {
      product: "Cocoa",
      origin: "Lagos",
      destination: "Rotterdam",
      quantity: "",
      unit: "tonnes",
      shipmentDate: "",
    },
    record,
  };
}

function finding(assessment: string, requirementId: string): AnalysisFinding {
  return {
    analysis_id: `a-${requirementId}`,
    requirement_id: requirementId,
    requirement_text: `Requirement ${requirementId}`,
    applicability: "applicable",
    assessment,
    explanation: "The evidence was reviewed.",
    uncertainty: "determined",
    uncertainty_explanation: "",
    evidence_sufficiency: "sufficient",
    sufficiency_explanation: "",
    contradiction_state: "none",
    missing_information: [],
    supporting_evidence: [{ evidence_id: "ev-1" }],
    conflicting_evidence: [],
    knowledge_references: [],
    sources: [{ title: "Destination plant health regulation", source_id: "DEST-PH-1" }],
    missing_items: [],
  };
}

function storedReport(): AnalysisReport {
  return {
    report_id: "rep-1",
    case_id: "case-done",
    counts: {},
    requirements_with_missing_information: [],
    uncertain_requirement_ids: [],
    requirements_with_conflicting_evidence: [],
    conflicting_evidence_count: 0,
    findings: [
      finding("satisfied", "r1"),
      {
        ...finding("unknown", "r2"),
        uncertainty: "uncertain",
        uncertainty_explanation: "The available source records leave this point unresolved.",
        contradiction_state: "present",
        missing_information: ["A supporting certificate is not recorded."],
        conflicting_evidence: [
          {
            evidence_id: "ev-conflict",
            evidence_type: "certificate",
            reference: "page 4",
            status: "rejected",
          },
        ],
      },
    ],
  };
}

function stubMatchMedia() {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

let currentSeed: ShipmentEntry[] = [];

function seed(entries: ShipmentEntry[]) {
  window.sessionStorage.setItem("xportra.shipments.v1", JSON.stringify(entries));
  currentSeed = entries;
}

function renderReport(path: string) {
  stubMatchMedia();
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={{ token: "test-token" }}>
        <WorkflowProvider>
          <ThemeProvider>
            <Routes>
              <Route path="/shipments/:caseId/report" element={<HistoricalReportPage />} />
              <Route path="/shipments" element={<div>Shipments stub</div>} />
              <Route path="/shipments/:caseId" element={<div>Workspace stub</div>} />
              <Route path="/start" element={<div>Start stub</div>} />
            </Routes>
          </ThemeProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function serverItem(entry: ShipmentEntry) {
  return {
    shipment_id: entry.shipmentId ?? entry.caseId,
    case_id: entry.caseId,
    product: entry.profile.product,
    origin_country: entry.profile.origin,
    destination_country: entry.profile.destination,
    quantity: entry.profile.quantity || null,
    unit: entry.profile.unit || null,
    shipment_date: entry.profile.shipmentDate || null,
    status: "bound",
    created_at: "",
    updated_at: "",
    workflow: entry.record
      ? {
          workflow_id: entry.record.id,
          state: entry.record.state,
          is_closed: entry.record.state === "assessment_package_ready",
          supplied_evidence_count: entry.record.supplied_evidence_ids.length,
          open_requirements_count: entry.record.open_requirements.length,
          round_count: entry.record.rounds.length,
          latest_report_id:
            entry.record.rounds.length > 0
              ? entry.record.rounds[entry.record.rounds.length - 1].report_id
              : null,
        }
      : null,
    workflow_count: entry.record ? 1 : 0,
    workflow_record: entry.record,
  };
}

function stubBackend(report: AnalysisReport | null, entries: ShipmentEntry[] = currentSeed) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/compliance/shipments")) {
        // Durable list serves the seeded entries, as a
        // persisted backend would after real starts.
        return new Response(
          JSON.stringify({
            shipments: entries.map(serverItem),
            limit: 20,
            offset: 0,
            total: entries.length,
          }),
          { status: 200 },
        );
      }
      if (url.includes("/compliance/reports/")) {
        if (!report) {
          return new Response(JSON.stringify({ error: "gone" }), { status: 404 });
        }
        return new Response(JSON.stringify(report), { status: 200 });
      }
      if (url.includes("/compliance-evidence/") && !url.includes("/download")) {
        return new Response(
          JSON.stringify({
            id: "ev-1",
            tenant_id: "tenant-1",
            source_id: null,
            document_title: "Phytosanitary certificate scan",
            document_type: "certificate",
            file_reference_or_uri: "",
            content_hash: null,
            status: "accepted",
            uploaded_at: "",
            created_at: "",
            updated_at: "",
            mime_type: "application/pdf",
          }),
          { status: 200 },
        );
      }
      throw new Error(`unexpected ${url}`);
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.sessionStorage.clear();
  currentSeed = [];
  delete document.documentElement.dataset.theme;
});

describe("historical report", () => {
  it("presents the completed shipment as a quiet read-only record", async () => {
    seed([
      seedEntry("case-done", "assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
        supplied_evidence_ids: ["ev-1"],
      }),
    ]);
    stubBackend(storedReport());
    renderReport("/shipments/case-done/report");
    expect(
      await screen.findByRole("heading", { name: "Cocoa · Lagos → Rotterdam", level: 1 }),
    ).toBeInTheDocument();
    const banner = screen.getByRole("note");
    expect(banner.textContent).toContain("assessment package is complete and read-only.");
    expect(banner.textContent).toContain("does not mean a government authority has approved or cleared");
    expect(screen.getByText("Completed shipment")).toBeInTheDocument();
    expect(screen.getByText("Assessment finalized.")).toBeInTheDocument();
    expect(screen.getByText(/1 of 2 findings addressed in the recorded analysis/)).toBeInTheDocument();
    expect(screen.getByText("Requirement r1")).toBeInTheDocument();
    expect(screen.getAllByText("Addressed in this analysis").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Still checking").length).toBeGreaterThan(0);
    expect(screen.getByText("A supporting certificate is not recorded.")).toBeInTheDocument();
    expect(screen.getByText("Conflicting evidence — shown as recorded, not resolved")).toBeInTheDocument();
    expect(screen.getByText("The available source records leave this point unresolved.")).toBeInTheDocument();
    expect(await screen.findByText(/Phytosanitary certificate scan/)).toBeInTheDocument();
    expect(screen.getAllByText("Destination plant health regulation").length).toBeGreaterThan(0);
    expect(screen.queryByText("ev-conflict")).toBeNull();
    expect(screen.queryByText("DEST-PH-1")).toBeNull();
    expect(screen.getByText(/1 analysis round recorded/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New shipment" })).toHaveAttribute("href", "/start");
  });

  it("exposes no mutation controls and no PDF control", async () => {
    seed([
      seedEntry("case-done", "assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
      }),
    ]);
    stubBackend(storedReport());
    renderReport("/shipments/case-done/report");
    await screen.findByRole("heading", { name: "Cocoa · Lagos → Rotterdam", level: 1 });
    const controls = [
      ...screen.queryAllByRole("button"),
      ...screen.queryAllByRole("link"),
    ].map((control) => control.textContent ?? "");
    for (const name of controls) {
      expect(name).not.toMatch(/upload|verify|edit|reopen|finalize|delete|download pdf|run compliance/i);
    }
    expect(screen.queryByRole("button", { name: /download pdf/i })).toBeNull();
  });

  it("shows no identifiers, scores, or technical terminology", async () => {
    seed([
      seedEntry("case-done", "assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
        supplied_evidence_ids: ["ev-1"],
      }),
    ]);
    stubBackend(storedReport());
    renderReport("/shipments/case-done/report");
    await screen.findByText(/1 of 2 findings addressed in the recorded analysis/);
    const main = screen.getByRole("main");
    expect(main.textContent).not.toContain("ev-1");
    expect(main.textContent).not.toContain("rep-1");
    expect(main.textContent).not.toContain("case-done");
    expect(main.textContent).not.toMatch(/assessment_package_ready|DecisionTrace|trace_ids|%|score/i);
  });

  it("redirects active shipments without mutating anything", () => {
    seed([seedEntry("case-open", "evidence_pending")]);
    stubBackend(null);
    renderReport("/shipments/case-open/report");
    expect(screen.getByRole("heading", { name: "This shipment is still active." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open shipment workspace" })).toHaveAttribute(
      "href",
      "/shipments/case-open",
    );
    // The only controls are shell/back navigation — nothing that mutates.
    const names = screen.getAllByRole("button").map((button) => button.textContent ?? "");
    for (const name of names) {
      expect(name).not.toMatch(/upload|verify|edit|reopen|finalize|delete|continue|run/i);
    }
  });

  it("stays honest when nothing was recorded", async () => {
    seed([seedEntry("case-done", "assessment_package_ready")]);
    stubBackend(null);
    renderReport("/shipments/case-done/report");
    expect(
      await screen.findByRole("heading", { name: "Cocoa · Lagos → Rotterdam", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText(/no stored analysis report is available/i)).toBeInTheDocument();
    expect(screen.queryByText(/no findings were recorded in this report/i)).toBeNull();
    expect(screen.getByText(/no documents recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/does not establish compliance or government clearance/i)).toBeInTheDocument();
    // Absent facts are omitted, never placeholder-filled.
    expect(screen.queryByText("Unknown")).toBeNull();
  });

  it("states that an empty stored report does not establish compliance", async () => {
    const emptyReport = { ...storedReport(), findings: [] };
    seed([
      seedEntry("case-done", "assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
      }),
    ]);
    stubBackend(emptyReport);
    renderReport("/shipments/case-done/report");
    expect((await screen.findAllByText(/no findings were recorded in this report/i)).length).toBeGreaterThan(0);
    expect(screen.getByText(/does not establish compliance or confirm that the shipment is cleared/i)).toBeInTheDocument();
  });

  it("retries a failed report read with the profile intact", async () => {
    seed([
      seedEntry("case-done", "assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
      }),
    ]);
    let reportCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/compliance/shipments")) {
          return new Response(
            JSON.stringify({
              shipments: currentSeed.map(serverItem),
              limit: 20,
              offset: 0,
              total: currentSeed.length,
            }),
            { status: 200 },
          );
        }
        reportCalls += 1;
        if (reportCalls === 1) {
          throw new Error("network down");
        }
        return new Response(JSON.stringify(storedReport()), { status: 200 });
      }),
    );
    renderReport("/shipments/case-done/report");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Cocoa")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/1 of 2 findings addressed in the recorded analysis/)).toBeInTheDocument();
  });

  it("resolves a completed shipment from the server with an empty registry", async () => {
    window.sessionStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/compliance/shipments")) {
          return new Response(
            JSON.stringify({
              shipments: [
                {
                  shipment_id: "ship-done",
                  case_id: "case-done",
                  product: "Cocoa",
                  origin_country: "Lagos",
                  destination_country: "Rotterdam",
                  quantity: "",
                  unit: "tonnes",
                  shipment_date: "",
                  status: "bound",
                  created_at: "",
                  updated_at: "",
                  workflow: {
                    workflow_id: "id-case-done",
                    state: "assessment_package_ready",
                    is_closed: true,
                    supplied_evidence_count: 1,
                    open_requirements_count: 0,
                    round_count: 1,
                    latest_report_id: "rep-1",
                  },
                  workflow_count: 1,
                  workflow_record: {
                    id: "id-case-done",
                    tenant_id: "tenant-1",
                    case_id: "case-done",
                    shipment_id: "ship-done",
                    state: "assessment_package_ready",
                    rounds: [
                      {
                        round_index: 0,
                        report_id: "rep-1",
                        analysis_ids: [],
                        trace_ids: [],
                        input_fingerprints: [],
                      },
                    ],
                    supplied_evidence_ids: ["ev-1"],
                    open_requirements: [],
                  },
                },
              ],
              limit: 20,
              offset: 0,
              total: 1,
            }),
            { status: 200 },
          );
        }
        if (url.includes("/compliance/reports/")) {
          return new Response(JSON.stringify(storedReport()), { status: 200 });
        }
        if (url.includes("/compliance-evidence/") && !url.includes("/download")) {
          return new Response(
            JSON.stringify({
              id: "ev-1",
              tenant_id: "tenant-1",
              source_id: null,
              document_title: "Phytosanitary certificate scan",
              document_type: "certificate",
              file_reference_or_uri: "",
              content_hash: null,
              status: "accepted",
              uploaded_at: "",
              created_at: "",
              updated_at: "",
              mime_type: "application/pdf",
            }),
            { status: 200 },
          );
        }
        throw new Error(`unexpected ${url}`);
      }),
    );
    renderReport("/shipments/case-done/report");
    expect(
      await screen.findByRole("heading", { name: "Cocoa · Lagos → Rotterdam", level: 1 }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/1 of 2 findings addressed in the recorded analysis/)).toBeInTheDocument();
  });

  it("reports an unknown reference honestly", () => {
    seed([]);
    stubBackend(null);
    renderReport("/shipments/nope/report");
    expect(screen.getByRole("heading", { name: "Report unavailable" })).toBeInTheDocument();
  });

  it("keeps source details attached to each historical finding without technical identifiers", async () => {
    seed([
      seedEntry("case-done", "assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
      }),
    ]);
    stubBackend(storedReport());
    renderReport("/shipments/case-done/report");
    await screen.findAllByText("Destination plant health regulation");
    const findingCard = screen.getByRole("article", { name: "Finding: Requirement r1" });
    expect(within(findingCard).getByText("Sources and provenance")).toBeInTheDocument();
    expect(within(findingCard).getByText("Destination plant health regulation")).toBeInTheDocument();
    expect(within(findingCard).queryByText("DEST-PH-1")).toBeNull();
    expect(within(findingCard).queryByText(/\{.*kind.*\}/)).toBeNull();
  });
});
