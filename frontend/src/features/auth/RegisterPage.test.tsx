import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { savePendingRegistration } from "../../app/pendingRegistration";
import { RegisterPage } from "./RegisterPage";

vi.mock("../../app/supabaseClient", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../app/supabaseClient")>();
  return { ...original, getSupabaseClient: vi.fn(() => null) };
});
vi.mock("../../api/organizations", () => ({ registerOrganization: vi.fn() }));
import { registerOrganization } from "../../api/organizations";

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/register"]}>
      <AuthProvider initial={{ token: "verified-session-token" }}>
        <WorkflowProvider>
          <Routes>
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/dashboard" element={<div>Dashboard screen</div>} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  window.sessionStorage.clear();
});

describe("RegisterPage recovery", () => {
  it("keeps a failed registration retryable and prevents duplicate submissions", async () => {
    const pending = {
      email: "owner@example.com",
      organizationName: "Rift Valley Produce",
      organizationType: "exporter" as const,
      countryCode: "KE",
      region: null,
      contactName: null,
    };
    savePendingRegistration(pending);
    let finishRequest!: (value: unknown) => void;
    vi.mocked(registerOrganization).mockReturnValueOnce(
      new Promise((resolve) => { finishRequest = resolve; }) as never,
    );
    const user = userEvent.setup();
    renderPage();

    const resume = await screen.findByRole("button", { name: /resume registration/i });
    await user.click(resume);
    await user.click(resume);
    expect(registerOrganization).toHaveBeenCalledTimes(1);
    expect(resume).toBeDisabled();
    finishRequest({ tenant_id: "tenant-1" });

    expect(await screen.findByText("Dashboard screen")).toBeInTheDocument();
    expect(window.sessionStorage.getItem("xportra.pending-registration.v1")).toBeNull();
  });

  it("retains pending profile data and shows a safe retry after API failure", async () => {
    const pending = {
      email: "owner@example.com",
      organizationName: "Rift Valley Produce",
      organizationType: "exporter" as const,
      countryCode: "KE",
      region: null,
      contactName: null,
    };
    savePendingRegistration(pending);
    vi.mocked(registerOrganization).mockRejectedValueOnce(new Error("network down"));
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /resume registration/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be reached/i);
    expect(window.sessionStorage.getItem("xportra.pending-registration.v1")).not.toBeNull();
    expect(screen.getByRole("button", { name: /resume registration/i })).toBeEnabled();
  });
});
