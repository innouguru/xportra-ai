import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./AuthContext";
import { RequireAuth } from "./RequireAuth";

vi.mock("./supabaseClient", async (importOriginal) => {
  const original = await importOriginal<typeof import("./supabaseClient")>();
  return {
    ...original,
    getSupabaseClient: vi.fn().mockReturnValue(null),
  };
});

function renderAt(path: string, initial?: { token?: string | null; devTenantId?: string | null }) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={initial}>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <div>Protected content</div>
              </RequireAuth>
            }
          />
          <Route path="/session" element={<div>Session screen</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("RequireAuth", () => {
  it("renders protected content for configured sessions", () => {
    renderAt("/dashboard", { token: "test-token" });
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("accepts the development tenant mechanism where configured", () => {
    renderAt("/dashboard", { devTenantId: "22222222-2222-2222-2222-222222222222" });
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("redirects unauthenticated visitors to sign in", () => {
    renderAt("/dashboard");
    expect(screen.getByText("Session screen")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).toBeNull();
  });
});
