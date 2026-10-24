import { describe, expect, it, vi, afterEach } from "vitest";
import {
  getRegulatoryCandidate,
  getRegulatorySource,
  listRegulatorySources,
  listRequirementGovernanceFlags,
  listSourceGovernanceFlags,
  listSourceJobs,
  listStageBHistory,
  submitStageADecision,
  submitStageBDecision,
} from "./regulatory";
import type { AuthCredentials } from "./client";

const CREDENTIALS: AuthCredentials = { token: "tok", devTenantId: null };

type FetchCall = [string, RequestInit];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("regulatory API functions", () => {
  it("lists regulatory sources from the administration endpoint", async () => {
    const payload = { items: [], limit: 50, offset: 0, total: 0 };
    const spy = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const result = await listRegulatorySources(CREDENTIALS);
    const [url] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/regulatory/sources");
    expect(result).toEqual(payload);
  });

  it("fetches a source's ingestion jobs by source identity", async () => {
    const payload = { items: [], limit: 50, offset: 0, total: 0 };
    const spy = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await listSourceJobs(CREDENTIALS, "source-1");
    const [url] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/regulatory/sources/source-1/ingestion-jobs");
  });

  it("fetches source detail without inferring supersession", async () => {
    const source = {
      id: "s1",
      authority_id: "a1",
      jurisdiction: "EU",
      title: "T",
      version: null,
      status: "superseded",
      effective_date: null,
      publication_date: null,
      source_url: null,
      retrieval_timestamp: null,
      supersedes_source_id: "old",
      superseded_by_source_id: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const spy = vi.fn(async () => new Response(JSON.stringify(source), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const result = await getRegulatorySource(CREDENTIALS, "s1");
    const [url] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/regulatory/sources/s1");
    // The recorded supersession link is transported unchanged.
    expect(result.supersedes_source_id).toBe("old");
    expect(result.superseded_by_source_id).toBeNull();
  });

  it("encodes candidate identity in the detail path", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify({ id: "c/1" }), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await getRegulatoryCandidate(CREDENTIALS, "c/1");
    const [url] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/regulatory/candidates/c%2F1");
  });

  it("posts the Stage A decision with its rationale to the stage-a route", async () => {
    const stub = {
      id: "c1",
      requirement_id: "c1",
      source_id: "s1",
      stage_a_status: "verified",
      stage_a_reviewer_user_id: "u1",
      stage_a_reviewed_at: "2026-01-01T00:00:00Z",
      stage_a_rationale: "ok",
    };
    const spy = vi.fn(async () => new Response(JSON.stringify(stub), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const result = await submitStageADecision(CREDENTIALS, "c1", {
      stage_a_status: "verified",
      rationale: "Source traceability confirmed.",
    });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/regulatory/candidates/c1/stage-a");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      stage_a_status: "verified",
      rationale: "Source traceability confirmed.",
    });
    expect(result.stage_a_status).toBe("verified");
  });

  it("posts the Stage B decision to the distinct stage-b route", async () => {
    const stub = {
      id: "c1",
      requirement_id: "c1",
      source_id: "s1",
      stage_b_status: "approved",
      stage_b_reviewer_user_id: "u2",
      stage_b_reviewed_at: "2026-01-01T00:00:00Z",
      stage_b_rationale: "ok",
      stage_b_pilot_scope: "cocoa pilot",
    };
    const spy = vi.fn(async () => new Response(JSON.stringify(stub), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const result = await submitStageBDecision(CREDENTIALS, "c1", {
      stage_b_status: "approved",
      rationale: "Applies to pilot scope.",
      pilot_scope: "cocoa pilot",
      evidence_references: ["ev-1"],
    });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    // Distinct from the Stage A route — two independent review stages.
    expect(url).toBe("http://localhost:8000/regulatory/candidates/c1/stage-b");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      stage_b_status: "approved",
      rationale: "Applies to pilot scope.",
      pilot_scope: "cocoa pilot",
      evidence_references: ["ev-1"],
    });
    expect(result.stage_b_status).toBe("approved");
  });

  it("fetches Stage B decision history", async () => {
    const payload = { items: [], limit: 50, offset: 0, total: 0 };
    const spy = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await listStageBHistory(CREDENTIALS, "c1");
    const [url] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/regulatory/candidates/c1/stage-b/history");
  });

  it("fetches governance flags for a source", async () => {
    const payload = {
      items: [
        {
          id: "f1",
          requirement_id: "c1",
          trigger_source_id: "s1",
          trigger_type: "supersession",
          status: "pending_review",
          actor_user_id: "u1",
          rationale: "Source superseded.",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
    };
    const spy = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const flags = await listSourceGovernanceFlags(CREDENTIALS, "s1");
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/regulatory/sources/s1/governance-flags");
    expect(init.method).toBe("GET");
    expect(flags.items[0].status).toBe("pending_review");
    expect(flags.items[0].rationale).toBe("Source superseded.");
  });

  it("fetches governance flags for a requirement", async () => {
    const payload = { items: [], total: 0 };
    const spy = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await listRequirementGovernanceFlags(CREDENTIALS, "c1");
    const [url] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/regulatory/requirements/c1/governance-flags");
  });
});
