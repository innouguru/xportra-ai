import { describe, expect, it } from "vitest";
import {
  contradictionTone,
  gapKindLabel,
  readinessTone,
  sufficiencyTone,
} from "./evidence";

describe("evidence presentation helpers", () => {
  it("never maps states to verdicts, scores, or percentages", () => {
    for (const value of [
      "supported",
      "missing",
      "insufficient",
      "unknown",
      "ready",
      "partially_ready",
      "not_ready",
      "present",
      "none",
      "evidence_absent",
    ]) {
      for (const label of [
        sufficiencyTone(value),
        readinessTone(value),
        contradictionTone(value),
        gapKindLabel(value),
      ]) {
        expect(String(label)).not.toMatch(/compliant|failed|score|percent|verdict|risk/i);
      }
    }
  });

  it("renders gap kinds verbatim", () => {
    expect(gapKindLabel("evidence_absent")).toBe("evidence_absent");
    expect(gapKindLabel("custom_future_kind")).toBe("custom_future_kind");
  });

  it("marks contradiction presence as attention without resolving it", () => {
    expect(contradictionTone("present")).toBe("attention");
    expect(contradictionTone("none")).toBe("muted");
  });

  it("treats missing and insufficient as attention, not failure", () => {
    expect(sufficiencyTone("missing")).toBe("attention");
    expect(sufficiencyTone("insufficient")).toBe("attention");
    expect(sufficiencyTone("supported")).toBe("info");
    expect(sufficiencyTone("unknown")).toBe("attention");
  });
});
