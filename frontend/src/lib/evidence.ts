/**
 * Pure presentation helpers for evidence state.
 *
 * Backend vocabularies render verbatim; tones only aid
 * scanning and never carry verdict meaning. In particular:
 * missing/insufficient/unknown/contradictory evidence is
 * NEVER mapped to non-compliant, failed, scores, or
 * percentages — no such mapping exists here.
 */

/** Evidence sufficiency states (evidence_sufficiency). */
export function sufficiencyTone(value: string): "info" | "muted" | "attention" | "neutral" {
  if (value === "supported") return "info";
  if (value === "unknown") return "attention";
  if (value === "missing" || value === "insufficient") return "attention";
  return "neutral";
}

/** Readiness states (readiness_state). Informational only. */
export function readinessTone(value: string): "info" | "muted" | "attention" | "neutral" {
  if (value === "ready") return "info";
  if (value === "partially_ready") return "attention";
  if (value === "not_ready") return "attention";
  return "neutral";
}

/** Gap kinds render verbatim — the backend owns their meaning. */
export function gapKindLabel(kind: string): string {
  return kind;
}

/** Contradiction states render verbatim; presence is shown, never resolved. */
export function contradictionTone(value: string): "attention" | "neutral" | "muted" {
  if (value === "present") return "attention";
  if (value === "none") return "muted";
  return "neutral";
}
