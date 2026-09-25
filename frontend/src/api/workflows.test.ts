import { describe, expect, it, vi, afterEach } from "vitest";
import {
  determineApplicability,
  fetchWorkflowStatus,
  noteEvidencePending,
  provideInformation,
  recordApplicability,
  startWorkflow,
} from "./workflows";
import type { AuthCredentials } from "./client";
import type { WorkflowRecord } from "../types/api";

type FetchCall = [string, RequestInit];

const CREDENTIALS: AuthCredentials = { token: "tok", devTenantId: null };

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "created",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubJson(body: unknown, status = 200) {
  const spy = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("workflow API functions", () => {
  it("starts a workflow against the verified route", async () => {
    const spy = stubJson({ workflow: RECORD, summary: {} }, 201);
    await startWorkflow(CREDENTIALS, {
      case_id: RECORD.case_id,
      shipment_id: null,
    });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/start");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      case_id: RECORD.case_id,
      shipment_id: null,
    });
  });

  it("posts the client-held record for progression steps", async () => {
    const spy = stubJson({ workflow: RECORD, summary: {} });
    await provideInformation(CREDENTIALS, RECORD);
    await noteEvidencePending(CREDENTIALS, RECORD);
    await recordApplicability(CREDENTIALS, RECORD);
    const urls = spy.mock.calls.map(
      (call) => (call as unknown as FetchCall)[0],
    );
    expect(urls).toEqual([
      "http://localhost:8000/compliance/workflows/provide-information",
      "http://localhost:8000/compliance/workflows/note-evidence-pending",
      "http://localhost:8000/compliance/workflows/record-applicability",
    ]);
    for (const call of spy.mock.calls) {
      const request = (call as unknown as FetchCall)[1];
      expect(JSON.parse(request.body as string)).toEqual({ workflow: RECORD });
    }
  });

  it("fetches status summaries without inventing fields", async () => {
    stubJson({ workflow_id: RECORD.id, state: "created" });
    const summary = await fetchWorkflowStatus(CREDENTIALS, RECORD);
    expect(summary.state).toBe("created");
  });

  it("passes applicability facts straight through", async () => {
    const spy = stubJson({ counts: {}, results: [] });
    await determineApplicability(CREDENTIALS, {
      requirements: [{ id: "r1", requirement_text: "File form X." }],
      exporter: { country_of_registration: "NG" },
      product: null,
      destination: { country_code: "NL" },
      actor_role: null,
      business_characteristics: null,
    });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/assessments/applicability");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["requirements"]).toHaveLength(1);
    expect(body["destination"]).toEqual({ country_code: "NL" });
  });
});
