import { describe, expect, it, vi, afterEach } from "vitest";
import {
  fetchShipmentDetail,
  fetchShipmentList,
  toShipmentEntry,
  type ServerShipmentItem,
} from "./shipments";
import type { AuthCredentials } from "./client";
import { listShipments } from "../lib/shipments";

const CREDENTIALS: AuthCredentials = { token: "tok", devTenantId: null };

const RECORD = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: "44444444-4444-4444-4444-444444444444",
  state: "evidence_pending",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

const ITEM: ServerShipmentItem = {
  shipment_id: "44444444-4444-4444-4444-444444444444",
  case_id: "33333333-3333-3333-3333-333333333333",
  product: "Cocoa beans",
  origin_country: "Nigeria",
  destination_country: "Netherlands",
  quantity: "20",
  unit: "tonnes",
  shipment_date: "2026-11-01",
  status: "bound",
  created_at: "2026-10-07T00:00:00+00:00",
  updated_at: "2026-10-07T00:00:00+00:00",
  workflow: {
    workflow_id: "11111111-1111-1111-1111-111111111111",
    state: "evidence_pending",
    is_closed: false,
    supplied_evidence_count: 0,
    open_requirements_count: 0,
    round_count: 0,
    latest_report_id: null,
  },
  workflow_count: 1,
  workflow_record: RECORD,
};

afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

function stubJson(body: unknown, status = 200) {
  const spy = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("shipment discovery API", () => {
  it("adapts server items into the existing entry shape", () => {
    const entry = toShipmentEntry(ITEM);
    expect(entry).toEqual({
      caseId: ITEM.case_id,
      shipmentId: ITEM.shipment_id,
      profile: {
        product: "Cocoa beans",
        origin: "Nigeria",
        destination: "Netherlands",
        quantity: "20",
        unit: "tonnes",
        shipmentDate: "2026-11-01",
      },
      record: RECORD,
    });
  });

  it("maps absent optionals to blank profile fields", () => {
    const entry = toShipmentEntry({
      ...ITEM,
      quantity: null,
      unit: null,
      shipment_date: null,
      workflow: null,
      workflow_record: null,
    });
    expect(entry.profile.quantity).toBe("");
    expect(entry.profile.shipmentDate).toBe("");
    expect(entry.record).toBeNull();
  });

  it("fetches the paginated list and refreshes the device cache", async () => {
    const spy = stubJson({ shipments: [ITEM], limit: 20, offset: 0, total: 1 });
    const entries = await fetchShipmentList(CREDENTIALS);
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/compliance/shipments");
    expect(init.method).toBe("GET");
    expect(entries).toHaveLength(1);
    expect(entries[0].caseId).toBe(ITEM.case_id);
    // Cache refreshed so mutation continuity and suggestions keep working.
    expect(listShipments()).toHaveLength(1);
  });

  it("passes pagination and status filters through", async () => {
    const spy = stubJson({ shipments: [], limit: 5, offset: 5, total: 0 });
    await fetchShipmentList(CREDENTIALS, { limit: 5, offset: 5, status: "completed" });
    const [url] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(
      "http://localhost:8000/compliance/shipments?limit=5&offset=5&status=completed",
    );
  });

  it("fetches one shipment by server identity", async () => {
    const spy = stubJson(ITEM);
    const entry = await fetchShipmentDetail(CREDENTIALS, ITEM.shipment_id);
    const [url] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`http://localhost:8000/compliance/shipments/${ITEM.shipment_id}`);
    expect(entry?.caseId).toBe(ITEM.case_id);
  });

  it("returns null for unknown or cross-tenant identities", async () => {
    stubJson({ error: { code: "not_found" } }, 404);
    const entry = await fetchShipmentDetail(CREDENTIALS, "no-such-shipment");
    expect(entry).toBeNull();
  });
});
