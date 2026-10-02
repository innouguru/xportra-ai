import { describe, expect, it, afterEach } from "vitest";
import {
  emptyProfile,
  forgetShipment,
  listShipments,
  rememberShipment,
  shipmentDisplayName,
  type ShipmentEntry,
} from "./shipments";
import type { WorkflowRecord } from "../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: "44444444-4444-4444-4444-444444444444",
  state: "created",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

function entry(overrides: Partial<ShipmentEntry> = {}): ShipmentEntry {
  return {
    caseId: RECORD.case_id,
    shipmentId: RECORD.shipment_id,
    profile: {
      product: "Cocoa beans",
      origin: "Nigeria",
      destination: "Netherlands",
      quantity: "20",
      unit: "tonnes",
      shipmentDate: "2026-10-01",
    },
    record: RECORD,
    ...overrides,
  };
}

afterEach(() => {
  sessionStorage.clear();
});

describe("shipment registry", () => {
  it("starts empty and remembers shipments most-recent-first", () => {
    expect(listShipments()).toEqual([]);
    rememberShipment(entry());
    rememberShipment(entry({ caseId: "other-case", shipmentId: null }));
    const listed = listShipments();
    expect(listed.map((item) => item.caseId)).toEqual(["other-case", RECORD.case_id]);
  });

  it("refreshes an entry re-remembered under the same case", () => {
    rememberShipment(entry());
    rememberShipment(entry({ shipmentId: null }));
    const listed = listShipments();
    expect(listed).toHaveLength(1);
    expect(listed[0].shipmentId).toBeNull();
  });

  it("forgets one shipment without touching the others", () => {
    rememberShipment(entry());
    rememberShipment(entry({ caseId: "other-case", shipmentId: null }));
    forgetShipment("other-case");
    expect(listShipments().map((item) => item.caseId)).toEqual([RECORD.case_id]);
  });

  it("ignores corrupt or foreign storage content", () => {
    sessionStorage.setItem("xportra.shipments.v1", "not-json{{");
    expect(listShipments()).toEqual([]);
    sessionStorage.setItem(
      "xportra.shipments.v1",
      JSON.stringify([{ nope: true }, null, "x", entry()]),
    );
    expect(listShipments()).toHaveLength(1);
  });

  it("names shipments from the human profile, identifiers only as fallback", () => {
    expect(shipmentDisplayName(entry())).toBe("Cocoa beans · Nigeria → Netherlands");
    expect(shipmentDisplayName(entry({
      profile: emptyProfile(),
    }))).toBe("Shipment 44444444…");
    expect(
      shipmentDisplayName(entry({ profile: emptyProfile(), shipmentId: null })),
    ).toBe("Unbound shipment");
  });
});
