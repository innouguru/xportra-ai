import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import {
  DocumentStatus,
  RequirementCard,
  RequirementLedgerRow,
  RequirementStatus,
  ShipmentCard,
  ShipmentStatus,
  ShipmentSummary,
  ShipmentWorklistRow,
} from "./shipment";
import { StatusBadge } from "./status";

/**
 * Fixtures below are test-only display strings.
 * They assert primitive composition — never
 * business logic, never backend states.
 */
const SHIPMENT_FIXTURE = {
  title: "Cocoa — test fixture",
  meta: "Lagos → Rotterdam · test fixture",
  href: "/shipments/test-fixture",
};

describe("shipment primitives", () => {
  it("renders a clickable briefing card with a separate primary action", () => {
    render(
      <ul>
        <ShipmentCard
          title={SHIPMENT_FIXTURE.title}
          meta={SHIPMENT_FIXTURE.meta}
          status={<ShipmentStatus tone="warning" label="Needs attention" />}
          href={SHIPMENT_FIXTURE.href}
          action={<button type="button">Upload document</button>}
        />
      </ul>,
    );
    const link = screen.getByRole("link", { name: SHIPMENT_FIXTURE.title });
    expect(link).toHaveAttribute("href", SHIPMENT_FIXTURE.href);
    expect(screen.getByText(SHIPMENT_FIXTURE.meta)).toBeInTheDocument();
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
    const action = screen.getByRole("button", { name: "Upload document" });
    expect(action).toBeInTheDocument();
  });

  it("renders a worklist row with dot, name, route, state, and arrow action", () => {
    const onSelect = vi.fn();
    render(
      <ul>
        <ShipmentWorklistRow
          name="Frozen mango purée"
          route="→ European Union"
          state="1 requirement needs attention"
          tone="warning"
          href="/shipments/test-fixture"
          actionLabel="Review"
          onSelect={onSelect}
        />
      </ul>,
    );
    const link = screen.getByRole("link", { name: "Frozen mango purée" });
    expect(link).toHaveAttribute("href", "/shipments/test-fixture");
    expect(screen.getByText("→ European Union")).toBeInTheDocument();
    expect(screen.getByText("1 requirement needs attention")).toBeInTheDocument();
    fireEvent.click(link);
    expect(onSelect).toHaveBeenCalledTimes(1);
    const action = screen.getByRole("button", { name: "Review" });
    fireEvent.click(action);
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it("renders a requirement ledger row as one drawer-opening control", () => {
    const onOpen = vi.fn();
    render(
      <ul>
        <RequirementLedgerRow
          name="Phytosanitary certificate"
          why="Required because this destination requires plant-health certification."
          state="Satisfied"
          tone="success"
          evidence="Evidence: phytosanitary_certificate.pdf"
          onOpen={onOpen}
        />
      </ul>,
    );
    const row = screen.getByRole("button", { name: "Phytosanitary certificate — Satisfied" });
    expect(screen.getByText("Required because this destination requires plant-health certification.")).toBeInTheDocument();
    expect(screen.getByText("Evidence: phytosanitary_certificate.pdf")).toBeInTheDocument();
    fireEvent.click(row);
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("invokes onSelect instead of navigating when provided", () => {
    const onSelect = vi.fn();
    render(
      <ul>
        <ShipmentCard
          title={SHIPMENT_FIXTURE.title}
          status={<ShipmentStatus tone="info" label="Still checking" />}
          href={SHIPMENT_FIXTURE.href}
          onSelect={onSelect}
        />
      </ul>,
    );
    fireEvent.click(screen.getByRole("link", { name: SHIPMENT_FIXTURE.title }));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("renders shipment facts as labeled rows", () => {
    render(
      <ShipmentSummary
        rows={[
          { label: "Product", value: "Cocoa beans" },
          { label: "Destination", value: "Rotterdam" },
        ]}
      />,
    );
    expect(screen.getByText("Product")).toBeInTheDocument();
    expect(screen.getByText("Rotterdam")).toBeInTheDocument();
  });

  it("supports the user-facing requirement states", () => {
    for (const label of ["Addressed", "Waiting for you", "Needs attention", "Still checking"]) {
      const { unmount } = render(
        <RequirementCard
          name="Phytosanitary certificate"
          status={<RequirementStatus tone="info" label={label} />}
          action={<button type="button">View documents</button>}
        />,
      );
      expect(screen.getByRole("heading", { name: "Phytosanitary certificate" })).toBeInTheDocument();
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it("renders document verification stages in plain words", () => {
    render(<DocumentStatus tone="info" label="Checking evidence" />);
    expect(screen.getByText("Checking evidence")).toBeInTheDocument();
  });

  it("never exposes technical state vocabulary", () => {
    const { container } = render(
      <div>
        <ShipmentCard
          title={SHIPMENT_FIXTURE.title}
          status={<ShipmentStatus tone="info" label="Still checking" detail="Reading document" />}
          href={SHIPMENT_FIXTURE.href}
        />
        <RequirementCard
          name="Certificate of origin"
          status={<StatusBadge tone="warning" label="Waiting for you" />}
        />
      </div>,
    );
    for (const forbidden of ["UNKNOWN", "sufficiency", "confidence", "retrieval", "Run Compliance"]) {
      expect(container.textContent).not.toContain(forbidden);
    }
  });
});
