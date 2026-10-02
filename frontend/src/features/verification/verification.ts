import type { AnalysisFinding, AnalysisReport } from "../../types/api";
import type { StatusTone } from "../../primitives/status";

/**
 * Phase 10.8F verification presentation mapping.
 *
 * Verification here means exactly what the
 * existing boundaries support: an uploaded
 * document is linked to a requirement
 * (`supply-evidence`), and the verdict comes
 * from the authoritative finding recorded by a
 * backend analysis round — never from a
 * frontend judgment, score, or fabricated
 * reason. Unknown means "no finding yet" or an
 * undecided assessment, never failure.
 */

export type VerificationState = "satisfied" | "not-satisfied" | "unknown";

export interface VerificationVerdict {
  state: VerificationState;
  label: string;
  tone: StatusTone;
  explanation: string;
}

/** User-facing verdict for one recorded assessment. */
export function verdictForAssessment(assessment: string): VerificationVerdict {
  switch (assessment) {
    case "satisfied":
      return {
        state: "satisfied",
        label: "Satisfied",
        tone: "success",
        explanation: "This document satisfies the requirement.",
      };
    case "not_satisfied":
      return {
        state: "not-satisfied",
        label: "Not satisfied",
        tone: "warning",
        explanation: "This document does not provide all the evidence needed for this requirement.",
      };
    default:
      return {
        state: "unknown",
        label: "Unknown",
        tone: "neutral",
        explanation: "Xportra could not determine whether this document satisfies the requirement.",
      };
  }
}

/** Verdict when no finding exists yet for the requirement. */
export function unverifiedVerdict(): VerificationVerdict {
  return {
    state: "unknown",
    label: "Unknown",
    tone: "neutral",
    explanation:
      "This requirement has not been analyzed with this document yet. Run analysis to record a finding.",
  };
}

/** Latest finding for a requirement id, or null. */
export function findFindingForRequirement(
  report: AnalysisReport | null,
  requirementId: string,
): AnalysisFinding | null {
  if (!report) {
    return null;
  }
  const matches = report.findings.filter((finding) => finding.requirement_id === requirementId);
  return matches.length > 0 ? matches[matches.length - 1] : null;
}

/** Non-empty trimmed lines of missing information. */
export function missingLines(finding: AnalysisFinding): string[] {
  return finding.missing_information.filter((line) => line.trim().length > 0);
}

/** Inline preview support by mime type (honest subset only). */
export function previewKind(mimeType: string | null): "pdf" | "image" | "unsupported" {
  if (mimeType === "application/pdf") {
    return "pdf";
  }
  if (mimeType === "image/jpeg" || mimeType === "image/png" || mimeType === "image/jpg") {
    return "image";
  }
  return "unsupported";
}
