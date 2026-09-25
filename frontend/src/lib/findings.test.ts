import { describe, expect, it } from "vitest";
import { assessmentTone, stateQualifier, uncertaintyTone } from "./findings";

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
});
