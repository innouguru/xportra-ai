import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";

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

function renderAt(path: string, authInitial?: { token: string }) {
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
  render(
    <MemoryRouter initialEntries={[path]}>
      <App authInitial={authInitial} />
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("authenticated routes", () => {
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
  });
});
