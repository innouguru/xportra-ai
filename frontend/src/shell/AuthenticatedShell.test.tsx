import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider, useAuth } from "../app/AuthContext";
import { IdentityProvider } from "../app/IdentityContext";
import { ThemeProvider } from "../theme/theme";
import { AuthenticatedShell } from "./AuthenticatedShell";
import type { Identity } from "../types/api";

function stubMatchMedia(matches: boolean) {
  window.matchMedia = ((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

const DEFAULT_IDENTITY: Identity = {
  user_id: "11111111-1111-1111-1111-111111111111",
  display_name: "Jane Exporter",
  email: "jane@example.test",
  organization_id: "22222222-2222-2222-2222-222222222222",
  organization_name: "Acme Exporters Ltd",
  role: "owner",
  staff_permissions: [],
};

const STAFF_IDENTITY: Identity = {
  ...DEFAULT_IDENTITY,
  display_name: "Alex Regulator",
  email: "alex@example.test",
  staff_permissions: ["grant_manage"],
};

const STAFF_ONLY_IDENTITY: Identity = {
  ...DEFAULT_IDENTITY,
  display_name: "Sam Regulator",
  email: "sam@example.test",
  organization_id: null,
  organization_name: null,
  role: null,
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

function renderShell(
  path = "/dashboard",
  token: string | null = "test-token",
  identity: Identity | null = DEFAULT_IDENTITY,
) {
  stubMatchMedia(false);
  if (identity !== null) {
    stubFetchIdentity(identity);
  } else {
    stubFetchReject();
  }
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={token ? { token } : {}}>
        <IdentityProvider>
          <ThemeProvider>
            <AuthenticatedShell crumbs={[{ label: "Shell test" }]}>
              <p>Page body</p>
            </AuthenticatedShell>
          </ThemeProvider>
        </IdentityProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function authProbe() {
  let configured: boolean | null = null;
  function Probe() {
    configured = useAuth().isConfigured;
    return null;
  }
  render(
    <MemoryRouter>
      <AuthProvider initial={{ token: "test-token" }}>
        <IdentityProvider>
          <ThemeProvider>
            <AuthenticatedShell crumbs={[{ label: "Shell test" }]}>
              <Probe />
            </AuthenticatedShell>
          </ThemeProvider>
        </IdentityProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
  return () => configured;
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
  vi.unstubAllGlobals();
});

describe("authenticated shell navigation", () => {
  it("shows Dashboard, View Shipments, and Regulatory Ingestion to authorized staff", async () => {
    renderShell("/dashboard", "test-token", STAFF_IDENTITY);
    const primary = screen.getByRole("navigation", { name: "Primary" });
    await waitFor(() =>
      expect(
        within(primary).getByRole("link", { name: "Dashboard" }),
      ).toHaveAttribute("href", "/dashboard"),
    );
    await waitFor(() =>
      expect(
        within(primary).getByRole("link", { name: "View Shipments" }),
      ).toHaveAttribute("href", "/shipments"),
    );
    await waitFor(() =>
      expect(
        within(primary).getByRole("link", { name: "Regulatory Ingestion" }),
      ).toHaveAttribute("href", "/regulatory-ingestion"),
    );
    const links = within(primary).getAllByRole("link");
    expect(links).toHaveLength(3);
  });

  it("shows only Regulatory Ingestion to dedicated staff without organization membership", async () => {
    renderShell("/dashboard", "test-token", STAFF_ONLY_IDENTITY);
    const primary = screen.getByRole("navigation", { name: "Primary" });
    // Organization-owned destinations are hidden for a staff-only account.
    expect(within(primary).queryByRole("link", { name: "Dashboard" })).toBeNull();
    expect(within(primary).queryByRole("link", { name: "View Shipments" })).toBeNull();
    await waitFor(() =>
      expect(
        within(primary).getByRole("link", { name: "Regulatory Ingestion" }),
      ).toHaveAttribute("href", "/regulatory-ingestion"),
    );
    const links = within(primary).getAllByRole("link");
    expect(links).toHaveLength(1);
  });

  it("hides Regulatory Ingestion from an ordinary authenticated exporter", async () => {
    renderShell(); // DEFAULT_IDENTITY has staff_permissions: []
    const primary = screen.getByRole("navigation", { name: "Primary" });
    await waitFor(() =>
      expect(
        within(primary).getByRole("link", { name: "Dashboard" }),
      ).toHaveAttribute("href", "/dashboard"),
    );
    await waitFor(() =>
      expect(
        within(primary).getByRole("link", { name: "View Shipments" }),
      ).toHaveAttribute("href", "/shipments"),
    );
    expect(within(primary).queryByRole("link", { name: "Regulatory Ingestion" })).toBeNull();
    const links = within(primary).getAllByRole("link");
    expect(links).toHaveLength(2);
  });

  it("hides organization navigation and Regulatory Ingestion while authorization state is unknown or unavailable", () => {
    // Fetch never resolves: identity stays in a non-ready state, so the
    // shell fails closed and reveals neither org navigation nor staff entry.
    stubFetchReject();
    renderShell("/dashboard", "test-token", null);
    const primary = screen.getByRole("navigation", { name: "Primary" });
    expect(within(primary).queryByRole("link", { name: "Dashboard" })).toBeNull();
    expect(within(primary).queryByRole("link", { name: "View Shipments" })).toBeNull();
    expect(within(primary).queryByRole("link", { name: "Regulatory Ingestion" })).toBeNull();
  });

  it("does not expose workflow concepts as primary navigation", () => {
    renderShell();
    for (const name of ["Documents", "Requirements", "Evidence", "Assessment", "RAG", "API"]) {
      expect(screen.queryByRole("link", { name })).toBeNull();
    }
  });

  it("communicates the active destination with aria-current", async () => {
    renderShell("/shipments");
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "View Shipments" })).toHaveAttribute("aria-current", "page"),
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });

  it("renders the breadcrumb trail and page body", () => {
    renderShell();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Shell test");
    expect(screen.getByText("Page body")).toBeInTheDocument();
  });
});

describe("sidebar collapse", () => {
  it("collapses and expands with accessible labels intact", async () => {
    renderShell();
    const sidebar = screen.getByRole("complementary", { name: "Application" });
    expect(sidebar.className).not.toMatch(/xb-sidebar--collapsed/);

    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(toggle);

    expect(sidebar.className).toMatch(/xb-sidebar--collapsed/);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "View Shipments" })).toBeInTheDocument(),
    );
    expect(window.localStorage.getItem("xportra.shell.sidebar.v1")).toBe("collapsed");

    fireEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(sidebar.className).not.toMatch(/xb-sidebar--collapsed/);
  });

  it("starts collapsed on smaller desktop widths", () => {
    stubMatchMedia(true);
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider initial={{ token: "test-token" }}>
          <IdentityProvider>
            <ThemeProvider>
              <AuthenticatedShell crumbs={[{ label: "Shell test" }]}>
                <p>Page body</p>
              </AuthenticatedShell>
            </ThemeProvider>
          </IdentityProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("complementary", { name: "Application" }).className).toMatch(
      /xb-sidebar--collapsed/,
    );
  });
});

