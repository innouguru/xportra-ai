import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { savePendingRegistration } from "../../app/pendingRegistration";
import { AuthCallbackPage } from "./AuthCallbackPage";

vi.mock("../../api/organizations", () => ({
  registerOrganization: vi.fn().mockResolvedValue({ tenant_id: "tenant-1" }),
}));


vi.mock("../../app/supabaseClient", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../app/supabaseClient")>();
  return {
    ...original,
    getSupabaseClient: vi.fn(),
  };
});

import { getSupabaseClient } from "../../app/supabaseClient";

const mockGetClient = vi.mocked(getSupabaseClient);

function mockClient() {
  const auth = {
    getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    onAuthStateChange: vi.fn().mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    }),
    signInWithOtp: vi.fn(),
    signOut: vi.fn(),
    exchangeCodeForSession: vi.fn(),
  };
  return { client: { auth }, auth };
}

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <WorkflowProvider>
          <Routes>
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route path="/session" element={<div>Session screen</div>} />
            <Route path="/start" element={<div>Start screen</div>} />
            <Route path="/setup-password" element={<div>Create your password</div>} />
            <Route path="/dashboard" element={<div>Dashboard screen</div>} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  mockGetClient.mockReturnValue(null);
  window.localStorage.clear();
});

describe("AuthCallbackPage", () => {
  it("exchanges a valid code and navigates to the safe return path", async () => {
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: { access_token: "fresh-token" } },
      error: null,
    });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/auth/callback?code=valid-code&next=/dashboard");
    expect(await screen.findByText("Dashboard screen")).toBeInTheDocument();
    expect(auth.exchangeCodeForSession).toHaveBeenCalledTimes(1);
    expect(auth.exchangeCodeForSession).toHaveBeenCalledWith("valid-code");
    expect(document.body.textContent).not.toMatch(/valid-code/);
  });

  it("falls back to the workspace for hostile return paths", async () => {
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: { access_token: "fresh-token" } },
      error: null,
    });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/auth/callback?code=valid-code&next=https://evil.example.com/dashboard");
    expect(await screen.findByText("Start screen")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard screen")).toBeNull();
  });

  it("shows recovery for expired or reused codes", async () => {
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: null },
      error: { message: "code expired" },
    });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/auth/callback?code=stale-code");
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid, expired, or already used/i);
    expect(screen.getByRole("link", { name: /back to sign in/i })).toHaveAttribute(
      "href",
      "/session",
    );
    expect(document.body.textContent).not.toMatch(/stale-code|code expired/);
  });

  it("shows recovery when the code is missing", async () => {
    const { client } = mockClient();
    mockGetClient.mockReturnValue(client as never);
    renderAt("/auth/callback");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to sign in/i })).toBeInTheDocument();
  });

  it("shows recovery when sign-in is unconfigured", async () => {
    mockGetClient.mockReturnValue(null);
    renderAt("/auth/callback?code=any-code");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/not configured/i);
  });

  it("redirects new registration confirmation (no cached profile) to password setup", async () => {
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: {
        session: {
          access_token: "fresh-token",
          user: { email: "owner@example.com" },
        },
      },
      error: null,
    });
    mockGetClient.mockReturnValue(client as never);
    // Simulate new-tab confirmation: no pending profile in storage.
    renderAt("/auth/callback?code=valid-code&flow=registration");
    // New registrations with no cached profile are still directed to
    // password creation — PKCE confirmation establishes the session.
    expect(await screen.findByText("Create your password")).toBeInTheDocument();
    expect(window.localStorage.getItem("xportra.onboarding-state.v1")).not.toBeNull();
  });

  it("recovers the same-tab profile and redirects new registrations to password creation", async () => {
    const pending = {
      email: "owner@example.com",
      organizationName: "Rift Valley Produce",
      organizationType: "exporter" as const,
      countryCode: "KE",
      region: null,
      contactName: null,
    };
    savePendingRegistration(pending);
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: {
        session: {
          access_token: "fresh-token",
          user: { email: "owner@example.com" },
        },
      },
      error: null,
    });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/auth/callback?code=valid-code&flow=registration");
    // New registrations with a pending profile are directed to the
    // dedicated password-creation screen; organization finalization
    // runs only after the user has set a password.
    expect(await screen.findByText("Create your password")).toBeInTheDocument();
    expect(window.localStorage.getItem("xportra.pending-registration.v1")).not.toBeNull();
    expect(window.localStorage.getItem("xportra.onboarding-state.v1")).not.toBeNull();
  });
});
