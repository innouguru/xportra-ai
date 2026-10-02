import { describe, expect, it } from "vitest";
import {
  EMPTY_FILTER,
  distinctProfileValues,
  hasShipmentDates,
  queryArchive,
} from "./shipmentsArchive";
import type { ShipmentEntry } from "../../lib/shipments";
import type { WorkflowRecord } from "../../types/api";

/**
 * Archive query contract (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * Fixtures are test-only registry entries.
 * Search/filter/sort must use stored fields
 * only and keep the active → incomplete →
 * completed order stable.
 */

function entry(
  caseId: string,
  product: string,
  destination: string,
  state: string,
  shipmentDate = "",
): ShipmentEntry {
  const record: WorkflowRecord = {
    id: `id-${caseId}`,
    tenant_id: "tenant-1",
    case_id: caseId,
    shipment_id: null,
    state,
    rounds: [],
    supplied_evidence_ids: [],
    open_requirements: [],
  };
  return {
    caseId,
    shipmentId: null,
    profile: { product, origin: "Lagos", destination, quantity: "", unit: "", shipmentDate },
    record,
  };
}

const ENTRIES = [
  entry("case-done", "Cocoa", "Rotterdam", "assessment_package_ready", "2026-01-10"),
  entry("case-new", "Sesame", "Accra", "created"),
  entry("case-wait", "Cocoa", "India", "evidence_pending"),
];

describe("archive query", () => {
  it("orders active before incomplete before completed, stably", () => {
    const withActive = [
      ...ENTRIES,
      entry("case-active", "Ginger", "Canada", "evidence_pending", ""),
    ];
    // evidence_pending without supplied documents is attention text,
    // but still an active (in-progress) group member.
    const titles = queryArchive(withActive, EMPTY_FILTER).map((item) => item.title);
    expect(titles).toEqual([
      "Cocoa · Lagos → India",
      "Ginger · Lagos → Canada",
      "Sesame · Lagos → Accra",
      "Cocoa · Lagos → Rotterdam",
    ]);
  });

  it("searches product, destination, and identity text", () => {
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, query: "cocoa" })).toHaveLength(2);
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, query: "accra" })[0].title).toContain("Sesame");
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, query: "case-done" })).toHaveLength(1);
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, query: "nope" })).toHaveLength(0);
  });

  it("filters by user-facing status groups", () => {
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, status: "completed" })).toHaveLength(1);
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, status: "incomplete" })).toHaveLength(1);
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, status: "active" })).toHaveLength(1);
  });

  it("filters by exact product, destination, and date", () => {
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, product: "Cocoa" })).toHaveLength(2);
    expect(
      queryArchive(ENTRIES, { ...EMPTY_FILTER, destination: "Rotterdam" })[0].entry.caseId,
    ).toBe("case-done");
    expect(queryArchive(ENTRIES, { ...EMPTY_FILTER, date: "2026-01-10" })).toHaveLength(1);
  });

  it("combines search and filters", () => {
    const result = queryArchive(ENTRIES, {
      ...EMPTY_FILTER,
      query: "cocoa",
      status: "completed",
    });
    expect(result).toHaveLength(1);
    expect(result[0].entry.caseId).toBe("case-done");
  });

  it("never exposes technical states in user text", () => {
    for (const item of queryArchive(ENTRIES, EMPTY_FILTER)) {
      const text = `${item.title} ${item.statusLabel} ${item.attention ?? ""}`;
      expect(text).not.toContain("assessment_package_ready");
      expect(text).not.toContain("evidence_pending");
    }
  });
});

describe("archive facets", () => {
  it("lists distinct products and destinations", () => {
    expect(distinctProfileValues(ENTRIES, (item) => item.profile.product)).toEqual(["Cocoa", "Sesame"]);
    expect(distinctProfileValues(ENTRIES, (item) => item.profile.destination)).toEqual([
      "Accra",
      "India",
      "Rotterdam",
    ]);
  });

  it("detects whether any date filter is honest", () => {
    expect(hasShipmentDates(ENTRIES)).toBe(true);
    expect(hasShipmentDates([entry("x", "A", "B", "created")])).toBe(false);
  });
});
