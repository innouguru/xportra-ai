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
    findings: [finding("satisfied", "r1"), finding("unknown", "r2")],
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

function seed(entries: ShipmentEntry[]) {
  window.sessionStorage.setItem("xportra.shipments.v1", JSON.stringify(entries));
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

function stubBackend(report: AnalysisReport | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
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
    expect(banner.textContent).toContain("This shipment is complete and read-only.");
    expect(banner.textContent).toContain("It’s kept as a compliance record.");
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Assessment finalized.")).toBeInTheDocument();
    expect(screen.getByText(/1 of 2 requirements addressed\./)).toBeInTheDocument();
    expect(screen.getByText("Requirement r1")).toBeInTheDocument();
    expect(screen.getByText("Addressed")).toBeInTheDocument();
    expect(screen.getByText("Still checking")).toBeInTheDocument();
    expect(await screen.findByText(/Phytosanitary certificate scan/)).toBeInTheDocument();
    expect(screen.getByText("Destination plant health regulation")).toBeInTheDocument();
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
    await screen.findByText(/1 of 2 requirements addressed\./);
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
    expect(screen.getByText(/no recorded findings/i)).toBeInTheDocument();
    expect(screen.getByText(/no documents recorded/i)).toBeInTheDocument();
    // Absent facts are omitted, never placeholder-filled.
    expect(screen.queryByText("Unknown")).toBeNull();
  });

  it("retries a failed report read with the profile intact", async () => {
    seed([
      seedEntry("case-done", "assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
      }),
    ]);
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        calls += 1;
        if (calls === 1) {
          throw new Error("network down");
        }
        return new Response(JSON.stringify(storedReport()), { status: 200 });
      }),
    );
    renderReport("/shipments/case-done/report");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Cocoa")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/1 of 2 requirements addressed\./)).toBeInTheDocument();
  });

  it("reports an unknown reference honestly", () => {
    seed([]);
    stubBackend(null);
    renderReport("/shipments/nope/report");
    expect(screen.getByRole("heading", { name: "Report unavailable" })).toBeInTheDocument();
  });

  it("keeps sources readable and secondary", async () => {
    seed([
      seedEntry("case-done", "assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
      }),
    ]);
    stubBackend(storedReport());
    renderReport("/shipments/case-done/report");
    const sources = await screen.findByRole("heading", { name: "Regulatory sources" });
    const section = sources.closest("section");
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getByText("Destination plant health regulation")).toBeInTheDocument();
    expect(within(section as HTMLElement).queryByText(/\{.*kind.*\}/)).toBeNull();
  });
});
