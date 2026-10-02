import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { BackButton, Breadcrumbs, PageHeader, Sidebar, TopBar, WorkspaceContainer } from "./layout";

describe("layout primitives", () => {
  it("renders the page header hierarchy with actions", () => {
    render(
      <WorkspaceContainer>
        <PageHeader
          eyebrow="Shipment workspace"
          title="Cocoa export"
          description="What is happening and what to do next."
          actions={<button type="button">Upload document</button>}
        />
      </WorkspaceContainer>,
    );
    expect(screen.getByRole("heading", { name: "Cocoa export", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Shipment workspace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload document" })).toBeInTheDocument();
  });

  it("marks the current breadcrumb for assistive technology", () => {
    render(
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Shipments", href: "/shipments" },
          { label: "Cocoa export" },
        ]}
      />,
    );
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
    const current = screen.getByText("Cocoa export");
    expect(current).toHaveAttribute("aria-current", "page");
  });

  it("invokes the back handler on activation", () => {
    const onBack = vi.fn();
    render(<BackButton label="Back to shipments" onBack={onBack} />);
    fireEvent.click(screen.getByRole("button", { name: /back to shipments/i }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("renders the sidebar landmark with slots and collapsed state", () => {
    const { rerender } = render(
      <Sidebar
        label="Application"
        brand={<span>Xportra</span>}
        nav={<a href="/dashboard">Dashboard</a>}
        footer={<span>Account</span>}
      />,
    );
    const sidebar = screen.getByRole("complementary", { name: "Application" });
    expect(sidebar).toBeInTheDocument();
    expect(sidebar.className).toMatch(/xb-sidebar/);
    expect(sidebar.className).not.toMatch(/xb-sidebar--collapsed/);
    expect(screen.getByRole("navigation", { name: "Application sections" })).toBeInTheDocument();

    rerender(
      <Sidebar label="Application" nav={<a href="/dashboard">Dashboard</a>} collapsed />,
    );
    expect(screen.getByRole("complementary", { name: "Application" }).className).toMatch(
      /xb-sidebar--collapsed/,
    );
  });

  it("renders the contextual top bar slots", () => {
    render(<TopBar context={<span>Shipment context</span>} actions={<span>Actions</span>} />);
    expect(screen.getByText("Shipment context")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });
});
