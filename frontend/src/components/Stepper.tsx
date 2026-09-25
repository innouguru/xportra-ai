import {
  JOURNEY_STEPS,
  journeyStepStatuses,
  type JourneyStepId,
} from "../lib/workflow";

/**
 * Journey stepper: Shipment → Requirements → Evidence →
 * Analysis → Review → Assessment.
 *
 * Communicates process position only. Reaching a step never
 * implies the shipment is compliant. Each step carries a
 * short process description (what the stage records), never
 * a compliance claim.
 */
const STEP_DETAILS: Record<JourneyStepId, string> = {
  shipment: "Workspace and information",
  requirements: "Applicability recorded",
  evidence: "References supplied",
  analysis: "Rounds recorded",
  review: "Findings reviewed",
  assessment: "Final package",
};

export function Stepper({ state, current }: { state: string; current?: JourneyStepId }) {
  const statuses = journeyStepStatuses(state);
  const activeStep = current ?? null;
  const terminal = state === "assessment_package_ready";
  return (
    <ol className="stepper" aria-label="Compliance journey progress">
      {JOURNEY_STEPS.map((step) => {
        const status = activeStep === step.id ? "current" : statuses[step.id];
        const closed = terminal && step.id === "assessment";
        return (
          <li
            key={step.id}
            className={`step step--${status}${closed ? " step--terminal" : ""}`}
            aria-current={status === "current" ? "step" : undefined}
          >
            <span className="step-number" aria-hidden="true" />
            <span className="step-marker" aria-hidden="true" />
            <span className="step-label">
              {step.label}
              {closed ? <span className="step-flag"> — closed</span> : null}
              {!closed && status === "action-required" ? (
                <span className="step-flag"> — action needed</span>
              ) : null}
            </span>
            <span className="step-detail">{STEP_DETAILS[step.id]}</span>
          </li>
        );
      })}
    </ol>
  );
}
