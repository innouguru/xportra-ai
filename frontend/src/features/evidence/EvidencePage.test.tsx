import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { EvidencePage } from "./EvidencePage";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "evidence_pending",
  rounds: [],
  supplied_evidence_ids: ["66666666-6666-6666-0000-000000000001"],
  open_requirements: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderWithRecord(record: WorkflowRecord | null = RECORD) {
  if (record) {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(record));
  }
  render(
    <MemoryRouter initialEntries={["/workspace/evidence"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <Routes>
            <Route path="/workspace/evidence" element={<EvidencePage />} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("EvidencePage", () => {
  it("states reference-based intake with no file uploader", () => {
    renderWithRecord();
    expect(screen.getByText(/rather than uploading/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/file upload|drag.*drop|choose file/i)).toBeNull();
    expect(screen.queryByText(/upload progress/i)).toBeNull();
  });

  it("rejects empty references with validation guidance", async () => {
    const user = userEvent.setup();
    renderWithRecord();
    await user.click(screen.getByRole("button", { name: "Register evidence reference" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/required/i);
  });

  it("registers then supplies a reference through the real routes", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        if (url.endsWith("/compliance-evidence")) {
          return new Response(
            JSON.stringify({
              id: "77777777-7777-7777-7777-777777777777",
              document_title: "Phyto certificate",
              document_type: "certificate",
              file_reference_or_uri: "registry://NG-118",
              status: "uploaded",
            }),
            { status: 201 },
          );
        }
        return new Response(
          JSON.stringify({
            workflow: { ...RECORD, supplied_evidence_ids: ["77777777-7777-7777-7777-777777777777"] },
            summary: {},
          }),
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Document title"), "Phyto certificate");
    await user.type(screen.getByLabelText("Document type"), "certificate");
    await user.type(screen.getByLabelText("File reference or URI"), "registry://NG-118");
    await user.click(screen.getByRole("button", { name: "Register evidence reference" }));
    await waitFor(() => expect(screen.getByText("registry://NG-118")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Supply to workflow" }));
    await waitFor(() => {
      expect(calls.some((url) => url.endsWith("/compliance/workflows/supply-evidence"))).toBe(true);
    });
  });

  it("surfaces API failure without losing the form", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ error: { code: "invalid_input", message: "Bad title." } }), {
          status: 400,
        }),
      ),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Document title"), "T");
    await user.type(screen.getByLabelText("Document type"), "certificate");
    await user.type(screen.getByLabelText("File reference or URI"), "uri://x");
    await user.click(screen.getByRole("button", { name: "Register evidence reference" }));
    expect(await screen.findByText("Bad title.")).toBeInTheDocument();
    expect(screen.getByLabelText("Document title")).toHaveValue("T");
  });

  it("renders already-supplied evidence from the workflow record", () => {
    renderWithRecord();
    const section = screen.getByRole("region", { name: "Supplied evidence" });
    expect(within(section).getByTitle("66666666-6666-6666-0000-000000000001")).toBeInTheDocument();
    expect(screen.getByText("Supplied to this workflow (1)")).toBeInTheDocument();
  });
});
