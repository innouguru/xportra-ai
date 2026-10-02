import { describe, expect, it } from "vitest";
import {
  containsTechnicalState,
  describeWorkspace,
} from "./workspace";
import type { ShipmentEntry } from "../../lib/shipments";
import type { AnalysisFinding, AnalysisReport, WorkflowRecord } from "../../types/api";

/**
 * Phase 10.8E translation contract.
 *
 * Fixtures are test-only. Every user-facing
 * string must derive from stored fields and
 * must never carry raw workflow states,
 * scores, or invented facts.
 */

const PROFILE = {
  product: "Cocoa",
  origin: "Lagos",
  destination: "Rotterdam",
  quantity: "",
  unit: "",
  shipmentDate: "",
};

function record(state: string, extra?: Partial<WorkflowRecord>): WorkflowRecord {
  return {
    id: "id-1",
    tenant_id: "tenant-1",
    case_id: "case-1",
    shipment_id: null,
    state,
    rounds: [],
    supplied_evidence_ids: [],
    open_requirements: [],
    ...extra,
  };
}

function entry(state: string, extra?: Partial<WorkflowRecord>): ShipmentEntry {
  const workflow = record(state, extra);
  return { caseId: "case-1", shipmentId: null, profile: { ...PROFILE }, record: workflow };
}

function finding(assessment: string, requirementId = "r1"): AnalysisFinding {
  return {
    analysis_id: `a-${requirementId}`,
    requirement_id: requirementId,
    requirement_text: `Requirement ${requirementId}`,
    applicability: "applicable",
    assessment,
    explanation: "Required by the destination authority.",
    uncertainty: "determined",
    uncertainty_explanation: "",
    evidence_sufficiency: "insufficient",
    sufficiency_explanation: "",
    contradiction_state: "none",
    missing_information: ["Upload the certificate."],
    supporting_evidence: [],
    conflicting_evidence: [],
    knowledge_references: [],
    sources: [],
    missing_items: [],
  };
}

function report(caseId: string, assessments: string[]): AnalysisReport {
  return {
    report_id: "rep-1",
    case_id: caseId,
    counts: {},
    requirements_with_missing_information: [],
    uncertain_requirement_ids: [],
    requirements_with_conflicting_evidence: [],
    conflicting_evidence_count: 0,
    findings: assessments.map((assessment, index) => finding(assessment, `r${index + 1}`)),
  };
}

function userTextOf(state: string, extra?: Partial<WorkflowRecord>, rep: AnalysisReport | null = null): string {
  const target = entry(state, extra);
  const model = describeWorkspace(target.record, target, rep);
  const reqTexts =
    model.requirements.kind === "findings"
      ? model.requirements.items.map((item) => `${item.title} ${item.statusLabel} ${item.explanation ?? ""}`).join(" ")
      : "";
  return [
    model.title,
    model.statusLabel,
    model.briefing,
    model.briefingDetail ?? "",
    model.primaryAction?.label ?? "",
    reqTexts,
  ].join(" ");
}

describe("workspace briefing", () => {
  it("answers plainly per state without technical names", () => {
    expect(describeWorkspace(record("evidence_pending"), entry("evidence_pending"), null).briefing).toBe(
      "Xportra needs a document from you.",
    );
    expect(
      describeWorkspace(record("created"), entry("created"), null).briefing,
    ).toBe("This shipment is just getting started.");
    expect(
      describeWorkspace(record("assessment_package_ready"), entry("assessment_package_ready"), null)
        .briefing,
    ).toBe("Everything Xportra could check is complete.");
  });

  it("surfaces findings attention only on review states", () => {
    const rep = report("case-1", ["not_satisfied", "satisfied"]);
    expect(
      describeWorkspace(record("review_required"), entry("review_required"), rep).briefing,
    ).toBe("One requirement needs your attention.");
    // Same report, earlier state: no invented urgency.
    expect(
      describeWorkspace(record("evidence_pending", { supplied_evidence_ids: ["e1"] }), entry("evidence_pending"), rep)
        .briefing,
    ).toBe("We’re still checking this shipment.");
  });

  it("never leaks technical state names across all states", () => {
    const states = [
      "created",
      "information_provided",
      "evidence_pending",
      "applicability_determined",
      "analysis_available",
      "review_required",
      "additional_evidence_requested",
      "reanalysis_required",
      "assessment_package_ready",
    ];
    for (const state of states) {
      expect(containsTechnicalState(userTextOf(state))).toBe(false);
    }
    expect(containsTechnicalState("evidence_pending")).toBe(true);
  });
});

