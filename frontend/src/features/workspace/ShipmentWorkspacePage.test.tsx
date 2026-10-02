import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { useEffect } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AnalysisProvider, useAnalysis } from "../../app/AnalysisContext";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ThemeProvider } from "../../theme/theme";
import type { ShipmentEntry } from "../../lib/shipments";
import type { AnalysisFinding, AnalysisReport, WorkflowRecord } from "../../types/api";
import { ShipmentWorkspacePage } from "./ShipmentWorkspacePage";

/**
 * Shipment workspace contract (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * One vertical workspace: identity, current
 * state, briefing, attention, requirement
 * ledger. Registry entries are seeded through
 * the real sessionStorage boundary; reports
 * through the real in-memory analysis context.
 * Fixtures are test-only display data.
 */

function workflow(state: string, extra?: Partial<WorkflowRecord>): WorkflowRecord {
  return {
    id: "id-1",
    tenant_id: "tenant-1",
    case_id: "case-1",
    shipment_id: null,
    state,
    rounds: [],
    supplied_evidence_ids: [],
    open_requirements: [],
    ...extra,
  };
}

function seedEntry(state: string, extra?: Partial<WorkflowRecord>): ShipmentEntry {
  const record = workflow(state, extra);
  return {
    caseId: "case-1",
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

function seed(entries: ShipmentEntry[]) {
  window.sessionStorage.setItem("xportra.shipments.v1", JSON.stringify(entries));
}

function finding(assessment: string): AnalysisFinding {
  return {
    analysis_id: "a1",
    requirement_id: "r1",
    requirement_text: "Phytosanitary certificate",
    applicability: "applicable",
    assessment,
    explanation: "Required by the destination authority.",
    uncertainty: "determined",
    uncertainty_explanation: "",
    evidence_sufficiency: "insufficient",
    sufficiency_explanation: "",
    contradiction_state: "none",
    missing_information: ["Upload the certificate."],
    supporting_evidence: [],
    conflicting_evidence: [],
    knowledge_references: [],
    sources: [],
    missing_items: [],
  };
}

function analysisReport(caseId: string, assessments: string[]): AnalysisReport {
  const titles = ["Phytosanitary certificate", "Certificate of origin"];
  const missing = ["Upload the certificate.", "Provide the origin declaration."];
  return {
    report_id: "rep-1",
    case_id: caseId,
    counts: {},
    requirements_with_missing_information: [],
    uncertain_requirement_ids: [],
    requirements_with_conflicting_evidence: [],
    conflicting_evidence_count: 0,
    findings: assessments.map((assessment, index) => ({
      ...finding(assessment),
      analysis_id: `a${index + 1}`,
      requirement_id: `r${index + 1}`,
      requirement_text: titles[index] ?? `Requirement ${index + 1}`,
      missing_information: [missing[index] ?? "Provide the document."],
    })),
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

function renderWorkspace(path: string, report: AnalysisReport | null = null) {
  stubMatchMedia();
  function SeedAnalysis({ children }: { children: React.ReactNode }) {
    const { setAnalysis } = useAnalysis();
    useEffect(() => {
      if (report) {
        setAnalysis(report, []);
      }
    }, []);
    return <>{children}</>;
  }
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={{ token: "test-token" }}>
        <WorkflowProvider>
          <ThemeProvider>
            <AnalysisProvider>
              <SeedAnalysis>
                <Routes>
                  <Route path="/shipments/:caseId" element={<ShipmentWorkspacePage />} />
                  <Route path="/dashboard" element={<div>Dashboard</div>} />
                  <Route path="/shipments" element={<div>Shipments list</div>} />
                  <Route path="/workspace/documents" element={<div>Documents</div>} />
                </Routes>
              </SeedAnalysis>
            </AnalysisProvider>
          </ThemeProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("workspace rendering", () => {
  it("shows identity, state, briefing, and action in reading order", () => {
    seed([seedEntry("evidence_pending")]);
    renderWorkspace("/shipments/case-1");
    expect(
      screen.getByRole("heading", { name: "Cocoa · Lagos → Rotterdam", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Shipment")).toBeInTheDocument();
    expect(screen.getByText("Xportra needs a document from you.")).toBeInTheDocument();
    expect(screen.getByText("Xportra’s briefing")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload document" })).toHaveAttribute(
      "href",
      "/workspace/evidence",
    );
    expect(screen.getByRole("button", { name: "Your shipments" })).toBeInTheDocument();
  });

  it("renders findings as attention plus ledger with progress", () => {
    seed([seedEntry("review_required")]);
    renderWorkspace("/shipments/case-1", analysisReport("case-1", ["satisfied", "not_satisfied"]));
    expect(screen.getByText("One requirement needs your attention.")).toBeInTheDocument();
    const attention = screen.getByRole("heading", { name: /What needs attention/ });
    expect(attention.textContent).toContain("1");
    const requirements = screen.getByRole("heading", { name: /Requirements/ });
    expect(requirements.textContent).toContain("1 of 2 addressed");
    const scope = within(requirements.closest("section") as HTMLElement);
    expect(
      scope.getByRole("button", { name: "Phytosanitary certificate — Addressed" }),
    ).toBeInTheDocument();
    expect(
      scope.getByRole("button", { name: "Certificate of origin — Needs attention" }),
    ).toBeInTheDocument();
    // The ledger carries no card chrome and no inline disclosures.
    expect(screen.getByRole("main").querySelector(".xb-card, .xb-req-card")).toBeNull();
    expect(screen.queryByRole("button", { name: "Why is this required?" })).toBeNull();
  });

  it("falls back honestly without findings data", () => {
    seed([seedEntry("additional_evidence_requested", { open_requirements: ["o1", "o2"] })]);
    renderWorkspace("/shipments/case-1");
    expect(screen.getByText(/2 requirements are flagged/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review requirements" })).toHaveAttribute(
      "href",
      "/workspace/requirements",
    );
    expect(screen.queryByText(/of \d+ requirements addressed/)).toBeNull();
  });

  it("renders completed shipments read-only without mutating actions", () => {
    seed([seedEntry("assessment_package_ready")]);
    renderWorkspace("/shipments/case-1");
    const banner = screen.getByRole("note");
    expect(banner.textContent).toContain("This shipment is complete and read-only.");
    expect(banner.textContent).toContain("It’s kept as a compliance record.");
    expect(screen.getByText("Everything Xportra could check is complete.")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /upload|run|re-run|finalize/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /upload|run compliance/i })).toBeNull();
  });

  it("asks for a shipment when none is open", () => {
    seed([]);
    renderWorkspace("/shipments/unknown-case");
    expect(screen.getByRole("heading", { name: "No shipment open" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to dashboard" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});

describe("document drawer seam", () => {
  it("opens requirement context from the ledger row and closes on Escape", () => {
    seed([seedEntry("review_required")]);
    renderWorkspace("/shipments/case-1", analysisReport("case-1", ["not_satisfied"]));
    const rows = screen.getAllByRole("button", { name: "Phytosanitary certificate — Needs attention" });
    expect(rows.length).toBeGreaterThan(0);
    fireEvent.click(rows[0]);
    const dialog = screen.getByRole("dialog", { name: "Requirement: Phytosanitary certificate" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const drawer = within(dialog);
    expect(drawer.getByRole("button", { name: "Back to shipment" })).toBeInTheDocument();
    expect(drawer.getByRole("button", { name: "Upload document" })).toBeInTheDocument();
    fireEvent.click(drawer.getByRole("button", { name: "Back to shipment" }));
    expect(screen.queryByRole("dialog", { name: "Requirement: Phytosanitary certificate" })).toBeNull();
  });
});

describe("workspace scope pins", () => {
  it("exposes no technical states, scores, or invented concepts", () => {
    seed([seedEntry("review_required", { supplied_evidence_ids: ["e1"] })]);
    renderWorkspace("/shipments/case-1", analysisReport("case-1", ["satisfied", "unknown"]));
    const main = screen.getByRole("main");
    for (const technical of [
      "evidence_pending",
      "review_required",
      "applicability_determined",
      "reanalysis_required",
      "additional_evidence_requested",
    ]) {
      expect(main.textContent).not.toContain(technical);
    }
    expect(main.textContent).not.toMatch(/%|compliance score|Run Compliance|AI thinking/i);
    expect(main.querySelector("svg, canvas")).toBeNull();
    for (const name of ["Documents", "Requirements", "Evidence", "Assessment"]) {
      expect(screen.queryByRole("link", { name })).toBeNull();
    }
  });
});
