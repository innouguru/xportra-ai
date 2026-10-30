import { describe, expect, it } from "vitest";
import {
  MAX_ARTIFACT_UPLOAD_BYTES,
  describeUnsupportedArtifactFile,
  resolveArtifactContentType,
} from "./regulatoryUpload";

describe("describeUnsupportedArtifactFile", () => {
  it("accepts files whose extension and MIME match the backend contract", () => {
    expect(
      describeUnsupportedArtifactFile({
        name: "regulation.pdf",
        size: 1024,
        type: "application/pdf",
      }),
    ).toBeNull();
    // Empty MIME (browsers often omit it) falls back to the extension.
    expect(
      describeUnsupportedArtifactFile({
        name: "act.txt",
        size: 1024,
        type: "",
      }),
    ).toBeNull();
    expect(
      describeUnsupportedArtifactFile({
        name: "guide.md",
        size: 1024,
        type: "",
      }),
    ).toBeNull();
    // Generic MIME cannot be trusted; the extension decides.
    expect(
      describeUnsupportedArtifactFile({
        name: "tariff.json",
        size: 1024,
        type: "application/octet-stream",
      }),
    ).toBeNull();
  });

  it("rejects unsupported extensions before any submission", () => {
    expect(
      describeUnsupportedArtifactFile({
        name: "scan.png",
        size: 1024,
        type: "image/png",
      }),
    ).toMatch(/not a supported artifact format/);
    expect(
      describeUnsupportedArtifactFile({
        name: "report.docx",
        size: 1024,
        type: "",
      }),
    ).toMatch(/not a supported artifact format/);
  });

  it("rejects files whose specific MIME type the backend does not accept", () => {
    expect(
      describeUnsupportedArtifactFile({
        name: "cover.pdf",
        size: 1024,
        type: "image/jpeg",
      }),
    ).toMatch(/unsupported content type/);
  });

  it("rejects empty and oversized files consistent with the backend limits", () => {
    expect(
      describeUnsupportedArtifactFile({
        name: "empty.pdf",
        size: 0,
        type: "application/pdf",
      }),
    ).toMatch(/empty/);
    expect(
      describeUnsupportedArtifactFile({
        name: "big.pdf",
        size: MAX_ARTIFACT_UPLOAD_BYTES + 1,
        type: "application/pdf",
      }),
    ).toMatch(/over the 10 MB limit/);
    // Exactly at the backend limit is accepted.
    expect(
      describeUnsupportedArtifactFile({
        name: "limit.pdf",
        size: MAX_ARTIFACT_UPLOAD_BYTES,
        type: "application/pdf",
      }),
    ).toBeNull();
  });
});

describe("resolveArtifactContentType", () => {
  it("uses a specific backend-accepted MIME type the browser reports", () => {
    expect(
      resolveArtifactContentType({ name: "doc.pdf", type: "application/pdf" }),
    ).toBe("application/pdf");
  });

  it("maps empty and generic MIME types to the extension-derived type", () => {
    expect(
      resolveArtifactContentType({ name: "minutes.txt", type: "" }),
    ).toBe("text/plain");
    expect(
      resolveArtifactContentType({ name: "charter.md", type: "" }),
    ).toBe("text/markdown");
    expect(
      resolveArtifactContentType({
        name: "schedule.json",
        type: "application/octet-stream",
      }),
    ).toBe("application/json");
  });
});
