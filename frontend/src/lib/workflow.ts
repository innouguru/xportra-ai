/**
 * Pure presentation helpers for workflow state.
 *
 * These map backend process states to human labels and
 * journey steps. They contain NO compliance logic: no
 * verdicts, no scores, no reinterpretation of regulatory
 * truth. Statuses from the backend are rendered verbatim
 * where they carry regulatory meaning (applicability,
 * assessment).
 */

/** Backend process states (compliance_workflow.WORKFLOW_STATES). */
export const WORKFLOW_STATES = [
  "created",
  "information_provided",
  "evidence_pending",
  "applicability_determined",
  "analysis_available",
  "review_required",
  "additional_evidence_requested",
  "reanalysis_required",
  "assessment_package_ready",
] as const;

export type WorkflowState = (typeof WORKFLOW_STATES)[number];

/** Human labels describe process position only — never compliance truth. */
const STATE_LABELS: Record<string, string> = {
  created: "Created",
  information_provided: "Information provided",
  evidence_pending: "Evidence pending",
  applicability_determined: "Applicability determined",
  analysis_available: "Analysis available",
  review_required: "Review required",
  additional_evidence_requested: "Additional evidence requested",
  reanalysis_required: "Re-analysis required",
  assessment_package_ready: "Assessment package ready",
};

export function workflowStateLabel(state: string): string {
  return STATE_LABELS[state] ?? state;
}

/** Journey spine: Shipment → Requirements → Evidence → Analysis → Review → Assessment. */
export type JourneyStepId =
  | "shipment"
  | "requirements"
  | "evidence"
  | "analysis"
  | "review"
  | "assessment";

export const JOURNEY_STEPS: Array<{ id: JourneyStepId; label: string }> = [
  { id: "shipment", label: "Shipment" },
  { id: "requirements", label: "Requirements" },
  { id: "evidence", label: "Evidence" },
  { id: "analysis", label: "Analysis" },
  { id: "review", label: "Review" },
  { id: "assessment", label: "Assessment" },
];

const STATE_TO_STEP: Record<string, JourneyStepId> = {
  created: "shipment",
  information_provided: "shipment",
  evidence_pending: "evidence",
  applicability_determined: "requirements",
  analysis_available: "analysis",
  review_required: "review",
  additional_evidence_requested: "evidence",
  reanalysis_required: "analysis",
  assessment_package_ready: "assessment",
};

/** Which journey step a backend state belongs to. Unknown states map to shipment (start). */
export function journeyStepForState(state: string): JourneyStepId {
  return STATE_TO_STEP[state] ?? "shipment";
}

export type StepStatus = "complete" | "current" | "upcoming" | "action-required";

/**
 * Status of each journey step given the current backend state.
 * Terminal package state marks assessment current (closed);
 * evidence-loop states flag action-required on evidence/analysis.
 */
export function journeyStepStatuses(state: string): Record<JourneyStepId, StepStatus> {
  const order = JOURNEY_STEPS.map((step) => step.id);
  const current = journeyStepForState(state);
  const currentIndex = order.indexOf(current);
  const statuses = {} as Record<JourneyStepId, StepStatus>;
  for (const [index, id] of order.entries()) {
    if (id === current) {
      statuses[id] = "current";
    } else if (index < currentIndex) {
      statuses[id] = "complete";
    } else {
      statuses[id] = "upcoming";
    }
  }
  if (state === "additional_evidence_requested") {
    statuses.evidence = "action-required";
  }
  if (state === "reanalysis_required") {
    statuses.analysis = "action-required";
  }
  return statuses;
}

/** Applicability outcomes render verbatim — the backend owns their meaning. */
export function applicabilityLabel(outcome: string): string {
  return outcome;
}

/** `unknown` applicability is undecided, never failed. */
export function applicabilityTone(outcome: string): "info" | "muted" | "attention" {
  if (outcome === "applicable") return "info";
  if (outcome === "not_applicable") return "muted";
  return "attention";
}

/** Terminal workflow states (compliance_workflow.WORKFLOW_TERMINAL_STATES). */
export const WORKFLOW_TERMINAL_STATES = ["assessment_package_ready"] as const;

/**
 * Whether a workflow state is terminal (permanently closed).
 *
 * Used only to stop offering mutating controls and to explain the
 * terminal state in text. It is a process fact, never a compliance
 * claim, and the backend remains the authority on closure.
 */
export function isTerminalState(state: string): boolean {
  return (WORKFLOW_TERMINAL_STATES as readonly string[]).includes(state);
}
