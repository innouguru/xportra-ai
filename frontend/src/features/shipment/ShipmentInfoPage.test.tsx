import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ShipmentInfoPage } from "./ShipmentInfoPage";
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
  sessionStorage.clear();
});

function renderWithRecord() {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(RECORD));
  render(
    <MemoryRouter initialEntries={["/workspace/info"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <Routes>
            <Route path="/workspace/info" element={<ShipmentInfoPage />} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("ShipmentInfoPage", () => {
  it("confirms a recorded step without inventing timestamps", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            workflow: { ...RECORD, state: "information_provided" },
            summary: {},
          }),
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.click(screen.getByRole("button", { name: "Provide shipment information" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/saved/i);
    expect(screen.queryByText(/\d{4}-\d{2}-\d{2}T\d{2}:/)).toBeNull();
  });

  it("clears the confirmation when the next action starts", async () => {
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        calls += 1;
        if (calls === 1) {
          return new Response(
            JSON.stringify({
              workflow: { ...RECORD, state: "information_provided" },
              summary: {},
            }),
            { status: 200 },
          );
        }
        return new Promise(() => {});
      }),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.click(screen.getByRole("button", { name: "Provide shipment information" }));
    await screen.findByRole("status");
    await user.click(screen.getByRole("button", { name: "Mark evidence pending" }));
    expect(screen.queryByRole("status", { name: /saved/i })).toBeNull();
  });
});
