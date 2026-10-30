import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { App } from "../App";

const STALE_RECORD = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "evidence_pending",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

const STAFF_ME = {
  user_id: "11111111-1111-1111-1111-111111111111",
  display_name: "Alex Regulator",
  email: "alex@example.test",
  organization_id: "22222222-2222-2222-2222-222222222222",
  organization_name: "Acme Exporters Ltd",
  role: "owner",
  staff_permissions: ["grant_manage"],
};

const EXPORTER_ME = {
  ...STAFF_ME,
  display_name: "Jane Exporter",
  email: "jane@example.test",
  staff_permissions: [],
};

function CurrentRoute() {
  return <output aria-label="Current route">{useLocation().pathname}</output>;
}

/**
 * Phase 10.8B route smoke tests, extended by Phase 10.10.
 *
 * The authenticated shell serves the dashboard and
 * shipment-list routes; the public landing route
 * stays outside the shell. Phase 10.10 gates the
 * workspace routes behind `RequireAuth`: visitors
 * without a session land on the sign-in surface
 * instead of workspace content. Full page behavior
 * belongs to later 10.8 phases.
 */

/**
 * Stub fetch so ``GET /me`` returns the supplied identity while every
 * other backend call is denied server-side. This keeps tests honest
 * about which requests a page really makes and mirrors the established
 * regulatory-backend stubbing pattern.
 */
function stubFetch(meResponse: Response) {
  return vi.fn(async (input: string | Request): Promise<Response> => {
    const url = typeof input === "string" ? input : input.url;
    if (url.endsWith("/me")) {
      return meResponse;
    }
    return new Response(
      JSON.stringify({ error: { code: "permission_denied", message: "Permission denied." } }),
      { status: 403, headers: { "Content-Type": "application/json" } },
    );
  });
}

function renderAt(path: string, authInitial?: { token: string }, me?: unknown) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
  vi.stubGlobal(
    "fetch",
    stubFetch(
      me !== undefined
        ? new Response(JSON.stringify(me), { status: 200, headers: { "Content-Type": "application/json" } })
        : new Response(
            JSON.stringify({ error: { code: "permission_denied", message: "Permission denied." } }),
            { status: 403, headers: { "Content-Type": "application/json" } },
          ),
    ),
  );
  render(
    <MemoryRouter initialEntries={[path]}>
      <App authInitial={authInitial} />
      <CurrentRoute />
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
  vi.unstubAllGlobals();
});

