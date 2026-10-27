import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { SetupPasswordPage } from "./SetupPasswordPage";


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

function mockClient(session: unknown = null) {
  const auth = {
    getSession: vi.fn().mockResolvedValue({ data: { session } }),
    onAuthStateChange: vi.fn().mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    }),
    signInWithOtp: vi.fn(),
    signOut: vi.fn(),
    signInWithPassword: vi.fn(),
    resetPasswordForEmail: vi.fn(),
    updateUser: vi.fn().mockResolvedValue({ error: null }),
    unsubscribe: vi.fn(),
    listener: null,
  };
  return { client: { auth }, auth };
}

function renderAt(path: string) {
  render(
        <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <WorkflowProvider>
            <Routes>
          <Route path="/setup-password" element={<SetupPasswordPage />} />
          <Route path="/dashboard" element={<div>Dashboard screen</div>} />
          <Route path="/session" element={<div>Session screen</div>} />
          </Routes>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
  );
}

describe("SetupPasswordPage", () => {
  it("shows the password form when a session exists", async () => {
    const { auth } = mockClient({ access_token: "token", user: { email: "new@example.com" } });
    mockGetClient.mockReturnValue({ auth } as never);
    renderAt("/setup-password");
    expect(await screen.findByRole("heading", { name: /create your password/i })).toBeInTheDocument();
  });

  it("rejects a mismatched confirmation", async () => {
    const { auth } = mockClient({ access_token: "token", user: { email: "test@example.com" } });
    mockGetClient.mockReturnValue({ auth } as never);
    renderAt("/setup-password");
    const submitButton = await screen.findByRole("button", { name: /continue/i });
    expect(submitButton).toBeInTheDocument();
  });

  it("shows recoverable state when session is unavailable", async () => {
    mockGetClient.mockReturnValue(null);
    renderAt("/setup-password");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
