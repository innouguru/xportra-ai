import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { AuthCallbackPage } from "./AuthCallbackPage";

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
});
