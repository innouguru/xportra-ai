import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { NewShipmentPage } from "./NewShipmentPage";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "created",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <Routes>
            <Route path="/" element={<NewShipmentPage />} />
            <Route path="/workspace" element={<div>Workspace</div>} />
            <Route path="/session" element={<div>Session</div>} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("NewShipmentPage", () => {
  it("leads with the workspace action and keeps identifiers secondary", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: "Start a shipment workspace" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Technical identifiers")).toBeInTheDocument();
    // The primary action still submits the technical contract.
    expect(
      screen.getByRole("button", { name: "Start compliance workflow" }),
    ).toBeInTheDocument();
  });

  it("introduces what the workspace will establish without promising approval", () => {
    renderPage();
    expect(screen.getByText(/will establish/i)).toBeInTheDocument();
    for (const item of [
      "Shipment context for the case under review",
      "Applicable requirements for that context",
      "Evidence coverage against those requirements",
      "Compliance analysis grounded in the evidence supplied",
      "An assessment package for final review",
    ]) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
    expect(screen.getByText(/no outcome here is a regulatory approval/i)).toBeInTheDocument();
  });

  it("rejects malformed IDs client-side with guidance", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByLabelText("Case ID"), "not-a-uuid");
    await user.click(screen.getByRole("button", { name: "Start compliance workflow" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/valid UUID/i);
  });

  it("creates the workflow, preserves the response, and transitions", async () => {
    const spy = vi.fn(async () =>
      new Response(
        JSON.stringify({
          workflow: RECORD,
          summary: { workflow_id: RECORD.id, state: "created" },
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", spy);
    const user = userEvent.setup();
    renderPage();
    await user.type(
      screen.getByLabelText("Case ID"),
      "33333333-3333-3333-3333-333333333333",
    );
    await user.click(screen.getByRole("button", { name: "Start compliance workflow" }));
    await waitFor(() => expect(screen.getByText("Workspace")).toBeInTheDocument());
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/compliance/workflows/start");
    expect(JSON.parse(init.body as string)).toEqual({
      case_id: "33333333-3333-3333-3333-333333333333",
      shipment_id: null,
    });
  });

  it("explains role-based denial without inventing meaning", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ error: { code: "permission_denied", message: "No." } }), {
          status: 403,
        }),
      ),
    );
    const user = userEvent.setup();
    renderPage();
    await user.type(
      screen.getByLabelText("Case ID"),
      "33333333-3333-3333-3333-333333333333",
    );
    await user.click(screen.getByRole("button", { name: "Start compliance workflow" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/workspace owner/i);
  });
});
