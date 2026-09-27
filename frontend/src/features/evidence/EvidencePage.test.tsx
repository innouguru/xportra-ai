import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
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

const EVIDENCE_ID = "77777777-7777-7777-7777-777777777777";

function uploadResult(overrides: Record<string, unknown> = {}) {
  return {
    evidence_id: EVIDENCE_ID,
    tenant_id: RECORD.tenant_id,
    document_title: "Phyto certificate",
    document_type: "pdf",
    status: "uploaded",
    processing_status: "ready",
    processing_step: "complete",
    processing_error: null,
    content_hash: "ab".repeat(32),
    original_filename: "certificate.pdf",
    mime_type: "application/pdf",
    duplicate: false,
    linked_requirement_ids: [],
    ...overrides,
  };
}

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
            <Route path="/workspace" element={<Outlet />}>
              <Route path="evidence" element={<EvidencePage />} />
            </Route>
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function pdfFile(name = "certificate.pdf", size = 18): File {
  const bytes = new Uint8Array(size).fill(0x25);
  return new File([bytes], name, { type: "application/pdf" });
}

describe("EvidencePage", () => {
  it("renders a real Upload evidence action with format guidance", () => {
    renderWithRecord();
    expect(screen.getByRole("heading", { name: "Upload evidence" })).toBeInTheDocument();
    expect(screen.getByLabelText("Choose a file to upload")).toBeInTheDocument();
    expect(screen.getAllByText(/PDF, Word \(.docx\), JPEG, or PNG/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Maximum 10 MB per file/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Upload evidence" }),
    ).toBeInTheDocument();
  });

  it("shows the selected file name and size before uploading", async () => {
    const user = userEvent.setup();
    renderWithRecord();
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    expect(screen.getByText("certificate.pdf")).toBeInTheDocument();
    expect(screen.getByText("18 B")).toBeInTheDocument();
    expect(screen.getByText("This file is ready to upload.")).toBeInTheDocument();
  });

  it("rejects oversized files client-side before any request", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        return new Response(JSON.stringify(uploadResult()), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithRecord();
    const big = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "big.pdf", {
      type: "application/pdf",
    });
    await user.upload(screen.getByLabelText("Choose a file to upload"), big);
    expect(await screen.findByRole("alert")).toHaveTextContent(/over the 10 MB limit/);
    expect(screen.getByRole("button", { name: "Upload evidence" })).toBeDisabled();
    expect(calls.filter((url) => url.endsWith("/compliance-evidence/uploads"))).toHaveLength(0);
  });

  it("uploads through the real endpoint and shows honest ready state", async () => {
    const calls: Array<{ url: string; body: Record<string, unknown> }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/compliance-evidence/uploads")) {
          calls.push({ url, body: JSON.parse(String(init?.body)) });
          return new Response(JSON.stringify(uploadResult()), { status: 201 });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    await waitFor(() =>
      expect(
        screen.getByText(/is ready as evidence\. This does not mean any requirement is satisfied\./),
      ).toBeInTheDocument(),
    );
    expect(calls).toHaveLength(1);
    const body = calls[0].body;
    expect(body["filename"]).toBe("certificate.pdf");
    expect(body["content_type"]).toBe("application/pdf");
    expect(typeof body["content_base64"]).toBe("string");
    expect((body["workflow"] as Record<string, unknown>)["id"]).toBe(RECORD.id);
    expect(body).not.toHaveProperty("tenant_id");
    const page = document.body.textContent ?? "";
    expect(page).not.toMatch(/compliant|verified|approved/i);
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("shows failed processing as unusable without compliance meaning", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/compliance-evidence/uploads")) {
          return new Response(
            JSON.stringify(uploadResult({ processing_status: "failed", processing_step: "parse" })),
            { status: 201 },
          );
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    await waitFor(() =>
      expect(screen.getAllByText(/cannot be used as evidence/).length).toBeGreaterThan(0),
    );
    expect(screen.getByText("Failed")).toBeInTheDocument();
    const supply = screen.getByRole("button", { name: "Supply to workflow" });
    expect(supply).toBeDisabled();
    expect(supply).toHaveAttribute("title", "Failed documents cannot be supplied");
  });

  it("surfaces upload failure without losing the selection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ error: { code: "payload_too_large", message: "Too big." } }),
            { status: 413 },
          ),
      ),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    expect(await screen.findByText(/larger than the 10 MB limit/)).toBeInTheDocument();
    expect(screen.getByText("certificate.pdf")).toBeInTheDocument();
  });

  it("supplies an uploaded document through the existing workflow route", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        if (url.endsWith("/compliance-evidence/uploads")) {
          return new Response(JSON.stringify(uploadResult()), { status: 201 });
        }
        return new Response(
          JSON.stringify({
            workflow: { ...RECORD, supplied_evidence_ids: [EVIDENCE_ID] },
            summary: {},
          }),
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithRecord({ ...RECORD, supplied_evidence_ids: [] });
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    await user.click(await screen.findByRole("button", { name: "Supply to workflow" }));
    await waitFor(() => {
      expect(calls.some((url) => url.endsWith("/compliance/workflows/supply-evidence"))).toBe(true);
    });
  });

  it("renders supplied evidence with fetched document detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/compliance-evidence/66666666-6666-6666-0000-000000000001")) {
          return new Response(
            JSON.stringify({
              id: "66666666-6666-6666-0000-000000000001",
              document_title: "Phyto certificate",
              document_type: "certificate",
              status: "accepted",
              processing_status: "ready",
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    renderWithRecord();
    const section = screen.getByRole("region", { name: "Supplied evidence" });
    expect(await within(section).findByText("Phyto certificate")).toBeInTheDocument();
    expect(within(section).getByText("accepted")).toBeInTheDocument();
    expect(within(section).getByText("Ready")).toBeInTheDocument();
  });

  it("downloads through the authorized endpoint without showing the URL", async () => {
    const calls: string[] = [];
    const opened: string[] = [];
    vi.stubGlobal(
      "open",
      vi.fn((url: string) => {
        opened.push(url);
        return null;
      }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        if (url.endsWith("/compliance-evidence/uploads")) {
          return new Response(JSON.stringify(uploadResult()), { status: 201 });
        }
        if (url.endsWith("/download")) {
          return new Response(
            JSON.stringify({
              evidence_id: EVIDENCE_ID,
              tenant_id: RECORD.tenant_id,
              download_url: "https://signed.example/d1",
              expires_in_seconds: 300,
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithRecord({ ...RECORD, supplied_evidence_ids: [] });
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    await user.click(await screen.findByRole("button", { name: "Download document" }));
    await waitFor(() => expect(opened).toHaveLength(1));
    expect(opened[0]).toBe("https://signed.example/d1");
    expect(
      calls.some((url) => url.endsWith(`/compliance-evidence/${EVIDENCE_ID}/download`)),
    ).toBe(true);
    expect(document.body.textContent ?? "").not.toContain("https://signed.example/d1");
  });

  it("surfaces download failure honestly", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/compliance-evidence/uploads")) {
          return new Response(JSON.stringify(uploadResult()), { status: 201 });
        }
        return new Response(
          JSON.stringify({ error: { code: "not_found", message: "Gone." } }),
          { status: 404 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithRecord({ ...RECORD, supplied_evidence_ids: [] });
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    await user.click(await screen.findByRole("button", { name: "Download document" }));
    expect(await screen.findByText("The requested record was not found in this workspace.")).toBeInTheDocument();
  });

  it("disables upload on a finalized workflow with the reason stated", () => {
    renderWithRecord({ ...RECORD, state: "assessment_package_ready" });
    expect(
      screen.getByText("Upload is unavailable — this assessment has been finalized and can no longer be changed."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Choose a file to upload")).toBeNull();
    expect(screen.queryByRole("button", { name: "Upload evidence" })).toBeNull();
    expect(screen.queryByRole("button", { name: /reopen/i })).toBeNull();
  });

  it("offers the existing re-analysis path after post-analysis evidence", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/compliance-evidence/uploads")) {
          return new Response(JSON.stringify(uploadResult()), { status: 201 });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithRecord({
      ...RECORD,
      state: "analysis_available",
      rounds: [
        {
          round_index: 1,
          report_id: "99999999-9999-9999-9999-999999999999",
          analysis_ids: [],
          trace_ids: [],
          input_fingerprints: [],
        },
      ],
      supplied_evidence_ids: [],
    });
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    await waitFor(() =>
      expect(
        screen.getByText("New evidence is available — analysis may need to be rerun"),
      ).toBeInTheDocument(),
    );
    const rerunLinks = screen.getAllByRole("link", { name: "Run analysis again" });
    expect(rerunLinks.length).toBeGreaterThan(0);
    for (const link of rerunLinks) {
      expect(link).toHaveAttribute("href", "/workspace/analysis");
    }
  });

  it("renders requirement associations when the backend returns them", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/compliance-evidence/uploads")) {
          return new Response(
            JSON.stringify(
              uploadResult({ linked_requirement_ids: ["44444444-4444-4444-4444-444444444444"] }),
            ),
            { status: 201 },
          );
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithRecord({ ...RECORD, supplied_evidence_ids: [] });
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    await waitFor(() =>
      expect(screen.getByTitle("44444444-4444-4444-4444-444444444444")).toBeInTheDocument(),
    );
  });

  it("says association is pending when the backend returns none", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/compliance-evidence/uploads")) {
          return new Response(JSON.stringify(uploadResult()), { status: 201 });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithRecord({ ...RECORD, supplied_evidence_ids: [] });
    await user.upload(screen.getByLabelText("Choose a file to upload"), pdfFile());
    await user.click(screen.getByRole("button", { name: "Upload evidence" }));
    await waitFor(() =>
      expect(
        screen.getByText("Requirement association will be determined from the compliance context."),
      ).toBeInTheDocument(),
    );
  });

  it("keeps needed and attention areas free of compliance verdicts", () => {
    renderWithRecord({
      ...RECORD,
      state: "additional_evidence_requested",
      supplied_evidence_ids: [],
      open_requirements: ["44444444-4444-4444-4444-444444444444"],
    });
    expect(screen.getByText("Needed (1)")).toBeInTheDocument();
    expect(screen.getByText(/not non-compliance/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "What information is missing" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Additional evidence was requested")).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/failed|non-compliant|score/i);
  });

  it("keeps the upload control keyboard-accessible with labelled status", async () => {
    const user = userEvent.setup();
    renderWithRecord({ ...RECORD, supplied_evidence_ids: [] });
    const input = screen.getByLabelText("Choose a file to upload");
    expect(input).toHaveAttribute("type", "file");
    expect(input).toHaveAttribute("accept", ".pdf,.docx,.jpg,.jpeg,.png");
    input.focus();
    expect(input).toHaveFocus();
    await user.upload(input, pdfFile());
    expect(screen.getByLabelText("Selected file")).toBeInTheDocument();
  });
});
