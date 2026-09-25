import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { RequirementsPage } from "./RequirementsPage";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "information_provided",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderWithRecord() {
  sessionStorage.setItem(
    "xportra.workflow-record.v1",
    JSON.stringify(RECORD),
  );
  render(
    <MemoryRouter initialEntries={["/workspace/requirements"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <Routes>
            <Route path="/workspace/requirements" element={<RequirementsPage />} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("RequirementsPage", () => {
  it("renders the breakdown form and records the outcome", async () => {
    const spy = vi.fn(async (url: string) => {
      if (url.endsWith("/record-applicability")) {
        return new Response(
          JSON.stringify({
            workflow: { ...RECORD, state: "applicability_determined" },
            summary: {},
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ counts: {}, results: [] }), {
        status: 200,
      });
    });
    vi.stubGlobal("fetch", spy);
    const user = userEvent.setup();
    renderWithRecord();
    await user.click(screen.getByRole("button", { name: "Record applicability outcome" }));
    await waitFor(() => {
      expect(
        spy.mock.calls.some(([url]) =>
          (url as string).endsWith("/record-applicability"),
        ),
      ).toBe(true);
    });
  });

  it("renders backend outcomes verbatim with unknown as attention", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            counts: { applicable: 1, unknown: 1 },
            results: [
              {
                requirement_id: "44444444-4444-4444-4444-444444444444",
                outcome: "applicable",
                reason: "Matches commodity code.",
              },
              {
                requirement_id: "55555555-5555-5555-5555-555555555555",
                outcome: "unknown",
                reason: "Insufficient context.",
              },
            ],
          }),
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Requirement ID"), "req-1");
    await user.type(screen.getByLabelText("Requirement text"), "File form X.");
    await user.click(screen.getByRole("button", { name: "Determine applicability" }));
    expect(await screen.findByText("Matches commodity code.")).toBeInTheDocument();
    expect(screen.getByText("Insufficient context.")).toBeInTheDocument();
    // The unknown outcome renders verbatim with attention tone —
    // never converted into a failure state.
    const unknownBadges = screen
      .getAllByText("unknown")
      .filter((node) => node.closest(".badge") !== null);
    expect(unknownBadges).toHaveLength(1);
    expect(unknownBadges[0].closest(".badge")).toHaveClass("badge--attention");
    const failedOutcomes = screen.queryAllByText("failed", { exact: true });
    expect(failedOutcomes).toHaveLength(0);
  });
});
