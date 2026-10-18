import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("./supabaseClient", async (importOriginal) => {
  const original = await importOriginal<typeof import("./supabaseClient")>();
  return {
    ...original,
    getSupabaseClient: vi.fn(),
  };
});

import { getSupabaseClient } from "./supabaseClient";

const mockGetClient = vi.mocked(getSupabaseClient);

interface MockAuth {
  getSession: ReturnType<typeof vi.fn>;
  onAuthStateChange: ReturnType<typeof vi.fn>;
  signInWithOtp: ReturnType<typeof vi.fn>;
  signInWithPassword: ReturnType<typeof vi.fn>;
  resetPasswordForEmail: ReturnType<typeof vi.fn>;
  updateUser: ReturnType<typeof vi.fn>;
  signOut: ReturnType<typeof vi.fn>;
  unsubscribe: ReturnType<typeof vi.fn>;
  listener: ((event: string, session: unknown) => void) | null;
}

function mockClient(session: unknown = null): { client: unknown; auth: MockAuth } {
  const auth: MockAuth = {
    getSession: vi.fn().mockResolvedValue({ data: { session } }),
    onAuthStateChange: vi.fn(),
    signInWithOtp: vi.fn().mockResolvedValue({ error: null }),
    signInWithPassword: vi.fn().mockResolvedValue({
      data: { session: null },
      error: null,
    }),
    resetPasswordForEmail: vi.fn().mockResolvedValue({ error: null }),
    updateUser: vi.fn().mockResolvedValue({ error: null }),
    signOut: vi.fn().mockResolvedValue({ error: null }),
    unsubscribe: vi.fn(),
    listener: null,
  };
  auth.onAuthStateChange.mockImplementation((listener: MockAuth["listener"]) => {
    auth.listener = listener;
    return { data: { subscription: { unsubscribe: auth.unsubscribe } } };
  });
  return { client: { auth }, auth };
}

function probe(initial?: { token?: string | null; devTenantId?: string | null }) {
  let current: ReturnType<typeof useAuth> | null = null;
  function Probe() {
    current = useAuth();
    return null;
  }
  render(
    <AuthProvider initial={initial}>
      <Probe />
    </AuthProvider>,
  );
  return () => {
    if (!current) {
      throw new Error("auth probe unavailable");
    }
    return current;
  };
}

afterEach(() => {
  vi.clearAllMocks();
  mockGetClient.mockReturnValue(null);
});

describe("AuthProvider without Supabase configuration", () => {
  it("keeps the existing manual session behavior", () => {
    mockGetClient.mockReturnValue(null);
    const auth = probe({ token: "test-token" });
    expect(auth().isConfigured).toBe(true);
    expect(auth().initializing).toBe(false);
    expect(auth().supabaseConfigured).toBe(false);
    act(() => {
      auth().clear();
    });
    expect(auth().isConfigured).toBe(false);
  });

  it("signOut clears local state without a client", async () => {
    mockGetClient.mockReturnValue(null);
    const auth = probe({ token: "test-token" });
    await act(async () => {
      await auth().signOut();
    });
    expect(auth().isConfigured).toBe(false);
  });
});

