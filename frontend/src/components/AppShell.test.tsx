import { describe, expect, it, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
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
    expect(screen.getByRole("navigation", { name: "Public" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Test page" })).toBeInTheDocument();
    expect(screen.getByText("Page body")).toBeInTheDocument();
  });

  it("renders the brand lockup without fabricated artwork", () => {
    renderShell();
    const glyph = document.querySelector(".brand-glyph");
    expect(glyph).not.toBeNull();
    expect(glyph?.querySelector("svg, path, img, canvas")).toBeNull();
  });

  it("keeps authentication pages free of shipment status and workspace actions", () => {
    renderShell();
    expect(screen.queryByText("No active shipment")).toBeNull();
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("link", { name: "Start a shipment" })).toBeNull();
  });

  it("exposes a skip link for keyboard users", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeInTheDocument();
  });

  it("does not mount workspace or marketing navigation in the authentication shell", () => {
    renderShell();
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Secondary" })).toBeNull();
  });

  it("does not mount a session area on authentication pages", () => {
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
    expect(container.querySelector(".session-area")).toBeEmptyDOMElement();
    expect(container.textContent).not.toMatch(/bearer|token|secret|password/i);
  });

  it("shows no navigation without an active record in authentication mode", () => {
    renderShell();
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Secondary" })).toBeNull();
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
            <AppShell title="Test page" variant="workspace">
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
            <AppShell title="Test page" variant="workspace">
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

  it("renders no workspace controls when a record exists without a session", () => {
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
      <MemoryRouter initialEntries={["/session"]}>
        <AuthProvider>
          <WorkflowProvider>
            <AppShell title="Test page">
              <p>Page body</p>
            </AppShell>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Documents" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Assessment" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Settings" })).toBeNull();
    expect(screen.queryByText("No active shipment")).toBeNull();
    expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
  });

  it("hides workspace navigation once the session ends", () => {
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
      <MemoryRouter initialEntries={["/workspace"]}>
        <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
          <WorkflowProvider>
            <AppShell title="Test page" variant="workspace">
              <p>Page body</p>
            </AppShell>
          </WorkflowProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Documents" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(screen.queryByRole("link", { name: "Documents" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Assessment" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Documents" })).toBeNull();
  });
});
