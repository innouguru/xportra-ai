/**
 * Presentation helpers for the workflow history projection.
 *
 * History is a projection over recorded identifiers — NOT event
 * sourcing. Entries are grouped by kind in the backend's fixed
 * presentation order, and no timestamps exist anywhere in the
 * workflow, so none are rendered or invented. These helpers only
 * label what the backend already recorded; they add no reasoning
 * content and no chronology.
 */

const KIND_LABELS: Record<string, string> = {
  workflow_created: "Workflow created",
  shipment_bound: "Shipment bound",
  evidence_supplied: "Evidence supplied",
  analysis_completed: "Analysis completed",
  final_package_ready: "Final package ready",
};

/** Human label for a recorded entry kind (unknown kinds stay verbatim). */
export function historyKindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

/** Reference labels are rendered as recorded, underscores expanded. */
export function referenceLabel(label: string): string {
  return label.replace(/_/g, " ");
}

/** One projection reference as received (`{label, value}` pairs). */
export interface HistoryReferenceView {
  label: string;
  value: string;
}

/** Read a reference defensively: only the recorded label/value survive. */
export function readReference(reference: Record<string, string>): HistoryReferenceView {
  const label = typeof reference["label"] === "string" ? reference["label"] : "";
  const value = typeof reference["value"] === "string" ? reference["value"] : "";
  return { label, value };
}