describe("authenticated routes", () => {
  it("serves the staff ingestion dashboard inside the application shell for signed-in users", () => {
    // The dashboard calls the staff regulatory API; authorization is
    // enforced server-side, so a denial is expected here and the shell
    // chrome must still render for a signed-in visitor. ``GET /me``
    // fails, so the staff entry point stays hidden; only the shell
    // chrome and breadcrumb are asserted.
    renderAt("/regulatory-ingestion", { token: "test-token" });
    expect(screen.getByRole("complementary", { name: "Application" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent(
      "Regulatory ingestion",
    );
  });

  it("resolves the Regulatory Ingestion navigation item to the dashboard route", async () => {
    renderAt("/dashboard", { token: "test-token" }, STAFF_ME);
    // Wait for the server-resolved identity to grant staff access before
    // the navigation item is rendered.
    await waitFor(() => {
      expect(
        screen.getByRole("navigation", { name: "Primary" }).querySelector(
          'a[href="/regulatory-ingestion"]',
        ),
      ).not.toBeNull();
    });
    fireEvent.click(
      screen.getByRole("navigation", { name: "Primary" }).querySelector(
        'a[href="/regulatory-ingestion"]',
      ) as HTMLAnchorElement,
    );
    await waitFor(() => {
      expect(screen.getByText("Regulatory administration")).toBeInTheDocument();
    });
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent(
      "Regulatory ingestion",
    );
  });

  it("serves the dashboard inside the application shell for signed-in users", () => {
    renderAt("/dashboard", { token: "test-token" });
    expect(screen.getByRole("complementary", { name: "Application" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Your shipments", level: 1 })).toBeInTheDocument();
  });

  it("serves the shipment list inside the application shell for signed-in users", () => {
    renderAt("/shipments", { token: "test-token" });
    expect(screen.getByRole("complementary", { name: "Application" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("View Shipments");
  });

  it("directs signed-out visitors to sign in instead of workspace content", () => {
    renderAt("/dashboard");
    expect(screen.getByText("Connect to your workspace")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Your shipments" })).toBeNull();
    expect(screen.queryByRole("complementary", { name: "Application" })).toBeNull();
  });

  it("keeps the public landing page outside the application shell", () => {
    renderAt("/");
    expect(screen.queryByRole("complementary", { name: "Application" })).toBeNull();
    expect(screen.queryByText("No active shipment")).toBeNull();
  });

  it.each(["/register", "/session", "/auth/callback", "/reset-password"])(
    "%s uses public authentication chrome without shipment UI",
    (path) => {
      renderAt(path);
      expect(screen.queryByText("No active shipment")).toBeNull();
      expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
      expect(screen.queryByRole("complementary", { name: "Application" })).toBeNull();
      if (path === "/register") {
        expect(screen.getByRole("heading", { name: "Create your organization" })).toBeInTheDocument();
        expect(screen.getByLabelText("Organization name")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/session");
      }
      if (path === "/session") {
        expect(screen.getByRole("heading", { name: "Connect to your workspace" })).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Sign-in method" })).toBeInTheDocument();
        expect(screen.getByLabelText("Email address")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /create an account/i })).toHaveAttribute("href", "/register");
        fireEvent.click(screen.getByRole("button", { name: /^password$/i }));
        expect(screen.getByRole("link", { name: /forgot password/i })).toHaveAttribute("href", "/reset-password");
      }
      if (path === "/reset-password") {
        expect(screen.getByRole("heading", { name: "Reset your password" })).toBeInTheDocument();
        expect(screen.queryByText("Connect to your workspace")).toBeNull();
      }
    },
  );

  it.each(["/start", "/settings", "/regulatory-ingestion"])(
    "protects %s from signed-out visitors",
    (path) => {
    renderAt(path);
    expect(screen.getByRole("heading", { name: "Connect to your workspace" })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Application" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "New shipment" })).toBeNull();
  });

  it("denies an unauthorized exporter direct access to /regulatory-ingestion", async () => {
    renderAt("/regulatory-ingestion", { token: "test-token" }, EXPORTER_ME);
    // The shell chrome renders, but the staff guard fails closed with an
    // in-place access-denied panel once the exporter identity resolves.
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "This area is restricted" })).toBeInTheDocument(),
    );
    expect(screen.getByText(/Regulatory ingestion administration is limited to authorized staff/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Return to your dashboard/ })).toHaveAttribute("href", "/dashboard");
    expect(screen.queryByRole("heading", { name: "Your shipments" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Regulatory ingestion" })).toBeNull();
  });

  it("does not render workspace navigation for a signed-out visitor with a stale record", async () => {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(STALE_RECORD));
    renderAt("/session");
    expect(screen.getByText("Connect to your workspace")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
    expect(screen.queryByText("No active shipment")).toBeNull();
    expect(screen.queryByRole("link", { name: "Documents" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Assessment" })).toBeNull();
    // The coordination boundary clears the stale record on sign-out.
    await waitFor(() =>
      expect(sessionStorage.getItem("xportra.workflow-record.v1")).toBeNull(),
    );
  });

  it("still redirects unauthenticated visitors to sign in with a stale record", () => {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(STALE_RECORD));
    renderAt("/dashboard");
    expect(screen.getByText("Connect to your workspace")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Your shipments" })).toBeNull();
    expect(screen.queryByRole("complementary", { name: "Application" })).toBeNull();
  });

  it("redirects the unqualified legacy workspace route to the canonical shipment", async () => {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(STALE_RECORD));
    renderAt("/workspace", { token: "test-token" }, EXPORTER_ME);
    expect(await screen.findByRole("heading", { name: "Shipment workspace" })).toBeInTheDocument();
    expect(screen.getByLabelText("Current route")).toHaveTextContent(
      `/shipments/${STALE_RECORD.case_id}`,
    );
    expect(screen.getByRole("navigation", { name: "Primary" })).toHaveTextContent("View Shipments");
    expect(screen.queryByRole("link", { name: "Documents" })).toBeNull();
    expect(sessionStorage.getItem("xportra.workflow-record.v1")).not.toBeNull();
  });

  it("preserves nested legacy workflow routes as compatibility screens", () => {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(STALE_RECORD));
    renderAt("/workspace/info", { token: "test-token" });
    expect(screen.getByRole("navigation", { name: "Shipment sections" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Shipment identity" })).toBeInTheDocument();
  });

  it("ends the session on sign-out and clears session-scoped workspace state", async () => {
    sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(STALE_RECORD));
    renderAt("/workspace", { token: "test-token" }, EXPORTER_ME);
    await waitFor(() =>
      expect(screen.getByRole("navigation", { name: "Primary" })).toHaveTextContent("View Shipments"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
    // Returned to the public sign-in surface, no workspace navigation.
    expect(await screen.findByText("Connect to your workspace")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View Shipments" })).toBeNull();
    // The coordination boundary clears the session-scoped record.
    await waitFor(() =>
      expect(sessionStorage.getItem("xportra.workflow-record.v1")).toBeNull(),
    );
  });
});
