import { afterEach, describe, expect, it } from "vitest";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider, useAuth } from "../app/AuthContext";
import { ThemeProvider } from "../theme/theme";
import { AuthenticatedShell } from "./AuthenticatedShell";

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

function renderShell(path = "/dashboard", token: string | null = "test-token") {
  stubMatchMedia(false);
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={token ? { token } : {}}>
        <ThemeProvider>
          <AuthenticatedShell crumbs={[{ label: "Shell test" }]}>
            <p>Page body</p>
          </AuthenticatedShell>
        </ThemeProvider>
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
        <ThemeProvider>
          <AuthenticatedShell crumbs={[{ label: "Shell test" }]}>
            <Probe />
          </AuthenticatedShell>
        </ThemeProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
  return () => configured;
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("authenticated shell navigation", () => {
  it("shows exactly Dashboard and View Shipments as primary navigation", () => {
    renderShell();
    const primary = screen.getByRole("navigation", { name: "Primary" });
    expect(within(primary).getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
    expect(within(primary).getByRole("link", { name: "View Shipments" })).toHaveAttribute("href", "/shipments");
    const links = within(primary).getAllByRole("link");
    expect(links).toHaveLength(2);
  });

  it("does not expose workflow concepts as primary navigation", () => {
    renderShell();
    for (const name of ["Documents", "Requirements", "Evidence", "Assessment", "RAG", "API"]) {
      expect(screen.queryByRole("link", { name })).toBeNull();
    }
  });

  it("communicates the active destination with aria-current", () => {
    renderShell("/shipments");
    expect(screen.getByRole("link", { name: "View Shipments" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });

  it("renders the breadcrumb trail and page body", () => {
    renderShell();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Shell test");
    expect(screen.getByText("Page body")).toBeInTheDocument();
  });
});

describe("sidebar collapse", () => {
  it("collapses and expands with accessible labels intact", () => {
    renderShell();
    const sidebar = screen.getByRole("complementary", { name: "Application" });
    expect(sidebar.className).not.toMatch(/xb-sidebar--collapsed/);

    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(toggle);

    expect(sidebar.className).toMatch(/xb-sidebar--collapsed/);
    // Labels stay accessible names when collapsed.
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Shipments" })).toBeInTheDocument();
    expect(window.localStorage.getItem("xportra.shell.sidebar.v1")).toBe("collapsed");

    fireEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(sidebar.className).not.toMatch(/xb-sidebar--collapsed/);
  });

  it("starts collapsed on smaller desktop widths", () => {
    stubMatchMedia(true);
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider initial={{ token: "test-token" }}>
          <ThemeProvider>
            <AuthenticatedShell crumbs={[{ label: "Shell test" }]}>
              <p>Page body</p>
            </AuthenticatedShell>
          </ThemeProvider>
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

describe("account menu", () => {
  function openMenu() {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    return screen.getByRole("menu", { name: "Account" });
  }

  it("exposes Profile, Organization, Settings, and Sign out", () => {
    const menu = openMenu();
    expect(within(menu).getByRole("menuitem", { name: /Profile/ })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: /Organization/ })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(within(menu).getByRole("menuitem", { name: "Sign out" })).toBeInTheDocument();
  });

  it("signs out through the existing auth boundary", () => {
    const menu = openMenu();
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

  it("closes when a destination is chosen", () => {
    openDrawer();
    const dialog = screen.getByRole("dialog", { name: "Application navigation" });
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
