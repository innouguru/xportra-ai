import { describe, expect, it, vi, afterEach } from "vitest";
import {
  fetchStoredPackage,
  fetchStoredReport,
  fetchWorkflowHistory,
  finalizeStoredPackage,
  requestAdditionalEvidence,
} from "./workflows";
import type { AuthCredentials } from "./client";
import type { WorkflowRecord } from "../types/api";

const CREDENTIALS: AuthCredentials = { token: "tok", devTenantId: null };

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "review_required",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

type FetchCall = [string, RequestInit];

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubJson(body: unknown, status = 200) {
  const spy = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("stored-path API functions", () => {
  it("requests additional evidence with requirement IDs", async () => {
    const spy = stubJson({ workflow: RECORD, summary: {} });
    await requestAdditionalEvidence(CREDENTIALS, RECORD, ["req-1", "req-2"]);
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/request-additional-evidence");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["requirement_ids"]).toEqual(["req-1", "req-2"]);
    expect(body["workflow"]).toEqual(RECORD);
  });

  it("finalizes with only the workflow record", async () => {
    const spy = stubJson({ workflow: RECORD, package: { workflow_id: RECORD.id } });
    await finalizeStoredPackage(CREDENTIALS, RECORD);
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/finalize");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ workflow: RECORD });
  });

  it("reads the stored package with only the workflow record", async () => {
    const spy = stubJson({ workflow_id: RECORD.id });
    await fetchStoredPackage(CREDENTIALS, RECORD);
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/package");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ workflow: RECORD });
  });

  it("reads a stored report by identity over GET", async () => {
    const spy = stubJson({ report_id: "r1" });
    await fetchStoredReport(CREDENTIALS, "report-id-1");
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/reports/report-id-1");
    expect(init.method).toBe("GET");
  });

  it("reads workflow history with only the workflow record", async () => {
    const spy = stubJson({ entries: [] });
    await fetchWorkflowHistory(CREDENTIALS, RECORD);
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/history");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ workflow: RECORD });
  });
});
