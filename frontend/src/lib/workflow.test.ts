import { describe, expect, it } from "vitest";
import {
  JOURNEY_STEPS,
  applicabilityLabel,
  applicabilityTone,
  journeyStepForState,
  journeyStepStatuses,
  workflowStateLabel,
} from "./workflow";

describe("workflowStateLabel", () => {
  it("labels every known backend state as process position", () => {
    expect(workflowStateLabel("created")).toBe("Created");
    expect(workflowStateLabel("assessment_package_ready")).toBe(
      "Assessment package ready",
    );
  });

  it("passes unknown states through instead of inventing labels", () => {
    expect(workflowStateLabel("mystery")).toBe("mystery");
  });

  it("never uses regulatory-truth vocabulary", () => {
    for (const state of [
      "created",
      "information_provided",
      "evidence_pending",
      "applicability_determined",
      "analysis_available",
      "review_required",
      "additional_evidence_requested",
      "reanalysis_required",
      "assessment_package_ready",
    ]) {
      expect(workflowStateLabel(state).toLowerCase()).not.toMatch(
        /compliant|non-compliant|passed|failed|verdict/,
      );
    }
  });
});

describe("journey mapping", () => {
  it("exposes the six-step spine in order", () => {
    expect(JOURNEY_STEPS.map((step) => step.id)).toEqual([
      "shipment",
      "requirements",
      "evidence",
      "analysis",
      "review",
      "assessment",
    ]);
  });

  it("maps states to steps without implying compliance", () => {
    expect(journeyStepForState("created")).toBe("shipment");
    expect(journeyStepForState("applicability_determined")).toBe("requirements");
    expect(journeyStepForState("assessment_package_ready")).toBe("assessment");
    expect(journeyStepForState("unknown-state")).toBe("shipment");
  });

  it("marks the terminal state current with prior steps complete", () => {
    const statuses = journeyStepStatuses("assessment_package_ready");
    expect(statuses.assessment).toBe("current");
    expect(statuses.shipment).toBe("complete");
    expect(statuses.review).toBe("complete");
  });

  it("flags evidence-loop states as action-required", () => {
    expect(journeyStepStatuses("additional_evidence_requested").evidence).toBe(
      "action-required",
    );
    expect(journeyStepStatuses("reanalysis_required").analysis).toBe(
      "action-required",
    );
  });
});

describe("applicability presentation", () => {
  it("renders outcomes verbatim", () => {
    expect(applicabilityLabel("unknown")).toBe("unknown");
  });

  it("treats unknown as attention, never failure", () => {
    expect(applicabilityTone("unknown")).toBe("attention");
    expect(applicabilityTone("not_applicable")).toBe("muted");
    expect(applicabilityTone("applicable")).toBe("info");
  });
});
