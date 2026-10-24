import { describe, expect, it } from "vitest";
import {
  applicabilityLabel,
  assessmentLabel,
  assessmentTone,
  contradictionLabel,
  countRequirementsNeedingAttention,
  readinessLabel,
  stateQualifier,
  sufficiencyLabel,
  uncertaintyLabel,
  uncertaintyTone,
} from "./findings";

describe("findings presentation helpers", () => {
  it("renders backend states verbatim", () => {
    expect(assessmentTone("satisfied")).toBe("info");
    expect(assessmentTone("not_satisfied")).toBe("attention");
    expect(assessmentTone("unknown")).toBe("attention");
    expect(uncertaintyTone("determined")).toBe("info");
    expect(uncertaintyTone("uncertain")).toBe("attention");
    expect(uncertaintyTone("unknown")).toBe("attention");
  });

  it("qualifies unknown as unresolved, never failed", () => {
    const qualifier = stateQualifier("assessment", "unknown");
    expect(qualifier).toMatch(/attention/i);
    expect(qualifier).not.toMatch(/\bfailed\b/i);
    expect(stateQualifier("assessment", "satisfied")).toBeNull();
  });

  it("qualifies missing/insufficient evidence as a need, never non-compliance", () => {
    const qualifier = stateQualifier("sufficiency", "missing");
    expect(qualifier).toBe("More evidence is needed — not a finding of non-compliance.");
    expect(stateQualifier("sufficiency", "supported")).toBeNull();
  });

  it("exposes no score, verdict, or confidence vocabulary", () => {
    const texts = [
      stateQualifier("assessment", "unknown") ?? "",
      stateQualifier("sufficiency", "insufficient") ?? "",
      stateQualifier("applicability", "unknown") ?? "",
    ].join(" ").toLowerCase();
    expect(texts).not.toMatch(/score|percent|verdict|confidence|compliant/);
  });

  it("maps recorded finding states to plain language and keeps unknown values neutral", () => {
    expect(assessmentLabel("satisfied")).toBe("Addressed in this analysis");
    expect(assessmentLabel("not_satisfied")).toBe("Needs attention");
    expect(assessmentLabel("unknown")).toBe("Still checking");
    expect(assessmentLabel("future_state")).toBe("Assessment unavailable");
    expect(applicabilityLabel("applicable")).toBe("Applies to this shipment");
    expect(applicabilityLabel("not_applicable")).toBe("Does not apply");
    expect(sufficiencyLabel("insufficient")).toBe("More evidence may be needed");
    expect(contradictionLabel("present")).toBe("Conflicting evidence recorded");
    expect(uncertaintyLabel("uncertain")).toBe("Some uncertainty remains");
    expect(readinessLabel("partially_ready")).toBe("Some information is still needed");
    expect(readinessLabel("future_state")).toBe("Information coverage unavailable");
  });

  it("counts each requirement once when report rollups overlap", () => {
    expect(
      countRequirementsNeedingAttention({
        requirements_with_missing_information: ["r1", "r2"],
        uncertain_requirement_ids: ["r1", "r3"],
      }),
    ).toBe(3);
  });
});
