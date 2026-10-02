import { describe, expect, it } from "vitest";
import {
  processingStateTone,
  readinessTone,
  sufficiencyTone,
} from "./evidence";
import { assessmentTone } from "./findings";

/**
 * Phase 10.7B compliance-semantics pins.
 *
 * Each user-facing state resolves to a badge tone through
 * the existing helpers — never to the brand accent, never
 * to a verdict. Tones aid scanning; the words carry the
 * meaning.
 */
describe("compliance state tones", () => {
  it("keeps satisfied distinct from brand treatment", () => {
    expect(assessmentTone("satisfied")).toBe("info");
    expect(sufficiencyTone("supported")).toBe("info");
    expect(readinessTone("ready")).toBe("info");
    expect(processingStateTone("ready")).toBe("info");
  });

  it("marks information needs as attention, never failure", () => {
    expect(sufficiencyTone("missing")).toBe("attention");
    expect(sufficiencyTone("insufficient")).toBe("attention");
    expect(readinessTone("partially_ready")).toBe("attention");
    expect(assessmentTone("unknown")).toBe("attention");
  });

  it("marks negative states as attention with words doing the work", () => {
    expect(assessmentTone("not_satisfied")).toBe("attention");
    expect(processingStateTone("failed")).toBe("attention");
  });

  it("keeps unknown and unavailable states neutral", () => {
    expect(processingStateTone("uploaded")).toBe("neutral");
    expect(processingStateTone(null)).toBe("muted");
  });
});
