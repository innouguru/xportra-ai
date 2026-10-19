import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { SessionPage } from "./SessionPage";

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
    signInWithOtp: vi.fn().mockResolvedValue({ error: null }),
    signInWithPassword: vi.fn().mockResolvedValue({
      data: {
        session: { access_token: "live-token", user: { email: "owner@example.com" } },
      },
      error: null,
    }),
    resetPasswordForEmail: vi.fn().mockResolvedValue({ error: null }),
    updateUser: vi.fn().mockResolvedValue({ error: null }),
    signOut: vi.fn().mockResolvedValue({ error: null }),
    exchangeCodeForSession: vi.fn(),
  };
  return { client: { auth }, auth };
}

function renderPage(initialPath = "/session") {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <WorkflowProvider>
          <Routes>
            <Route path="/session" element={<SessionPage />} />
            <Route path="/register" element={<div>Create account screen</div>} />
            <Route path="/reset-password" element={<div>Password recovery screen</div>} />
            <Route path="/start" element={<div>Start screen</div>} />
          </Routes>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllEnvs();
  mockGetClient.mockReturnValue(null);
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("SessionPage magic-link sign-in", () => {
  it("keeps sign-in usable while Supabase session restoration is pending", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    auth.getSession.mockReturnValue(new Promise(() => undefined));
    mockGetClient.mockReturnValue(client as never);
    renderPage();
    expect(await screen.findByLabelText(/email address/i)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: /email me a sign-in link/i });
    expect(submit).toBeEnabled();
    await user.type(screen.getByLabelText(/email address/i), "owner@example.com");
    await user.click(submit);
    expect(auth.signInWithOtp).toHaveBeenCalledTimes(1);
  });

  it("shows a recovery action when session restoration fails", async () => {
    const { client, auth } = mockClient();
    auth.getSession.mockRejectedValueOnce(new Error("storage unavailable"));
    mockGetClient.mockReturnValue(client as never);
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(/reload this page or continue by signing in/i);
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reload session/i })).toBeInTheDocument();
  });

  it("validates the email address before submitting", async () => {
    const user = userEvent.setup();
    mockGetClient.mockReturnValue(mockClient().client as never);
    renderPage();
    await screen.findByLabelText(/email address/i);
    await user.type(screen.getByLabelText(/email address/i), "not-an-email");
    await user.click(screen.getByRole("button", { name: /email me a sign-in link/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/valid email/i);
  });

  it("confirms the sent link without revealing account details", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    mockGetClient.mockReturnValue(client as never);
    renderPage();
    await screen.findByLabelText(/email address/i);
    await user.type(screen.getByLabelText(/email address/i), "owner@example.com");
    await user.click(screen.getByRole("button", { name: /email me a sign-in link/i }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      /check owner@example.com/i,
    );
    expect(auth.signInWithOtp).toHaveBeenCalledTimes(1);
    // No credential material leaks; the word "password" is legitimate
    // copy now that the surface also offers password sign-in.
    expect(document.body.textContent).not.toMatch(/bearer|access.?token|secret/i);
  });

  it("prevents duplicate submissions while sending", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    let release!: () => void;
    const gate = new Promise<{ error: null }>((resolve) => {
      release = () => resolve({ error: null });
    });
    auth.signInWithOtp.mockReturnValueOnce(gate);
    mockGetClient.mockReturnValue(client as never);
    renderPage();
    await screen.findByLabelText(/email address/i);
    await user.type(screen.getByLabelText(/email address/i), "owner@example.com");
    const button = screen.getByRole("button", { name: /email me a sign-in link/i });
    await user.click(button);
    await user.click(button);
    release();
    await screen.findByRole("status");
    expect(auth.signInWithOtp).toHaveBeenCalledTimes(1);
  });

  it("reports send failures without provider internals", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    auth.signInWithOtp.mockResolvedValueOnce({ error: { message: "boom" } });
    mockGetClient.mockReturnValue(client as never);
    renderPage();
    await screen.findByLabelText(/email address/i);
    await user.type(screen.getByLabelText(/email address/i), "owner@example.com");
    await user.click(screen.getByRole("button", { name: /email me a sign-in link/i }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).not.toMatch(/boom/);
    expect(alert).toHaveTextContent(/could not send/i);
  });

  it("shows a configuration error when Supabase is unconfigured", async () => {
    mockGetClient.mockReturnValue(null);
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(/not configured/i);
    expect(
      screen.getByRole("button", { name: /email me a sign-in link/i }),
    ).toBeDisabled();
  });

  it("offers continue and sign-out when already signed in", async () => {
    const { client } = mockClient({
      access_token: "live-token",
      user: { email: "owner@example.com" },
    });
    mockGetClient.mockReturnValue(client as never);
    renderPage();
    expect(await screen.findByText(/signed in as owner@example.com/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /continue to the workspace/i })).toHaveAttribute(
      "href",
      "/start",
    );
  });

  it("keeps the local-development tenant workflow intact", async () => {
    const user = userEvent.setup();
    mockGetClient.mockReturnValue(null);
    renderPage();
    await screen.findByLabelText(/development tenant id/i);
    await user.type(
      screen.getByLabelText(/development tenant id/i),
      "22222222-2222-2222-2222-222222222222",
    );
    await user.click(screen.getByRole("button", { name: /^connect$/i }));
    await waitFor(() => {
      expect(screen.getByText("Start screen")).toBeInTheDocument();
    });
  });

  it("does not show workspace navigation when a stale record persists without a session", async () => {
    mockGetClient.mockReturnValue(null);
    sessionStorage.setItem(
      "xportra.workflow-record.v1",
      JSON.stringify({
        id: "11111111-1111-1111-1111-111111111111",
        tenant_id: "22222222-2222-2222-2222-222222222222",
        case_id: "33333333-3333-3333-3333-333333333333",
        shipment_id: null,
        state: "evidence_pending",
        rounds: [],
        supplied_evidence_ids: [],
        open_requirements: [],
      }),
    );
    renderPage();
    expect(await screen.findByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
    expect(screen.queryByText("No active shipment")).toBeNull();
    expect(screen.queryByRole("link", { name: "Documents" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Assessment" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Settings" })).toBeNull();
  });
});

