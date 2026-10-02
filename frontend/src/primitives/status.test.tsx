import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AttentionIndicator, MetricSummary, StatusBadge, StatusIndicator } from "./status";

describe("status primitives", () => {
  it("renders indicator words with a non-color cue for every tone", () => {
    const tones = ["success", "warning", "danger", "info", "neutral"] as const;
    for (const tone of tones) {
      const { unmount } = render(<StatusIndicator tone={tone} label={`State ${tone}`} />);
      expect(screen.getByText(`State ${tone}`)).toBeInTheDocument();
      unmount();
    }
  });

  it("renders optional detail text alongside the label", () => {
    render(<StatusIndicator tone="warning" label="Needs attention" detail="2 documents missing" />);
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByText("2 documents missing")).toBeInTheDocument();
  });

  it("renders badges with explicit labels", () => {
    render(<StatusBadge tone="info" label="Still checking" />);
    expect(screen.getByText("Still checking")).toBeInTheDocument();
  });

  it("announces metric values through their labels", () => {
    render(<MetricSummary value="5" label="Active shipments" hint="Across this workspace" />);
    expect(screen.getByText("Active shipments: 5")).toBeInTheDocument();
    expect(screen.getByText("Across this workspace")).toBeInTheDocument();
  });

  it("renders the quiet attention affordance", () => {
    render(<AttentionIndicator label="2 shipments need attention" />);
    expect(screen.getByText("2 shipments need attention")).toBeInTheDocument();
  });
});
