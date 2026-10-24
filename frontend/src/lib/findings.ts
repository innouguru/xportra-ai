/**
 * Pure presentation helpers for analysis findings.
 *
 * Presentation labels summarize recorded backend values without
 * changing their meaning. Tones aid scanning only.
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

/** Plain language for an analysis record, not a regulatory verdict. */
export function assessmentLabel(value: string): string {
  if (value === "satisfied") return "Addressed in this analysis";
  if (value === "not_satisfied") return "Needs attention";
  if (value === "unknown") return "Still checking";
  return "Assessment unavailable";
}

export function applicabilityLabel(value: string): string {
  if (value === "applicable") return "Applies to this shipment";
  if (value === "not_applicable") return "Does not apply";
  if (value === "unknown") return "Not yet determined";
  return "Applicability unavailable";
}

export function sufficiencyLabel(value: string): string {
  if (value === "supported") return "Supporting evidence recorded";
  if (value === "insufficient") return "More evidence may be needed";
  if (value === "missing") return "No evidence recorded";
  if (value === "unknown") return "Not yet determined";
  return "Evidence status unavailable";
}

export function contradictionLabel(value: string): string {
  if (value === "present") return "Conflicting evidence recorded";
  if (value === "none") return "No conflict recorded";
  if (value === "unknown") return "Conflict status not determined";
  return "Conflict status unavailable";
}

export function uncertaintyLabel(value: string): string {
  if (value === "uncertain") return "Some uncertainty remains";
  if (value === "determined") return "No uncertainty recorded";
  if (value === "unknown") return "Uncertainty not determined";
  return "Uncertainty status unavailable";
}

/** Information coverage helper labels are not compliance outcomes. */
export function readinessLabel(value: string): string {
  if (value === "ready") return "Information coverage appears complete";
  if (value === "partially_ready") return "Some information is still needed";
  if (value === "not_ready") return "More information is needed before coverage can be checked";
  return "Information coverage unavailable";
}

/** Unique requirements flagged in either report rollup. */
export function countRequirementsNeedingAttention(report: {
  requirements_with_missing_information: string[];
  uncertain_requirement_ids: string[];
}): number {
  return new Set([
    ...report.requirements_with_missing_information,
    ...report.uncertain_requirement_ids,
  ]).size;
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
