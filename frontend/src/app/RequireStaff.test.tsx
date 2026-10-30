import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../app/AuthContext";
import { IdentityProvider } from "../app/IdentityContext";
import { RequireStaff } from "./RequireStaff";
import type { Identity } from "../types/api";

const EXPORTER_IDENTITY: Identity = {
  user_id: "11111111-1111-1111-1111-111111111111",
  display_name: "Jane Exporter",
  email: "jane@example.test",
  organization_id: "22222222-2222-2222-2222-222222222222",
  organization_name: "Acme Exporters Ltd",
  role: "owner",
  staff_permissions: [],
};

const STAFF_IDENTITY: Identity = {
  ...EXPORTER_IDENTITY,
  display_name: "Alex Regulator",
  email: "alex@example.test",
  staff_permissions: ["grant_manage"],
};

function stubFetchIdentity(identity: Identity) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify(identity), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

function stubFetchReject() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new TypeError("fetch failed");
    }),
  );
}

function renderGuard(
  identity: Identity | null = EXPORTER_IDENTITY,
  token: string | null = "test-token",
) {
  if (identity !== null) {
    stubFetchIdentity(identity);
  } else {
    stubFetchReject();
  }
  return render(
    <MemoryRouter>
      <AuthProvider initial={token ? { token } : {}}>
        <IdentityProvider>
          <RequireStaff>
            <div data-testid="guarded-content">Guarded content</div>
          </RequireStaff>
        </IdentityProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("RequireStaff", () => {
  it("renders the guarded page for an authorized staff identity", async () => {
    renderGuard(STAFF_IDENTITY);
    await waitFor(() =>
      expect(screen.getByTestId("guarded-content")).toHaveTextContent("Guarded content"),
    );
  });

  it("fails closed with an access-denied panel for an ordinary exporter", async () => {
    renderGuard(EXPORTER_IDENTITY);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "This area is restricted" })).toBeInTheDocument(),
    );
    expect(screen.getByText(/Regulatory ingestion administration is limited to authorized staff/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Return to your dashboard/ })).toHaveAttribute("href", "/dashboard");
    expect(screen.queryByTestId("guarded-content")).toBeNull();
  });

  it("does not reveal the guarded page while authorization is unknown or unavailable", async () => {
    renderGuard(null);
    await waitFor(() =>
      expect(screen.getByText(/Checking your access/)).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("guarded-content")).toBeNull();
  });
});
