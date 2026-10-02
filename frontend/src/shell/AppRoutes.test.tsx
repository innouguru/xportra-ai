import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";

/**
 * Phase 10.8B route smoke tests.
 *
 * The authenticated shell serves the dashboard and
 * shipment-list routes; the public landing route
 * stays outside the shell. Full page behavior
 * belongs to later 10.8 phases.
 */

function renderAt(path: string) {
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
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("authenticated routes", () => {
  it("serves the dashboard inside the application shell", () => {
    renderAt("/dashboard");
    expect(screen.getByRole("complementary", { name: "Application" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Your shipments", level: 1 })).toBeInTheDocument();
  });

  it("serves the shipment list inside the application shell", () => {
    renderAt("/shipments");
    expect(screen.getByRole("complementary", { name: "Application" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("View Shipments");
  });

  it("keeps the public landing page outside the application shell", () => {
    renderAt("/");
    expect(screen.queryByRole("complementary", { name: "Application" })).toBeNull();
  });
});
