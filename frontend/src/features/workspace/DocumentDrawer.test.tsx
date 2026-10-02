import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { MemoryRouter } from "react-router-dom";
import { AnalysisProvider, useAnalysis } from "../../app/AnalysisContext";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ThemeProvider } from "../../theme/theme";
import type { AnalysisFinding, AnalysisReport, WorkflowRecord } from "../../types/api";
import { DocumentDrawer, type DrawerRequirement } from "./DocumentDrawer";

/**
 * Phase 10.8F drawer contract.
 *
 * Backend calls are mocked at the fetch
 * boundary with exact-contract payloads;
 * fixtures are test-only. Every asserted
 * behavior must trace to a real endpoint or
 * an honest seam — no simulated verification.
 */

const REQUIREMENT: DrawerRequirement = {
  id: "r1",
  title: "Phytosanitary certificate",
  statusLabel: "Needs attention",
  tone: "warning",
  explanation: "Required by the destination authority.",
};

function workflow(extra?: Partial<WorkflowRecord>): WorkflowRecord {
  return {
    id: "id-1",
    tenant_id: "tenant-1",
    case_id: "case-1",
    shipment_id: null,
    state: "evidence_pending",
    rounds: [],
    supplied_evidence_ids: [],
    open_requirements: [],
    ...extra,
  };
}

