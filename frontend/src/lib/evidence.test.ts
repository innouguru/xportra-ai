import { describe, expect, it } from "vitest";
import {
  MAX_UPLOAD_BYTES,
  contradictionTone,
  describeUnsupportedFile,
  formatFileSize,
  gapKindLabel,
  processingStateLabel,
  processingStateNote,
  processingStateTone,
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

  it("formats upload sizes honestly", () => {
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1024)).toBe("1 KB");
    expect(formatFileSize(MAX_UPLOAD_BYTES)).toBe("10 MB");
  });

  it("pre-checks files without ever approving them", () => {
    expect(
      describeUnsupportedFile({ name: "a.pdf", size: 100, type: "application/pdf" }),
    ).toBeNull();
    expect(
      describeUnsupportedFile({ name: "a.pdf", size: MAX_UPLOAD_BYTES + 1, type: "application/pdf" }),
    ).toMatch(/10 MB/);
    expect(
      describeUnsupportedFile({ name: "a.txt", size: 100, type: "text/plain" }),
    ).toMatch(/not a supported format/);
    expect(
      describeUnsupportedFile({ name: "a.pdf", size: 100, type: "image/png" }),
    ).toMatch(/does not look like/);
  });

  it("labels processing states without compliance meaning", () => {
    expect(processingStateLabel("ready")).toBe("Ready");
    expect(processingStateLabel("failed")).toBe("Failed");
    expect(processingStateTone("ready")).toBe("info");
    expect(processingStateTone("failed")).toBe("attention");
    const notes = [
      processingStateNote("processing"),
      processingStateNote("ready"),
      processingStateNote("failed"),
    ].join(" ");
    expect(notes).not.toMatch(/compliant|verified|approved/i);
    expect(processingStateNote("ready")).toMatch(/does not mean/i);
  });
});
