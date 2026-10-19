import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ResetPasswordPage } from "./ResetPasswordPage";

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
    signInWithPassword: vi.fn(),
    resetPasswordForEmail: vi.fn(),
    updateUser: vi.fn().mockResolvedValue({ error: null }),
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
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/session" element={<div>Session screen</div>} />
            <Route path="/start" element={<div>Start screen</div>} />
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
  window.sessionStorage.clear();
});

describe("ResetPasswordPage", () => {
  it("exchanges a recovery code and sets a new password", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: { access_token: "recovery-token" } },
      error: null,
    });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password?code=valid-code");
    const password = await screen.findByLabelText(/^new password$/i);
    await user.type(password, "brand-new-password");
    await user.type(screen.getByLabelText(/confirm new password/i), "brand-new-password");
    await user.click(screen.getByRole("button", { name: /set new password/i }));
    expect(await screen.findByRole("status")).toHaveTextContent(/password has been updated/i);
    expect(auth.exchangeCodeForSession).toHaveBeenCalledWith("valid-code");
    expect(auth.updateUser).toHaveBeenCalledWith({ password: "brand-new-password" });
    // The one-time code is never surfaced.
    expect(document.body.textContent).not.toMatch(/valid-code/);
  });

  it("rejects mismatched passwords before calling the provider", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: { access_token: "recovery-token" } },
      error: null,
    });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password?code=valid-code");
    await user.type(await screen.findByLabelText(/^new password$/i), "brand-new-password");
    await user.type(screen.getByLabelText(/confirm new password/i), "different-password");
    await user.click(screen.getByRole("button", { name: /set new password/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/do not match/i);
    expect(auth.updateUser).not.toHaveBeenCalled();
  });

  it("enforces a minimum password length", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: { access_token: "recovery-token" } },
      error: null,
    });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password?code=valid-code");
    await user.type(await screen.findByLabelText(/^new password$/i), "short");
    await user.type(screen.getByLabelText(/confirm new password/i), "short");
    await user.click(screen.getByRole("button", { name: /set new password/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/at least 8 characters/i);
    expect(auth.updateUser).not.toHaveBeenCalled();
  });

  it("shows recovery for invalid or reused codes", async () => {
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: null },
      error: { message: "code expired" },
    });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password?code=stale-code");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/invalid, expired, or already used/i);
    expect(screen.getByRole("link", { name: /request a new link/i })).toHaveAttribute(
      "href",
      "/reset-password",
    );
    expect(screen.getByRole("link", { name: /back to sign in/i })).toHaveAttribute("href", "/session");
    expect(document.body.textContent).not.toMatch(/stale-code|code expired/);
  });

  it("renders recovery email form on direct access and validates email there", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient(null);
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password");
    expect(await screen.findByRole("button", { name: /send recovery link/i })).toBeInTheDocument();
    await user.type(screen.getByLabelText(/email address/i), "invalid");
    await user.click(screen.getByRole("button", { name: /send recovery link/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/valid email address/i);
    expect(auth.resetPasswordForEmail).not.toHaveBeenCalled();
  });

  it("sends a recovery request and shows an account-neutral confirmation", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient(null);
    auth.resetPasswordForEmail.mockResolvedValue({ error: null });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password");
    await user.type(await screen.findByLabelText(/email address/i), "owner@example.com");
    await user.click(screen.getByRole("button", { name: /send recovery link/i }));
    expect(await screen.findByRole("status")).toHaveTextContent(/if an account exists/i);
    expect(auth.resetPasswordForEmail).toHaveBeenCalledWith("owner@example.com", expect.objectContaining({
      redirectTo: expect.stringMatching(/\/reset-password$/),
    }));
    expect(document.body.textContent).not.toContain("owner@example.com");
  });

  it("shows a safe error when the recovery request fails", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient(null);
    auth.resetPasswordForEmail.mockResolvedValue({ error: { message: "provider detail" } });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password");
    await user.type(await screen.findByLabelText(/email address/i), "owner@example.com");
    await user.click(screen.getByRole("button", { name: /send recovery link/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not send a reset link/i);
    expect(alert.textContent).not.toContain("provider detail");
  });

  it("prevents duplicate recovery requests while sending", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient(null);
    let finishRequest!: (value: { error: null }) => void;
    auth.resetPasswordForEmail.mockReturnValueOnce(new Promise((resolve) => {
      finishRequest = resolve;
    }));
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password");
    await user.type(await screen.findByLabelText(/email address/i), "owner@example.com");
    const submit = screen.getByRole("button", { name: /send recovery link/i });
    await user.click(submit);
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/sending recovery link/i);
    await user.click(submit);
    expect(auth.resetPasswordForEmail).toHaveBeenCalledTimes(1);
    finishRequest({ error: null });
    expect(await screen.findByRole("status")).toHaveTextContent(/if an account exists/i);
  });

  it("requires an exchanged recovery session before showing the new-password form", async () => {
    const { client, auth } = mockClient();
    auth.exchangeCodeForSession.mockResolvedValue({ data: { session: null }, error: null });
    mockGetClient.mockReturnValue(client as never);
    renderAt("/reset-password?code=empty-session");
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid, expired, or already used/i);
    expect(screen.queryByLabelText(/^new password$/i)).toBeNull();
  });

  it("shows recovery when sign-in is unconfigured", async () => {
    mockGetClient.mockReturnValue(null);
    renderAt("/reset-password?code=any-code");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/not configured/i);
  });
});
