import { describe, expect, it, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../app/AuthContext";
import { WorkflowProvider } from "../app/WorkflowContext";
import { AppShell } from "./AppShell";

afterEach(() => {
  sessionStorage.clear();
});

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

  it("renders the brand lockup without fabricated artwork", () => {
    renderShell();
    const glyph = document.querySelector(".brand-glyph");
    expect(glyph).not.toBeNull();
    expect(glyph?.querySelector("svg, path, img, canvas")).toBeNull();
  });

  it("shows the empty workspace state and a sign-in action when unconfigured", () => {
    renderShell();
    expect(screen.getByText("No active shipment")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Sign in" }).length).toBeGreaterThan(0);
  });

  it("exposes a skip link for keyboard users", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeInTheDocument();
  });

  it("shows the public site map without an active shipment", () => {
    renderShell();
    const primary = screen.getByRole("navigation", { name: "Primary" });
    for (const name of ["Product", "How It Works", "For Exporters", "Resources"]) {
      expect(primary).toHaveTextContent(name);
    }
    expect(screen.getByRole("link", { name: "Start a shipment" })).toBeInTheDocument();
    // No workflow concepts leak into public navigation.
    expect(screen.queryByRole("link", { name: "Assessment" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Documents" })).toBeNull();
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

  it("shows public navigation without an active record", () => {
    renderShell();
    // Without a shipment the secondary group carries the public
    // entry points, never workflow concepts.
    const secondary = screen.getByRole("navigation", { name: "Secondary" });
    expect(secondary).toHaveTextContent("Sign in");
    expect(secondary).toHaveTextContent("Start a shipment");
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Documents" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Assessment" })).toBeNull();
  });

  it("shows the five product concepts with an active record", () => {
    sessionStorage.setItem(
      "xportra.workflow-record.v1",
      JSON.stringify({
        id: "11111111-1111-1111-1111-111111111111",
        tenant_id: "22222222-2222-2222-2222-222222222222",
        case_id: "33333333-3333-3333-3333-333333333333",
        shipment_id: null,
        state: "evidence_pending",
        rounds: [],
        supplied_evidence_ids: [],
        open_requirements: [],
      }),
    );
    render(
      <MemoryRouter initialEntries={["/workspace/documents"]}>
        <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
          <WorkflowProvider>
            <AppShell title="Test page">
              <p>Page body</p>
            </AppShell>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    const primary = screen.getByRole("navigation", { name: "Primary" });
    for (const name of ["Overview", "Shipments", "Documents", "Requirements", "Assessment"]) {
      expect(primary).toHaveTextContent(name);
    }
    // Internal workflow stages are not top-level destinations.
    for (const name of ["Information", "Evidence gaps", "Analysis", "Review", "Final review"]) {
      expect(screen.queryByRole("link", { name })).toBeNull();
    }
    // Secondary navigation carries Ask Xportra slot and Settings.
    expect(screen.getByRole("navigation", { name: "Secondary" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
    // Application and shipment navigation stay distinct; the active
    // product concept is marked for assistive technology.
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("points Assessment at the package once the workflow is terminal", () => {
    sessionStorage.setItem(
      "xportra.workflow-record.v1",
      JSON.stringify({
        id: "11111111-1111-1111-1111-111111111111",
        tenant_id: "22222222-2222-2222-2222-222222222222",
        case_id: "33333333-3333-3333-3333-333333333333",
        shipment_id: null,
        state: "assessment_package_ready",
        rounds: [],
        supplied_evidence_ids: [],
        open_requirements: [],
      }),
    );
    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
          <WorkflowProvider>
            <AppShell title="Test page">
              <p>Page body</p>
            </AppShell>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Assessment" }).getAttribute("href")).toBe(
      "/workspace/assessment",
    );
  });
});
