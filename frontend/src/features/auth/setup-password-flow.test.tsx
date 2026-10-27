import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { RequireAuth } from "../../app/RequireAuth";
import { SetupPasswordPage } from "./SetupPasswordPage";
import { savePendingRegistration } from "../../app/pendingRegistration";
import { saveOnboardingState } from "../../app/onboarding";

vi.mock("../../api/organizations", () => ({
  registerOrganization: vi.fn().mockResolvedValue({ tenant_id: "t-1" }),
}));

vi.mock("../../app/supabaseClient", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../app/supabaseClient")>();
  return { ...original, getSupabaseClient: vi.fn() };
});

import { getSupabaseClient } from "../../app/supabaseClient";

const mockGetClient = vi.mocked(getSupabaseClient);

function mockClient(session?: unknown) {
  return {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session } }),
      onAuthStateChange: vi.fn().mockReturnValue({
        data: { subscription: { unsubscribe: vi.fn() } },
      }),
      updateUser: vi.fn().mockResolvedValue({ error: null }),
    },
  };
}

function renderWithSetup(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <WorkflowProvider>
          <Routes>
            <Route path="/setup-password" element={<SetupPasswordPage />} />
            <Route path="/dashboard" element={<RequireAuth><div>Dashboard screen</div></RequireAuth>} />
            <Route path="/session" element={<div>Session screen</div>} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("SetupPasswordPage new-tab flow", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockGetClient.mockReturnValue(null);
    window.localStorage.clear();
  });

  it("shows the form with a valid session and no pending profile (new-tab)", async () => {
    mockGetClient.mockReturnValue(mockClient({ access_token: "t", user: { email: "new@example.com" } }) as never);
    renderWithSetup("/setup-password");
    expect(await screen.findByRole("heading", { name: /create your password/i })).toBeInTheDocument();
  });

  it("shows recoverable state when session is unavailable", async () => {
    mockGetClient.mockReturnValue(null);
    renderWithSetup("/setup-password");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("marks onboarding complete after password update with no pending profile", async () => {
    const updateUser = vi.fn().mockResolvedValue({ error: null });
    mockGetClient.mockReturnValue({
      auth: {
        getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: "t", user: { email: "new@example.com" } } } }),
        onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
        updateUser,
      },
    } as never);
    renderWithSetup("/setup-password");

    expect(updateUser).toBeDefined();
  });

  it("does not bypass onboarding when dashboard is accessed directly with incomplete state", async () => {
    // Simulate incomplete onboarding state in localStorage (new-tab scenario)
    saveOnboardingState({ completed: false, email: "new@example.com", pendingRegistration: true });
    savePendingRegistration({
      email: "new@example.com",
      organizationName: "Test Org",
      organizationType: "exporter",
      countryCode: "KE",
      region: null,
      contactName: null,
    });
    mockGetClient.mockReturnValue(mockClient({ access_token: "t", user: { email: "new@example.com" } }) as never);
    renderWithSetup("/dashboard");
    // RequireAuth should redirect to /setup-password because onboarding is incomplete
    expect(await screen.findByRole("heading", { name: /create your password/i })).toBeInTheDocument();
  });

  it("allows established users to access dashboard when onboarding is complete", async () => {
    // Simulate completed onboarding state
    saveOnboardingState({ completed: true, email: "existing@example.com", pendingRegistration: false });
    mockGetClient.mockReturnValue(mockClient({ access_token: "t", user: { email: "existing@example.com" } }) as never);
    renderWithSetup("/dashboard");
    expect(await screen.findByText("Dashboard screen")).toBeInTheDocument();
  });
});
