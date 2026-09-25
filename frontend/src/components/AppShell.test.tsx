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

  it("hides current-shipment navigation without an active record", () => {
    renderShell();
    expect(screen.queryByRole("navigation", { name: "Current shipment" })).toBeNull();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
  });

  it("shows current-shipment navigation with an active record", () => {
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
      <MemoryRouter initialEntries={["/workspace/evidence"]}>
        <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
          <WorkflowProvider>
            <AppShell title="Test page">
              <p>Page body</p>
            </AppShell>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    const shipmentNav = screen.getByRole("navigation", { name: "Current shipment" });
    for (const name of ["Overview", "Information", "Requirements", "Evidence", "Analysis", "Assessment"]) {
      expect(shipmentNav).toHaveTextContent(name);
    }
    // Application and shipment navigation stay distinct; the active
    // shipment section is marked for assistive technology.
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Evidence" })).toHaveAttribute(
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
      "/workspace/package",
    );
  });
});