describe("SessionPage development gating", () => {
  it("hides the development tenant control outside development builds", async () => {
    vi.stubEnv("DEV", false);
    mockGetClient.mockReturnValue(null);
    renderPage();
    expect(await screen.findByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/development tenant id/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /^connect$/i })).toBeNull();
    // Production copy must not advertise the development mechanism.
    expect(document.body.textContent).not.toMatch(/development/i);
  });

  it("renders the development tenant control in development builds", async () => {
    vi.stubEnv("DEV", true);
    mockGetClient.mockReturnValue(null);
    renderPage();
    expect(await screen.findByLabelText(/development tenant id/i)).toBeInTheDocument();
  });
});

describe("SessionPage password sign-in", () => {
  async function switchToPassword(user: ReturnType<typeof userEvent.setup>) {
    await screen.findByLabelText(/email address/i);
    await user.click(screen.getByRole("button", { name: /^password$/i }));
    return screen.getByLabelText(/^password$/i);
  }

  it("signs in with email and password and continues to the workspace", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    mockGetClient.mockReturnValue(client as never);
    renderPage();
    await switchToPassword(user);
    await user.type(screen.getByLabelText(/email address/i), "owner@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "correct horse battery");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));
    expect(await screen.findByText("Start screen")).toBeInTheDocument();
    expect(auth.signInWithPassword).toHaveBeenCalledWith({
      email: "owner@example.com",
      password: "correct horse battery",
    });
  });

  it("keeps password failures generic", async () => {
    const user = userEvent.setup();
    const { client, auth } = mockClient();
    auth.signInWithPassword.mockResolvedValueOnce({
      data: { session: null },
      error: { message: "Invalid login credentials" },
    });
    mockGetClient.mockReturnValue(client as never);
    renderPage();
    await switchToPassword(user);
    await user.type(screen.getByLabelText(/email address/i), "owner@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).not.toMatch(/invalid login credentials/i);
    expect(alert).toHaveTextContent(/could not sign you in/i);
  });

  it("links to the recovery route rather than submitting reset from sign-in", async () => {
    const user = userEvent.setup();
    mockGetClient.mockReturnValue(mockClient().client as never);
    renderPage();
    await switchToPassword(user);
    await user.click(screen.getByRole("link", { name: /forgot password/i }));
    expect(await screen.findByText("Password recovery screen")).toBeInTheDocument();
  });

  it("offers a direct registration cross-link", async () => {
    const user = userEvent.setup();
    mockGetClient.mockReturnValue(mockClient().client as never);
    renderPage();
    await user.click(await screen.findByRole("link", { name: /create an account/i }));
    expect(await screen.findByText("Create account screen")).toBeInTheDocument();
  });

  it("switches between the email-link and password methods", async () => {
    const user = userEvent.setup();
    mockGetClient.mockReturnValue(mockClient().client as never);
    renderPage();
    await screen.findByLabelText(/email address/i);
    expect(screen.queryByLabelText(/^password$/i)).toBeNull();
    await user.click(screen.getByRole("button", { name: /^password$/i }));
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^sign in$/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /email me a sign-in link/i }),
    ).toBeNull();
    await user.click(screen.getByRole("button", { name: /email link/i }));
    expect(screen.queryByLabelText(/^password$/i)).toBeNull();
    expect(
      screen.getByRole("button", { name: /email me a sign-in link/i }),
    ).toBeInTheDocument();
  });

  it("toggles password visibility", async () => {
    const user = userEvent.setup();
    mockGetClient.mockReturnValue(mockClient().client as never);
    renderPage();
    await switchToPassword(user);
    const input = screen.getByLabelText(/^password$/i);
    expect(input).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: /^show$/i }));
    expect(input).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: /^hide$/i }));
    expect(input).toHaveAttribute("type", "password");
  });
});
