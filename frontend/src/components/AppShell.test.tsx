import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../app/AuthContext";
import { WorkflowProvider } from "../app/WorkflowContext";
import { AppShell } from "./AppShell";

function renderShell() {
  render(
    <MemoryRouter>
      <AuthProvider>
        <WorkflowProvider>
          <AppShell title="Test page">
            <p>Page body</p>
          </AppShell>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  it("renders brand, navigation, title, and body", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "Xportra AI home" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Test page" })).toBeInTheDocument();
    expect(screen.getByText("Page body")).toBeInTheDocument();
  });

  it("shows the empty workspace state and a sign-in action when unconfigured", () => {
    renderShell();
    expect(screen.getByText("No active shipment")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });

  it("exposes a skip link for keyboard users", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeInTheDocument();
  });

  it("marks the active navigation item for assistive technology", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "New shipment" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("shows session status without leaking credentials", () => {
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <WorkflowProvider>
            <AppShell title="Test page">
              <p>Page body</p>
            </AppShell>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(container.querySelector(".session-dot")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/bearer|token|secret|password/i);
  });
});
