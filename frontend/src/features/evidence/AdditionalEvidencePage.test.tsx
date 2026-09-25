import { describe, expect, it, vi, afterEach } from "vitest";
import { useEffect } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AnalysisProvider, useAnalysis } from "../../app/AnalysisContext";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { AdditionalEvidencePage } from "./AdditionalEvidencePage";
import type { AnalysisFinding, AnalysisReport, WorkflowRecord } from "../../types/api";

const REQUIREMENT_ID = "44444444-4444-4444-4444-444444444444";
const EVIDENCE_ID = "77777777-7777-7777-7777-777777777777";
const REPORT_ID = "99999999-9999-9999-9999-999999999999";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "additional_evidence_requested",
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
  open_requirements: [REQUIREMENT_ID],
};

const FINDING: AnalysisFinding = {
  analysis_id: "a-1",
  requirement_id: REQUIREMENT_ID,
  requirement_text: "Present a phytosanitary certificate before export.",
  applicability: "applicable",
  assessment: "unknown",
  explanation: "The filing is not yet evidenced.",
  uncertainty: "uncertain",
  uncertainty_explanation: "",
  evidence_sufficiency: "insufficient",
  sufficiency_explanation: "",
  contradiction_state: "none",
  missing_information: ["Phytosanitary certificate copy missing."],
  supporting_evidence: [],
  conflicting_evidence: [],
  knowledge_references: [],
  sources: [],
  missing_items: [],
};

const REPORT: AnalysisReport = {
  report_id: REPORT_ID,
  case_id: RECORD.case_id,
  counts: {},
  requirements_with_missing_information: [REQUIREMENT_ID],
  uncertain_requirement_ids: [REQUIREMENT_ID],
  requirements_with_conflicting_evidence: [],
  conflicting_evidence_count: 0,
  findings: [FINDING],
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderPage(record: WorkflowRecord = RECORD, report: AnalysisReport | null = REPORT) {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  function Seed() {
    const { setAnalysis } = useAnalysis();
    useEffect(() => {
      if (report) {
        setAnalysis(report, []);
      }
    }, [setAnalysis]);
    return <AdditionalEvidencePage />;
  }
  render(
    <MemoryRouter initialEntries={["/workspace/additional-evidence"]}>
      <AuthProvider initial={{ devTenantId: RECORD.tenant_id }}>
        <WorkflowProvider>
          <AnalysisProvider>
            <Routes>
              <Route path="/workspace" element={<Outlet />}>
                <Route path="additional-evidence" element={<Seed />} />
                <Route path="analysis" element={<div>Analysis screen</div>} />
                <Route path="review" element={<div>Review screen</div>} />
                <Route path="package" element={<div>Package screen</div>} />
              </Route>
            </Routes>
          </AnalysisProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AdditionalEvidencePage", () => {
  it("explains why evidence was requested using recorded information only", () => {
    renderPage();
    expect(screen.getByText("Why additional evidence was requested")).toBeInTheDocument();
    expect(screen.getByText("additional_evidence_requested")).toBeInTheDocument();
    // The open requirement and its recorded detail come straight from the DTO.
    expect(screen.getByTitle(REQUIREMENT_ID)).toBeInTheDocument();
    expect(
      screen.getByText("Present a phytosanitary certificate before export."),
    ).toBeInTheDocument();
    expect(screen.getByText("Phytosanitary certificate copy missing.")).toBeInTheDocument();
    expect(
      screen.getAllByText(/not a finding of non-compliance/i).length,
    ).toBeGreaterThan(0);
  });

  it("states that intake accepts a reference and offers no file upload", () => {
    renderPage();
    expect(screen.getByText(/rather than uploading file bytes/i)).toBeInTheDocument();
    expect(screen.getByText(/never receives or\s+stores document bytes/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/upload/i)).toBeNull();
    expect(screen.queryByLabelText(/drag|choose file/i)).toBeNull();
    expect(screen.queryByText(/upload progress/i)).toBeNull();
  });

  it("requires requirement identities to request evidence", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Request additional evidence" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/at least one requirement id/i);
  });

  it("records a reference and supplies it with a requirement association", async () => {
    const calls: Array<{ url: string; body: Record<string, unknown> | null }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({
          url,
          body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
        });
        if (url.endsWith("/compliance-evidence/with-requirements")) {
          return new Response(
            JSON.stringify({
              id: EVIDENCE_ID,
              document_title: "Cert copy",
              document_type: "certificate",
              file_reference_or_uri: "registry://NG-1",
              status: "uploaded",
            }),
            { status: 201 },
          );
        }
        return new Response(
          JSON.stringify({
            workflow: {
              ...RECORD,
              state: "reanalysis_required",
              supplied_evidence_ids: [EVIDENCE_ID],
            },
            summary: {},
          }),
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByLabelText("Document title"), "Cert copy");
    await user.type(screen.getByLabelText("Document type"), "cert");
    await user.type(screen.getByLabelText("File reference or URI"), "registry://NG-1");
    await user.type(screen.getByLabelText(/associate requirement ids/i), "req-assoc");
    await user.click(screen.getByRole("button", { name: "Record evidence reference" }));
    expect(await screen.findByText("Cert copy")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Use this evidence ID for supply" }));
    expect(screen.getByLabelText("Evidence ID")).toHaveValue(EVIDENCE_ID);
    await user.type(screen.getByLabelText("Requirement ID (optional)"), "req-assoc");
    await user.click(screen.getByRole("button", { name: "Supply to workflow" }));

    await waitFor(() => {
      expect(
        calls.some((call) => call.url.endsWith("/compliance/workflows/supply-evidence")),
      ).toBe(true);
    });
    const intake = calls.find((call) => call.url.endsWith("/with-requirements"));
    expect(intake?.body?.["requirement_ids"]).toEqual(["req-assoc"]);
    const supply = calls.find((call) =>
      call.url.endsWith("/compliance/workflows/supply-evidence"),
    );
    expect(supply?.body?.["evidence_id"]).toBe(EVIDENCE_ID);
    expect(supply?.body?.["requirement_id"]).toBe("req-assoc");
    // Supplying evidence states plainly what it does and does not do.
    const notice = await screen.findByRole("status");
    expect(notice).toHaveTextContent(/does not establish compliance/i);
    expect(notice).toHaveTextContent(/does not run analysis/i);
  });

  it("surfaces a rejected request and keeps the entered identities", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: { code: "invalid_transition", message: "Workflow cannot move from here." },
          }),
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByLabelText("Requirement IDs"), REQUIREMENT_ID);
    await user.click(screen.getByRole("button", { name: "Request additional evidence" }));
    expect(
      await screen.findByText(/not available in the shipment's current step/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Requirement IDs")).toHaveValue(REQUIREMENT_ID);
  });

  it("disables every mutating control once the workflow is terminal", () => {
    renderPage({ ...RECORD, state: "assessment_package_ready" });
    expect(
      screen.getByText(/additional evidence can no longer be supplied/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request additional evidence" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Record evidence reference" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Supply to workflow" })).toBeDisabled();
    expect(screen.getByLabelText("Evidence ID")).toBeDisabled();
    expect(screen.getByLabelText("Requirement IDs")).toBeDisabled();
  });
});
