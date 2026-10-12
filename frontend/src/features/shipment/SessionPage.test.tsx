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

describe("SessionPage magic-link sign-in", () => {
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
    expect(document.body.textContent).not.toMatch(/token|secret|password/i);
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
});
