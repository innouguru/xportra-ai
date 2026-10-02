import { describe, expect, it, vi } from "vitest";
import {
  describeShipment,
  greetingForHour,
  loadDashboard,
  openShipment,
  partitionDashboard,
  RECENT_LIMIT,
  type DashboardShipment,
} from "./dashboard";
import type { ShipmentEntry } from "../../lib/shipments";
import type { WorkflowRecord } from "../../types/api";

/**
 * Phase 10.8C mapping contract.
 *
 * Fixtures below are test-only registry entries.
 * Every label must derive from stored profile /
 * process state / evidence and round counts —
 * never invented backend facts, never technical
 * state names as user language.
 */

function entry({
  state,
  record: recordOverride,
  ...rest
}: Omit<Partial<ShipmentEntry>, "record"> & {
  state: string;
  record?: Partial<WorkflowRecord>;
}): ShipmentEntry {
  const record: WorkflowRecord = {
    id: "11111111-1111-1111-1111-111111111111",
    tenant_id: "22222222-2222-2222-2222-222222222222",
    case_id: "33333333-3333-3333-3333-333333333333",
    shipment_id: null,
    state,
    rounds: [],
    supplied_evidence_ids: [],
    open_requirements: [],
    ...recordOverride,
  };
  return {
    caseId: record.case_id,
    shipmentId: null,
    profile: {
      product: "Cocoa",
      origin: "Lagos",
      destination: "Rotterdam",
      quantity: "",
      unit: "",
      shipmentDate: "",
    },
    record,
    ...rest,
  };
}

describe("greeting", () => {
  it("follows the local time of day", () => {
    expect(greetingForHour(8)).toBe("Good morning");
    expect(greetingForHour(11)).toBe("Good morning");
    expect(greetingForHour(12)).toBe("Good afternoon");
    expect(greetingForHour(17)).toBe("Good afternoon");
    expect(greetingForHour(18)).toBe("Good evening");
    expect(greetingForHour(23)).toBe("Good evening");
  });
});

describe("shipment description", () => {
  it("titles cards from the human profile, never raw identifiers", () => {
    const described = describeShipment(entry({ state: "evidence_pending" }));
    expect(described.title).toBe("Cocoa · Lagos → Rotterdam");
    expect(described.title).not.toContain("33333333");
  });

  it("marks early states incomplete with a continuation action", () => {
    for (const state of ["created", "information_provided"]) {
      const described = describeShipment(entry({ state }));
      expect(described.attention).toMatch(/incomplete/i);
      expect(described.action).toEqual({
        label: "Continue",
        destination: `/shipments/${described.entry.caseId}`,
      });
      expect(described.complete).toBe(false);
    }
  });

  it("asks for a document only when none is supplied", () => {
    const empty = describeShipment(entry({ state: "evidence_pending" }));
    expect(empty.attention).toMatch(/document needed/i);
    expect(empty.action).toEqual({ label: "Upload document", destination: "/workspace/evidence" });

    const supplied = describeShipment(
      entry({ state: "evidence_pending", record: { supplied_evidence_ids: ["e1"] } as Partial<WorkflowRecord> }),
    );
    expect(supplied.attention).toBeNull();
    expect(supplied.statusLabel).toBe("Still checking");
  });

  it("routes explicit evidence and review requests to real destinations", () => {
    expect(describeShipment(entry({ state: "additional_evidence_requested" })).action.destination).toBe(
      "/workspace/evidence",
    );
    expect(describeShipment(entry({ state: "review_required" })).action).toEqual({
      label: "Review",
      destination: "/workspace/review",
    });
    expect(describeShipment(entry({ state: "analysis_available" })).action.destination).toBe(
      "/workspace/review",
    );
    expect(describeShipment(entry({ state: "reanalysis_required" })).action.destination).toBe(
      "/workspace/analysis",
    );
  });

  it("treats completed shipments as history with a report link", () => {
    const withoutRounds = describeShipment(entry({ state: "assessment_package_ready" }));
    expect(withoutRounds.complete).toBe(true);
    expect(withoutRounds.attention).toBeNull();
    expect(withoutRounds.statusLabel).toBe("Completed");
    // Even without rounds, completed shipments open the
    // read-only historical report — never the workspace.
    expect(withoutRounds.action).toEqual({
      label: "View report",
      destination: "/shipments/33333333-3333-3333-3333-333333333333/report",
    });

    const withRounds = describeShipment(
      entry({
        state: "assessment_package_ready",
        record: {
          rounds: [{ round_index: 0, report_id: "r1", analysis_ids: [], trace_ids: [], input_fingerprints: [] }],
        } as Partial<WorkflowRecord>,
      }),
    );
    expect(withRounds.action).toEqual({ label: "View report", destination: "/shipments/33333333-3333-3333-3333-333333333333/report" });
  });

  it("renders unknown states honestly without inventing urgency", () => {
    const described = describeShipment(entry({ state: "some_future_state" }));
    expect(described.attention).toBeNull();
    expect(described.statusLabel).toBe("Still checking");
  });

  it("never exposes technical state names as user language", () => {
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
      const described = describeShipment(entry({ state }));
      const text = `${described.statusLabel} ${described.attention ?? ""} ${described.action.label}`;
      expect(text).not.toContain(state);
    }
  });
});

describe("dashboard partition", () => {
  function describedStates(states: string[]): DashboardShipment[] {
    return states.map((state, index) =>
      describeShipment(entry({ state, caseId: `case-${index}` })),
    );
  }

  it("collects attention work and limits recent to five without duplicates", () => {
    expect(RECENT_LIMIT).toBe(5);
    const model = partitionDashboard(
      describedStates([
        "created",
        "evidence_pending",
        "applicability_determined",
        "analysis_available",
        "assessment_package_ready",
        "evidence_pending",
      ]),
    );
    expect(model.attention.length).toBeGreaterThan(0);
    expect(model.recent.length).toBeLessThanOrEqual(5);
    const attentionIds = new Set(model.attention.map((item) => item.entry.caseId));
    for (const item of model.recent) {
      expect(attentionIds.has(item.entry.caseId)).toBe(false);
    }
  });

  it("counts active shipments and attention honestly", () => {
    const model = partitionDashboard(
      describedStates(["created", "evidence_pending", "assessment_package_ready"]),
    );
    expect(model.activeCount).toBe(2);
    expect(model.attentionCount).toBe(2);
  });
});

describe("dashboard loading", () => {
  it("opens shipments through the existing workspace mechanism", () => {
    const target = entry({ state: "created" });
    const setRecord = vi.fn();
    const navigate = vi.fn();
    openShipment(target, setRecord, navigate, "/workspace");
    expect(setRecord).toHaveBeenCalledWith(target.record);
    expect(navigate).toHaveBeenCalledWith("/workspace");
  });

  it("reads an empty registry as an empty dashboard", () => {
    window.sessionStorage.clear();
    const load = loadDashboard();
    expect(load.status).toBe("ready");
    if (load.status === "ready") {
      expect(load.model.entries).toEqual([]);
    }
  });
});
