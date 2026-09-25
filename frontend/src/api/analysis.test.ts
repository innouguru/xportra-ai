import { describe, expect, it, vi, afterEach } from "vitest";
import { runAnalysis } from "./analysis";
import type { AuthCredentials } from "./client";
import type { WorkflowRecord } from "../types/api";

const CREDENTIALS: AuthCredentials = { token: "tok", devTenantId: null };

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "applicability_determined",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

type FetchCall = [string, RequestInit];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("analysis API function", () => {
  it("posts the workflow record with caller-supplied cases", async () => {
    const spy = vi.fn(async () =>
      new Response(JSON.stringify({ workflow: RECORD, report: { report_id: "r1" } }), {
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", spy);
    const cases = [{ id: "case-1", tenant_id: RECORD.tenant_id }];
    const response = await runAnalysis(CREDENTIALS, RECORD, { cases });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/analyze");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["workflow"]).toEqual(RECORD);
    expect(body["cases"]).toEqual(cases);
    expect(response.report.report_id).toBe("r1");
  });

  it("forwards optional retrieval controls only when set", async () => {
    const spy = vi.fn(async () =>
      new Response(JSON.stringify({ workflow: RECORD, report: {} }), { status: 200 }),
    );
    vi.stubGlobal("fetch", spy);
    await runAnalysis(CREDENTIALS, RECORD, {
      cases: [{ id: "case-1" }],
      mode: "hybrid",
      max_context_characters: 4000,
    });
    const [, init] = spy.mock.calls[0] as unknown as FetchCall;
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["mode"]).toBe("hybrid");
    expect(body["max_context_characters"]).toBe(4000);
    expect(body).not.toHaveProperty("top_k");
    expect(body).not.toHaveProperty("candidate_pool");
  });
});
