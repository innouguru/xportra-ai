import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../app/AuthContext";
import { WorkflowProvider } from "../app/WorkflowContext";
import { ThemeProvider } from "../theme/theme";
import { AuthenticatedShell } from "./AuthenticatedShell";

/**
 * Phase 10.8I shell integration contract.
 *
 * One theme state, one notification posture
 * (subtle entry, honest empty, nothing
 * persisted), no bottom navigation, and no
 * top-level compliance concepts — across
 * shell entry points.
 */

function stubMatchMedia() {
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
}

function renderShell() {
  stubMatchMedia();
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AuthProvider initial={{ token: "test-token" }}>
        <WorkflowProvider>
          <ThemeProvider>
            <AuthenticatedShell crumbs={[{ label: "Dashboard" }]}>
              <p>Page body</p>
            </AuthenticatedShell>
          </ThemeProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("shell integration", () => {
  it("keeps one theme state across the toggle and the control", () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem("xportra.theme.mode.v1")).toBe("light");
    // Only the theme mode key is persisted — nothing else.
    expect(Object.keys({ ...window.localStorage })).toEqual(["xportra.theme.mode.v1"]);
  });

  it("persists no notification state whatsoever", () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(screen.getByRole("status")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(Object.keys({ ...window.localStorage })).toEqual([]);
    expect(screen.queryByText(/unread|new notification/i)).toBeNull();
  });

  it("renders no bottom navigation and no top-level compliance concepts", () => {
    renderShell();
    const navs = screen.getAllByRole("navigation").map((nav) => nav.getAttribute("aria-label"));
    expect(navs).not.toContain("Bottom");
    expect(document.querySelector("[class*='bottom-nav'], [class*='tab-bar']")).toBeNull();
    for (const name of ["Documents", "Requirements", "Evidence", "Assessment", "RAG", "API"]) {
      expect(screen.queryByRole("link", { name })).toBeNull();
    }
  });

  it("keeps the shell usable by keyboard with visible landmarks", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Application" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    const hamburger = screen.getByRole("button", { name: "Open navigation" });
    hamburger.focus();
    expect(document.activeElement).toBe(hamburger);
    fireEvent.click(hamburger);
    expect(screen.getByRole("dialog", { name: "Application navigation" })).toBeInTheDocument();
  });
});
