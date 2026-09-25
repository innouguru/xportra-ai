import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FindingCard } from "./FindingCard";
import type { AnalysisFinding } from "../types/api";
function finding(overrides: Partial<AnalysisFinding> = {}): AnalysisFinding {
  return {
    analysis_id: "a1",
    requirement_id: "req-1",
    requirement_text: "File form X before export.",
    applicability: "applicable",
    assessment: "unknown",
    explanation: "The evidence does not yet establish the filing.",
    uncertainty: "uncertain",
    uncertainty_explanation: "Wording is ambiguous.",
    evidence_sufficiency: "insufficient",
    sufficiency_explanation: "One of two expected items present.",
    contradiction_state: "present",
    missing_information: ["Certificate copy missing."],
    supporting_evidence: [{ evidence_id: "ev-1", status: "accepted" }],
    conflicting_evidence: [{ evidence_id: "ev-2", status: "rejected" }],
    knowledge_references: [],
    sources: [{ kind: "authority", identifier: "NG-SON" }],
    missing_items: [],
    ...overrides,
  };
}

describe("FindingCard", () => {
  it("renders every backend section verbatim", () => {
    render(<FindingCard finding={finding()} />);
    expect(screen.getByText("File form X before export.")).toBeInTheDocument();
    expect(screen.getByText("The evidence does not yet establish the filing.")).toBeInTheDocument();
    expect(screen.getByText("Certificate copy missing.")).toBeInTheDocument();
    expect(screen.getByText("Wording is ambiguous.")).toBeInTheDocument();
    expect(screen.getByText("One of two expected items present.")).toBeInTheDocument();
    expect(screen.getByText("applicable")).toBeInTheDocument();
    expect(screen.getByText("unknown")).toBeInTheDocument();
    expect(screen.getByText("insufficient")).toBeInTheDocument();
    expect(screen.getByText("present")).toBeInTheDocument();
  });

  it("preserves contradictions instead of resolving them", () => {
    render(<FindingCard finding={finding()} />);
    expect(screen.getByText(/shown as recorded, not resolved/i)).toBeInTheDocument();
    expect(screen.getByText("present")).toBeInTheDocument();
  });

  it("renders no score, verdict, confidence, or failure language", () => {
    const { container } = render(<FindingCard finding={finding()} />);
    const text = container.textContent?.toLowerCase() ?? "";
    for (const marker of ["score", "percent", "verdict", "confidence"]) {
      expect(text).not.toContain(marker);
    }
    expect(text).not.toMatch(/\bfailed\b/);
    expect(text).not.toContain("non-compliant");
  });

  it("handles empty evidence and sources gracefully", () => {
    render(
      <FindingCard
        finding={finding({
          supporting_evidence: [],
          conflicting_evidence: [],
          sources: [],
          missing_information: [],
        })}
      />,
    );
    expect(screen.getByText(/no evidence references recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/no sources recorded/i)).toBeInTheDocument();
  });

  it("structures the finding as a case record with labeled sections", () => {
    const { container } = render(<FindingCard finding={finding()} />);
    expect(screen.getByText("Requirement")).toBeInTheDocument();
    const article = container.querySelector("article.finding-card");
    expect(article).not.toBeNull();
    const sections = Array.from(
      article?.querySelectorAll("section.finding-section") ?? [],
    );
    expect(sections.length).toBeGreaterThanOrEqual(3);
    for (const section of sections) {
      expect(section.querySelector("h4")).not.toBeNull();
    }
  });

  it("numbers the finding within its report when position is given", () => {
    const { container } = render(<FindingCard finding={finding()} index={0} total={3} />);
    expect(screen.getByText("Finding 1 of 3")).toBeInTheDocument();
    expect(container.querySelector("article.finding-card")).not.toBeNull();
  });

  it("omits numbering when position is not given", () => {
    render(<FindingCard finding={finding()} />);
    expect(screen.queryByText(/Finding \d+ of \d+/)).toBeNull();
  });
});
