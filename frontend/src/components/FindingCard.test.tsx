import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
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

function renderCard(finding: AnalysisFinding, position?: { index: number; total: number }) {
  // Finding records link to the evidence workspace, so they render
  // inside a router. No assertion below depends on routing.
  return render(
    <MemoryRouter>
      <FindingCard finding={finding} {...position} />
    </MemoryRouter>,
  );
}

describe("FindingCard", () => {
  it("renders every backend section verbatim", () => {
    renderCard(finding());
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
    renderCard(finding());
    expect(screen.getByText(/shown as recorded, not resolved/i)).toBeInTheDocument();
    expect(screen.getByText("present")).toBeInTheDocument();
  });

  it("renders no score, verdict, confidence, or failure language", () => {
    const { container } = renderCard(finding());
    const text = container.textContent?.toLowerCase() ?? "";
    for (const marker of ["score", "percent", "verdict", "confidence"]) {
      expect(text).not.toContain(marker);
    }
    expect(text).not.toMatch(/\bfailed\b/);
    expect(text).not.toContain("non-compliant");
  });

  it("handles empty evidence and sources gracefully", () => {
    renderCard(
      finding({
        supporting_evidence: [],
        conflicting_evidence: [],
        sources: [],
        missing_information: [],
      }),
    );
    expect(screen.getByText(/no evidence references recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/no sources recorded/i)).toBeInTheDocument();
  });

  it("structures the finding as a case record with labeled sections", () => {
    const { container } = renderCard(finding());
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
    const { container } = renderCard(finding(), { index: 0, total: 3 });
    expect(screen.getByText("Finding 1 of 3")).toBeInTheDocument();
    expect(container.querySelector("article.finding-card")).not.toBeNull();
  });

  it("omits numbering when position is not given", () => {
    renderCard(finding());
    expect(screen.queryByText(/Finding \d+ of \d+/)).toBeNull();
  });
});
