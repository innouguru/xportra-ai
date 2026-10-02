import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EmptyState, ErrorState, LoadingState } from "./feedback";

describe("feedback primitives", () => {
  it("renders a friendly empty state with its action", () => {
    render(
      <EmptyState
        title="No shipments yet"
        body="Create your first shipment to see what it needs."
        action={<button type="button">New shipment</button>}
      />,
    );
    expect(screen.getByRole("heading", { name: "No shipments yet" })).toBeInTheDocument();
    expect(screen.getByText(/create your first shipment/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New shipment" })).toBeInTheDocument();
  });

  it("exposes loading through a live region", () => {
    render(<LoadingState text="Checking your documents…" />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Checking your documents…");
    expect(status).toHaveAttribute("aria-live", "polite");
  });

  it("announces errors and retries on request", () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        title="Could not load shipments."
        message="Check your connection and try again."
        onRetry={onRetry}
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Could not load shipments.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
