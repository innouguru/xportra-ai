import { describe, expect, it, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ThemeProvider } from "../../theme/theme";
import { SettingsPage } from "./SettingsPage";

/**
 * Phase 10.8I settings contract.
 *
 * Only session, theme, and connection facts
 * are functional; everything without a real
 * boundary renders as an honest unavailable
 * state with no pretend controls.
 */

function stubMatchMedia(matches = false) {
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

function renderPage() {
  stubMatchMedia();
  render(
    <MemoryRouter initialEntries={["/settings"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <ThemeProvider>
            <Routes>
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/session" element={<div>Session screen</div>} />
              <Route path="/dashboard" element={<div>Dashboard screen</div>} />
            </Routes>
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

describe("SettingsPage", () => {
  it("renders utility sections inside the authenticated shell", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Settings", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Application" })).toBeInTheDocument();
    for (const name of ["Account", "Organization", "Preferences", "Notifications", "Security"]) {
      expect(screen.getByRole("heading", { name })).toBeInTheDocument();
    }
  });

  it("shows connection facts without secrets and offers sign out", () => {
    renderPage();
    expect(screen.getByText("Development tenant (local development only)")).toBeInTheDocument();
    expect(screen.getByText("http://localhost:8000")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/22222222-2222-2222-2222-222222222222/);
    expect(text).not.toMatch(/bearer|secret|password/i);
  });

  it("changes the theme through the existing provider, nothing else", () => {
    renderPage();
    const group = screen.getByRole("group", { name: "Theme" });
    expect(group).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Light" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem("xportra.theme.mode.v1")).toBe("light");
  });

  it("marks unsupported areas honestly with no pretend controls", () => {
    renderPage();
    expect(screen.getByText(/detailed account management isn’t available/i)).toBeInTheDocument();
    expect(screen.getByText(/organization settings aren’t available/i)).toBeInTheDocument();
    expect(screen.getByText(/no notification settings to configure/i)).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(main.querySelectorAll("input[type='checkbox']").length).toBe(0);
    expect(main.textContent).not.toMatch(/coming soon|fake|beta toggle/i);
  });

  it("navigates back to the dashboard", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /back to dashboard/i }));
    expect(screen.getByText("Dashboard screen")).toBeInTheDocument();
  });
});
