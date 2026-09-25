import { describe, expect, it, vi, afterEach } from "vitest";
import { assessCaseReadiness } from "./assessments";
import type { AuthCredentials } from "./client";

const CREDENTIALS: AuthCredentials = { token: "tok", devTenantId: null };

type FetchCall = [string, RequestInit];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("assessments API function", () => {
  it("posts caller-supplied cases and returns the report unchanged", async () => {
    const report = {
      readiness_state: "partially_ready",
      required_information: 2,
      known_information: 1,
      missing_information_count: 1,
      gaps: [],
      missing_evidence_requirements: [],
      unknown_applicability_requirements: [],
      unknown_assessment_requirements: [],
    };
    const spy = vi.fn(async () => new Response(JSON.stringify(report), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const cases = [{ id: "case-1", tenant_id: "t-1" }];
    const result = await assessCaseReadiness(CREDENTIALS, cases);
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/assessments/case-readiness");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ cases });
    expect(result).toEqual(report);
  });
});