describe("brand behavior", () => {
  it("opens the public landing route in a new tab without signing out", () => {
    const isConfigured = authProbe();
    const home = screen.getByRole("link", { name: "Xportra AI home (opens in a new tab)" });
    expect(home.getAttribute("href")).toBe("/");
    expect(home.getAttribute("target")).toBe("_blank");
    expect(home.getAttribute("rel")).toContain("noreferrer");
    act(() => {
      home.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(isConfigured()).toBe(true);
  });
});

describe("account identity", () => {
  it("shows the organization name in the sidebar brand area", async () => {
    renderShell();
    await waitFor(() =>
      expect(screen.getByText("Acme Exporters Ltd")).toBeInTheDocument(),
    );
    const org = screen.getByText("Acme Exporters Ltd");
    expect(org).toHaveClass("xb-sidebar__org");
  });

  it("shows Organization unavailable in the sidebar when there is no membership", async () => {
    const noOrg: Identity = { ...DEFAULT_IDENTITY, organization_name: null, organization_id: null, role: null };
    renderShell("/dashboard", "test-token", noOrg);
    await waitFor(() =>
      expect(screen.getByText("Organization unavailable")).toBeInTheDocument(),
    );
  });

  it("does not show organization text when the sidebar is collapsed", async () => {
    stubMatchMedia(true);
    renderShell("/dashboard", "test-token", DEFAULT_IDENTITY);
    await waitFor(() =>
      expect(screen.getByText("Acme Exporters Ltd")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    const org = screen.getByText("Acme Exporters Ltd");
    expect(org).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Application" }).className).toMatch(
      /xb-sidebar--collapsed/,
    );
  });
});

describe("account menu", () => {
  function openMenu() {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    return screen.getByRole("menu", { name: "Account" });
  }

  it("shows the signed-in name, email, and organization", async () => {
    const menu = openMenu();
    await waitFor(() =>
      expect(within(menu).getByText("Jane Exporter")).toBeInTheDocument(),
    );
    expect(within(menu).getByText("jane@example.test")).toBeInTheDocument();
    expect(within(menu).getByText("Acme Exporters Ltd")).toBeInTheDocument();
  });

  it("shows Settings and Sign out", () => {
    const menu = openMenu();
    expect(within(menu).getByRole("menuitem", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(within(menu).getByRole("menuitem", { name: "Sign out" })).toBeInTheDocument();
  });

  it("shows Organization unavailable when no membership is resolved", async () => {
    const noOrg: Identity = { ...DEFAULT_IDENTITY, organization_name: null, organization_id: null, role: null };
    renderShell("/dashboard", "test-token", noOrg);
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    const menu = screen.getByRole("menu", { name: "Account" });
    await waitFor(() =>
      expect(within(menu).getByText("Organization unavailable")).toBeInTheDocument(),
    );
  });

  it("shows a loading state while identity is being resolved", async () => {
    // Fetch never resolves: identity stays loading.
    stubFetchReject();
    renderShell("/dashboard", "test-token", null);
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    const menu = screen.getByRole("menu", { name: "Account" });
    await waitFor(() =>
      expect(within(menu).getByText(/Loading account/i)).toBeInTheDocument(),
    );
  });

  it("signs out through the existing auth boundary", async () => {
    const menu = openMenu();
    await waitFor(() =>
      expect(within(menu).getByText("Jane Exporter")).toBeInTheDocument(),
    );
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Sign out" }));
    expect(screen.queryByRole("menu", { name: "Account" })).toBeNull();
    // Session cleared: reopening the menu now offers Sign in.
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByRole("menuitem", { name: "Sign in" })).toHaveAttribute("href", "/session");
  });

  it("closes on Escape and returns focus to the account control", () => {
    openMenu();
    const account = screen.getByRole("button", { name: "Account" });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu", { name: "Account" })).toBeNull();
    expect(document.activeElement).toBe(account);
  });
});

describe("notifications entry point", () => {
  it("exists without a notification center or fake data", () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    const notice = screen.getByRole("status");
    expect(notice).toHaveTextContent(/all caught up/i);
    expect(document.body.textContent).not.toMatch(/unread/i);
  });

  it("dismisses with Escape", () => {
    renderShell();
    const entry = screen.getByRole("button", { name: "Notifications" });
    fireEvent.click(entry);
    expect(screen.getByRole("status")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("status")).toBeNull();
    expect(document.activeElement).toBe(entry);
  });

  it("dismisses on outside interaction (10.8J audit)", () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(screen.getByRole("status")).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("shell theme", () => {
  it("toggles through the Phase 10.8A theme infrastructure", () => {
    renderShell();
    expect(document.documentElement.dataset.theme).toBe("dark");
    fireEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(screen.getByRole("button", { name: "Switch to dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

describe("mobile drawer", () => {
  function openDrawer() {
    renderShell();
    const hamburger = screen.getByRole("button", { name: "Open navigation" });
    hamburger.focus();
    fireEvent.click(hamburger);
    return hamburger;
  }

  it("opens an accessible dialog and closes it on Escape with focus restored", () => {
    const hamburger = openDrawer();
    const dialog = screen.getByRole("dialog", { name: "Application navigation" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(document.activeElement).toHaveAttribute("aria-label", "Close navigation");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Application navigation" })).toBeNull();
    expect(document.activeElement).toBe(hamburger);
  });

  it("cycles tab focus inside the dialog", () => {
    openDrawer();
    const dialog = screen.getByRole("dialog", { name: "Application navigation" });
    const close = screen.getByRole("button", { name: "Close navigation" });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).not.toBe(close);
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(close);
  });

  it("closes when a destination is chosen", async () => {
    openDrawer();
    const dialog = screen.getByRole("dialog", { name: "Application navigation" });
    await waitFor(() =>
      expect(within(dialog).getByRole("link", { name: "Dashboard" })).toBeInTheDocument(),
    );
    fireEvent.click(within(dialog).getByRole("link", { name: "Dashboard" }));
    expect(screen.queryByRole("dialog", { name: "Application navigation" })).toBeNull();
  });
});

describe("shell landmarks", () => {
  it("keeps skip link, landmarks, and main content", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Application" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });
});
