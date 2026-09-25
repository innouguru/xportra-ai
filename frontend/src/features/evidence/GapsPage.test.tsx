import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { GapsPage } from "./GapsPage";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "evidence_pending",
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
    <MemoryRouter initialEntries={["/workspace/gaps"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <Routes>
            <Route path="/workspace/gaps" element={<GapsPage />} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("GapsPage", () => {
  it("renders a ready state without inventing meaning", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            readiness_state: "ready",
            required_information: 2,
            known_information: 2,
            missing_information_count: 0,
            gaps: [],
            missing_evidence_requirements: [],
            unknown_applicability_requirements: [],
            unknown_assessment_requirements: [],
          }),
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Requirement ID"), "req-1");
    await user.type(screen.getByLabelText("Requirement text"), "File form X.");
    await user.click(screen.getByRole("button", { name: "Assess evidence coverage" }));
    expect(await screen.findByText("ready")).toBeInTheDocument();
    expect(screen.getByText(/every required information item is known/i)).toBeInTheDocument();
  });

  it("renders gaps verbatim with reasons, never as non-compliance", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            readiness_state: "partially_ready",
            required_information: 2,
            known_information: 1,
            missing_information_count: 1,
            gaps: [
              {
                requirement_id: "44444444-4444-4444-4444-444444444444",
                kind: "evidence_absent",
                reason: "No certificate on file.",
              },
            ],
            missing_evidence_requirements: ["44444444-4444-4444-4444-444444444444"],
            unknown_applicability_requirements: [],
            unknown_assessment_requirements: [],
          }),
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Requirement ID"), "req-1");
    await user.type(screen.getByLabelText("Requirement text"), "File form X.");
    await user.click(screen.getByRole("button", { name: "Assess evidence coverage" }));
    expect(await screen.findByText("evidence_absent")).toBeInTheDocument();
    expect(screen.getByText("No certificate on file.")).toBeInTheDocument();
    const page = document.body.textContent?.toLowerCase() ?? "";
    expect(page).not.toContain("non-compliant");
    expect(page).not.toContain("failed");
  });

  it("passes cases through without frontend calculation", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify({
      readiness_state: "ready",
      required_information: 0,
      known_information: 0,
      missing_information_count: 0,
      gaps: [],
      missing_evidence_requirements: [],
      unknown_applicability_requirements: [],
      unknown_assessment_requirements: [],
    }), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const user = userEvent.setup();
    renderWithRecord();
    await user.type(screen.getByLabelText("Requirement ID"), "req-9");
    await user.type(screen.getByLabelText("Requirement text"), "Label goods.");
    await user.click(screen.getByRole("button", { name: "Assess evidence coverage" }));
    await screen.findByText("ready");
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(init.body as string) as { cases: Array<Record<string, unknown>> };
    expect(body.cases).toHaveLength(1);
    expect((body.cases[0]["requirement"] as Record<string, unknown>)["id"]).toBe("req-9");
  });
});
