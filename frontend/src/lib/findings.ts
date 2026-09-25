/**
 * Pure presentation helpers for analysis findings.
 *
 * Assessment, uncertainty, and contradiction values render
 * verbatim from the backend. Tones aid scanning only.
 * Forbidden mappings (enforced by tests, never present
 * here): overall scores, numeric confidence, verdicts,
 * "unknown → failed", "missing → non-compliant",
 * contradiction resolution.
 */

/** Assessment states (assessment). Verbatim, never a verdict. */
export function assessmentTone(value: string): "info" | "muted" | "attention" | "neutral" {
  if (value === "satisfied") return "info";
  if (value === "not_satisfied") return "attention";
  if (value === "unknown") return "attention";
  return "neutral";
}

/** Uncertainty categories (uncertainty). Verbatim. */
export function uncertaintyTone(value: string): "info" | "muted" | "attention" | "neutral" {
  if (value === "determined") return "info";
  if (value === "uncertain") return "attention";
  if (value === "unknown") return "attention";
  return "neutral";
}

/** Short human qualifier clarifying — not redefining — a state. */
export function stateQualifier(kind: "assessment" | "applicability" | "sufficiency", value: string): string | null {
  if (value === "unknown") {
    if (kind === "assessment") return "Unresolved — needs attention, not a failure.";
    if (kind === "applicability") return "Not yet determined.";
    return "Not yet established.";
  }
  if (kind === "sufficiency" && (value === "missing" || value === "insufficient")) {
    return "More evidence is needed — not a finding of non-compliance.";
  }
  return null;
}
