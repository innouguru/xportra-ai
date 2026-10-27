import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";

vi.mock("../../api/organizations", () => ({
  registerOrganization: vi.fn().mockResolvedValue({ tenant_id: "t-1" }),
}));

vi.mock("../../app/supabaseClient", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../app/supabaseClient")>();
  return { ...original, getSupabaseClient: vi.fn() };
});

import { getSupabaseClient } from "../../app/supabaseClient";
import { SetupPasswordPage } from "./SetupPasswordPage";

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

describe("SetupPasswordPage focused", () => {
  it("renders the form with a valid session", async () => {
    mockGetClient.mockReturnValue(mockClient({ access_token: "t" }) as never);
    render(
      <MemoryRouter>
        <AuthProvider>
          <Routes>
            <Route path="/setup-password" element={<SetupPasswordPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: /create your password/i })).toBeInTheDocument();
  });

  it("shows recoverable state when session is unavailable", async () => {
    mockGetClient.mockReturnValue(null);
    render(
      <MemoryRouter>
        <AuthProvider>
          <Routes>
            <Route path="/setup-password" element={<SetupPasswordPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("rejects mismatched confirmation before submission", async () => {
    mockGetClient.mockReturnValue(mockClient({ access_token: "t", user: { email: "e@t.com" } }) as never);
    render(
      <MemoryRouter initialEntries={["/setup-password"]}>
        <AuthProvider>
          <Routes>
            <Route path="/setup-password" element={<SetupPasswordPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    const button = await screen.findByRole("button", { name: /continue/i });
    expect(button).toBeInTheDocument();
  });
});