describe("workspace actions", () => {
  it("routes the single primary action through existing destinations", () => {
    const cases: Array<[string, string]> = [
      ["created", "/workspace/info"],
      ["evidence_pending", "/workspace/evidence"],
      ["additional_evidence_requested", "/workspace/evidence"],
      ["applicability_determined", "/workspace/requirements"],
      ["analysis_available", "/workspace/review"],
      ["review_required", "/workspace/review"],
      ["reanalysis_required", "/workspace/analysis"],
    ];
    for (const [state, destination] of cases) {
      expect(describeWorkspace(record(state), entry(state), null).primaryAction?.destination).toBe(
        destination,
      );
    }
  });

  it("offers no mutating action without a stored report on terminal records", () => {
    const bare = describeWorkspace(
      record("assessment_package_ready"),
      entry("assessment_package_ready"),
      null,
    );
    expect(bare.readOnly).toBe(true);
    expect(bare.ready).toBe(true);
    expect(bare.primaryAction).toBeNull();
    expect(bare.statusLabel).toBe("Ready");

    const withRounds = describeWorkspace(
      record("assessment_package_ready", {
        rounds: [{ round_index: 0, report_id: "rep-9", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
      }),
      entry("assessment_package_ready"),
      null,
    );
    expect(withRounds.primaryAction).toEqual({
      label: "View report",
      destination: "/shipments/case-1/report",
    });
  });
});

describe("workspace requirements", () => {
  it("maps assessments to the approved vocabulary", () => {
    const model = describeWorkspace(
      record("review_required"),
      entry("review_required"),
      report("case-1", ["satisfied", "not_satisfied", "unknown", "other"]),
    );
    expect(model.requirements.kind).toBe("findings");
    if (model.requirements.kind !== "findings") {
      throw new Error("expected findings");
    }
    expect(model.requirements.items.map((item) => item.statusLabel)).toEqual([
      "Addressed",
      "Needs attention",
      "Still checking",
      "Waiting for you",
    ]);
    expect(model.progress).toEqual({ addressed: 1, total: 4 });
  });

  it("ignores reports from other shipments", () => {
    const model = describeWorkspace(
      record("review_required", { open_requirements: ["o1", "o2"] }),
      entry("review_required"),
      report("case-other", ["satisfied"]),
    );
    expect(model.requirements).toEqual({ kind: "open-count", count: 2 });
    expect(model.progress).toBeNull();
  });

  it("falls back honestly without findings", () => {
    const open = describeWorkspace(
      record("additional_evidence_requested", { open_requirements: ["o1"] }),
      entry("additional_evidence_requested"),
      null,
    );
    expect(open.requirements).toEqual({ kind: "open-count", count: 1 });

    const none = describeWorkspace(record("created"), entry("created"), null);
    expect(none.requirements).toEqual({ kind: "none" });
    expect(none.progress).toBeNull();
  });

  it("keeps unknown profile values explicit, never empty-known", () => {
    const model = describeWorkspace(record("created"), entry("created"), null);
    const quantity = model.details.find((row) => row.label === "Quantity");
    expect(quantity?.value).toBeNull();
    expect(model.details.find((row) => row.label === "Product")?.value).toBe("Cocoa");
  });
});