function finding(assessment: string): AnalysisFinding {
  return {
    analysis_id: "a1",
    requirement_id: "r1",
    requirement_text: "Phytosanitary certificate",
    applicability: "applicable",
    assessment,
    explanation: "The certificate was reviewed.",
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

function analysisReport(assessments: string[]): AnalysisReport {
  return {
    report_id: "rep-1",
    case_id: "case-1",
    counts: {},
    requirements_with_missing_information: [],
    uncertain_requirement_ids: [],
    requirements_with_conflicting_evidence: [],
    conflicting_evidence_count: 0,
    findings: assessments.map(finding),
  };
}

const UPLOAD_RESULT = {
  evidence_id: "ev-1",
  tenant_id: "tenant-1",
  document_title: "Certificate",
  document_type: "certificate",
  status: "uploaded",
  processing_status: "ready",
  processing_step: null,
  processing_error: null,
  content_hash: null,
  original_filename: "cert.pdf",
  mime_type: "application/pdf",
  duplicate: false,
  linked_requirement_ids: ["r1"],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function stubFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => handler(url, init)),
  );
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

function renderDrawer(options?: { report?: AnalysisReport | null; record?: WorkflowRecord }) {
  stubMatchMedia();
  const record = options?.record ?? workflow();
  window.sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  const report = options?.report ?? null;
  const onClose = vi.fn();
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
    <MemoryRouter>
      <AuthProvider initial={{ token: "test-token" }}>
        <WorkflowProvider>
          <ThemeProvider>
            <AnalysisProvider>
              <SeedAnalysis>
                <DocumentDrawer requirement={REQUIREMENT} onClose={onClose} />
              </SeedAnalysis>
            </AnalysisProvider>
          </ThemeProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
  return { onClose };
}

function pdfFile(name = "cert.pdf", size = 1024): File {
  const bytes = new Uint8Array(size);
  return new File([bytes], name, { type: "application/pdf" });
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("verification drawer", () => {
  it("opens with requirement context and no fabricated result", () => {
    renderDrawer();
    expect(
      screen.getByRole("dialog", { name: "Requirement: Phytosanitary certificate" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Requirement")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to shipment" })).toBeInTheDocument();
    expect(screen.getByText("Required by the destination authority.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload document" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Result" })).toBeNull();
    expect(document.activeElement?.textContent).toContain("Back to shipment");
  });

  it("closes on Escape", () => {
    const { onClose } = renderDrawer();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("uploads through the real endpoint with backend-owned constraints", async () => {
    const spy = vi.fn(async () => jsonResponse(UPLOAD_RESULT, 201));
    stubFetch(spy);
    const user = userEvent.setup();
    renderDrawer();
    await user.upload(screen.getByLabelText("Choose a file"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByText(/is ready as evidence/)).toBeInTheDocument();
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/compliance-evidence/uploads");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["requirement_ids"]).toEqual(["r1"]);
    expect(typeof body["content_base64"]).toBe("string");
  });

  it("rejects unsupported files before any request", async () => {
    const spy = vi.fn(async () => jsonResponse({}, 201));
    stubFetch(spy);
    const user = userEvent.setup();
    renderDrawer();
    const big = new Uint8Array(11 * 1024 * 1024);
    await user.upload(
      screen.getByLabelText("Choose a file"),
      new File([big], "huge.pdf", { type: "application/pdf" }),
    );
    expect(await screen.findByText(/over the 10 MB limit/)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("verifies by supplying, then reads the recorded finding", async () => {
    stubFetch((url) => {
      if (url.endsWith("/compliance-evidence/uploads")) {
        return jsonResponse(UPLOAD_RESULT, 201);
      }
      if (url.endsWith("/compliance/workflows/supply-evidence")) {
        return jsonResponse({
          workflow: workflow({ supplied_evidence_ids: ["ev-1"] }),
          summary: {},
        });
      }
      throw new Error(`unexpected ${url}`);
    });
    const user = userEvent.setup();
    renderDrawer({ report: analysisReport(["satisfied"]) });
    await user.upload(screen.getByLabelText("Choose a file"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    await screen.findByText(/is ready as evidence/);
    await user.click(screen.getByRole("button", { name: "Verify document" }));
    expect(await screen.findByRole("heading", { name: "Result" })).toBeInTheDocument();
    expect(screen.getByText("Satisfied")).toBeInTheDocument();
    expect(screen.getByText("From the latest recorded analysis round.")).toBeInTheDocument();
  });

  it("reports unknown when no finding exists, with an analysis path", async () => {
    stubFetch((url) => {
      if (url.endsWith("/compliance-evidence/uploads")) {
        return jsonResponse(UPLOAD_RESULT, 201);
      }
      if (url.endsWith("/compliance/workflows/supply-evidence")) {
        return jsonResponse({ workflow: workflow({ supplied_evidence_ids: ["ev-1"] }), summary: {} });
      }
      throw new Error(`unexpected ${url}`);
    });
    const user = userEvent.setup();
    renderDrawer({ report: null });
    await user.upload(screen.getByLabelText("Choose a file"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    await screen.findByText(/is ready as evidence/);
    await user.click(screen.getByRole("button", { name: "Verify document" }));
    expect(await screen.findByText("Unknown")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open analysis" })).toHaveAttribute(
      "href",
      "/workspace/analysis",
    );
  });

  it("opens and previews documents through authorized grants", async () => {
    stubFetch((url) => {
      if (url.endsWith("/compliance-evidence/uploads")) {
        return jsonResponse(UPLOAD_RESULT, 201);
      }
      if (url.includes("/download")) {
        return jsonResponse({
          evidence_id: "ev-1",
          tenant_id: "tenant-1",
          download_url: "https://signed.example/doc",
          expires_in_seconds: 60,
        });
      }
      throw new Error(`unexpected ${url}`);
    });
    const open = vi.fn();
    window.open = open as unknown as typeof window.open;
    const user = userEvent.setup();
    renderDrawer();
    await user.upload(screen.getByLabelText("Choose a file"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    await screen.findByText(/is ready as evidence/);
    await user.click(screen.getByRole("button", { name: "Open document" }));
    await waitFor(() =>
      expect(open).toHaveBeenCalledWith("https://signed.example/doc", "_blank", expect.anything()),
    );
    await user.click(screen.getByRole("button", { name: "Show preview" }));
    expect(await screen.findByTitle("Preview of document ev-1")).toBeInTheDocument();
  });

  it("reports failures plainly with no false success", async () => {
    stubFetch(async () => {
      throw new Error("network down");
    });
    const user = userEvent.setup();
    renderDrawer();
    await user.upload(screen.getByLabelText("Choose a file"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Result" })).toBeNull();
    expect(screen.getByLabelText("Choose a file")).toBeInTheDocument();
  });

  it("stays read-only on completed shipments", () => {
    renderDrawer({ record: workflow({ state: "assessment_package_ready" }) });
    expect(screen.getByText(/historical record — read-only/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Upload document" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Verify document" })).toBeNull();
  });

  it("introduces no scores, scans, or simulated output", () => {
    renderDrawer({ report: analysisReport(["not_satisfied"]) });
    const dialog = screen.getByRole("dialog", { name: /requirement:/i });
    expect(dialog.textContent).not.toMatch(/score|percent|Run Compliance|AI Check|Smart Scan|confidence/i);
    expect(screen.queryByRole("button", { name: /run compliance|analyze everything/i })).toBeNull();
  });
});