describe("AuthProvider with a Supabase client", () => {
  it("restores the session on startup and subscribes exactly once", async () => {
    const { client, auth } = mockClient({
      access_token: "restored-token",
      user: { email: "owner@example.com" },
    });
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    expect(state().initializing).toBe(true);
    await waitFor(() => {
      expect(state().isConfigured).toBe(true);
    });
    expect(state().initializing).toBe(false);
    expect(state().userEmail).toBe("owner@example.com");
    expect(auth.onAuthStateChange).toHaveBeenCalledTimes(1);
  });

  it("follows sign-in, refresh, and sign-out events without duplicates", async () => {
    const { client, auth } = mockClient(null);
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    await waitFor(() => {
      expect(state().initializing).toBe(false);
    });
    expect(state().isConfigured).toBe(false);
    act(() => {
      auth.listener?.("SIGNED_IN", {
        access_token: "fresh-token",
        user: { email: "owner@example.com" },
      });
    });
    expect(state().isConfigured).toBe(true);
    act(() => {
      auth.listener?.("TOKEN_REFRESHED", {
        access_token: "rotated-token",
        user: { email: "owner@example.com" },
      });
    });
    expect(state().isConfigured).toBe(true);
    act(() => {
      auth.listener?.("SIGNED_OUT", null);
    });
    expect(state().isConfigured).toBe(false);
    expect(state().userEmail).toBeNull();
    expect(auth.onAuthStateChange).toHaveBeenCalledTimes(1);
  });

  it("unsubscribes on unmount", async () => {
    const { client, auth } = mockClient(null);
    mockGetClient.mockReturnValue(client as never);
    const { unmount } = render(<AuthProvider>{null}</AuthProvider>);
    await waitFor(() => {
      expect(auth.onAuthStateChange).toHaveBeenCalledTimes(1);
    });
    unmount();
    expect(auth.unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("requests magic links and reports failures generically", async () => {
    const { client, auth } = mockClient(null);
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    await waitFor(() => {
      expect(state().initializing).toBe(false);
    });
    let result: { sent: boolean; errorMessage: string | null } = {
      sent: false,
      errorMessage: "unset",
    };
    await act(async () => {
      result = await state().signInWithEmail("owner@example.com");
    });
    expect(result.sent).toBe(true);
    expect(auth.signInWithOtp).toHaveBeenCalledTimes(1);
    const call = auth.signInWithOtp.mock.calls[0][0] as {
      email: string;
      options: Record<string, unknown>;
    };
    expect(call.email).toBe("owner@example.com");
    expect(call.options["shouldCreateUser"]).toBe(false);
    expect(String(call.options["emailRedirectTo"])).toMatch(/\/auth\/callback$/);

    auth.signInWithOtp.mockResolvedValueOnce({ error: { message: "User not found" } });
    await act(async () => {
      result = await state().signInWithEmail("unknown@example.com");
    });
    expect(result.sent).toBe(false);
    // Generic message: no account-existence oracle, no provider text.
    expect(result.errorMessage).not.toMatch(/not found/i);
    expect(result.errorMessage).toBeTruthy();
  });

  it("signs out through the client and stays cleared on remote failure", async () => {
    const { client, auth } = mockClient({
      access_token: "live-token",
      user: { email: "owner@example.com" },
    });
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    await waitFor(() => {
      expect(state().isConfigured).toBe(true);
    });
    await act(async () => {
      await state().signOut();
    });
    expect(auth.signOut).toHaveBeenCalledTimes(1);
    expect(state().isConfigured).toBe(false);

    auth.signOut.mockRejectedValueOnce(new Error("network down"));
    await act(async () => {
      await state().signOut();
    });
    expect(state().isConfigured).toBe(false);
  });

  it("signs in with email and password and adopts the returned session", async () => {
    const { client, auth } = mockClient(null);
    auth.signInWithPassword.mockResolvedValueOnce({
      data: {
        session: {
          access_token: "password-token",
          user: { email: "owner@example.com" },
        },
      },
      error: null,
    });
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    await waitFor(() => {
      expect(state().initializing).toBe(false);
    });
    let result: { ok: boolean; errorMessage: string | null } = {
      ok: false,
      errorMessage: "unset",
    };
    await act(async () => {
      result = await state().signInWithPassword(
        "owner@example.com",
        "secret-password",
      );
    });
    expect(result.ok).toBe(true);
    expect(state().isConfigured).toBe(true);
    expect(state().userEmail).toBe("owner@example.com");
    expect(auth.signInWithPassword).toHaveBeenCalledWith({
      email: "owner@example.com",
      password: "secret-password",
    });
    // Password sign-in never creates accounts.
    expect((auth as unknown as Record<string, unknown>)["signUp"]).toBeUndefined();
  });

  it("keeps password failures generic and leaves the session unset", async () => {
    const { client, auth } = mockClient(null);
    auth.signInWithPassword.mockResolvedValueOnce({
      data: { session: null },
      error: { message: "Invalid login credentials" },
    });
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    await waitFor(() => {
      expect(state().initializing).toBe(false);
    });
    let result: { ok: boolean; errorMessage: string | null } = {
      ok: true,
      errorMessage: null,
    };
    await act(async () => {
      result = await state().signInWithPassword("owner@example.com", "wrong");
    });
    expect(result.ok).toBe(false);
    // Generic message: no account-existence oracle, no provider text.
    expect(result.errorMessage).not.toMatch(/invalid login credentials/i);
    expect(result.errorMessage).toBeTruthy();
    expect(state().isConfigured).toBe(false);
  });

  it("requests a password reset through the recovery destination", async () => {
    const { client, auth } = mockClient(null);
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    await waitFor(() => {
      expect(state().initializing).toBe(false);
    });
    let result: { sent: boolean; errorMessage: string | null } = {
      sent: false,
      errorMessage: "unset",
    };
    await act(async () => {
      result = await state().requestPasswordReset("owner@example.com");
    });
    expect(result.sent).toBe(true);
    const call = auth.resetPasswordForEmail.mock.calls[0];
    expect(call[0]).toBe("owner@example.com");
    expect(String((call[1] as { redirectTo: string }).redirectTo)).toMatch(
      /\/reset-password$/,
    );

    auth.resetPasswordForEmail.mockResolvedValueOnce({
      error: { message: "rate limited" },
    });
    await act(async () => {
      result = await state().requestPasswordReset("owner@example.com");
    });
    expect(result.sent).toBe(false);
    expect(result.errorMessage).not.toMatch(/rate limited/i);
  });

  it("sets a new password for the current recovery session", async () => {
    const { client, auth } = mockClient(null);
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    await waitFor(() => {
      expect(state().initializing).toBe(false);
    });
    let result: { ok: boolean; errorMessage: string | null } = {
      ok: false,
      errorMessage: "unset",
    };
    await act(async () => {
      result = await state().updatePassword("brand-new-password");
    });
    expect(result.ok).toBe(true);
    expect(auth.updateUser).toHaveBeenCalledWith({
      password: "brand-new-password",
    });
  });

  it("does not restore a session after sign-out", async () => {
    const { client, auth } = mockClient({
      access_token: "live-token",
      user: { email: "owner@example.com" },
    });
    mockGetClient.mockReturnValue(client as never);
    const state = probe();
    await waitFor(() => {
      expect(state().isConfigured).toBe(true);
    });
    await act(async () => {
      await state().signOut();
    });
    expect(auth.signOut).toHaveBeenCalledTimes(1);
    expect(state().isConfigured).toBe(false);
    // The shared client now reports no session; a fresh provider
    // (as on the next load) stays signed out.
    auth.getSession.mockResolvedValue({ data: { session: null } });
    const freshState = probe();
    await waitFor(() => {
      expect(freshState().initializing).toBe(false);
    });
    expect(freshState().isConfigured).toBe(false);
  });

  it("never exposes tokens in rendered output", async () => {
    const { client } = mockClient({
      access_token: "super-secret-access-token-value",
      user: { email: "owner@example.com" },
    });
    mockGetClient.mockReturnValue(client as never);
    function TokenProbe(): ReactNode {
      const auth = useAuth();
      return <span>{auth.isConfigured ? "yes" : "no"}</span>;
    }
    render(
      <AuthProvider>
        <TokenProbe />
      </AuthProvider>,
    );
    await screen.findByText("yes");
    expect(document.body.textContent).not.toMatch(/super-secret-access-token-value/);
  });
});
