import { describe, expect, it, vi, afterEach } from "vitest";
import { fetchEvidence, recordEvidence } from "./evidence";
import type { AuthCredentials } from "./client";

const CREDENTIALS: AuthCredentials = { token: "tok", devTenantId: null };

type FetchCall = [string, RequestInit];

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubJson(body: unknown, status = 200) {
  const spy = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("evidence API functions", () => {
  it("records a bare reference against the recording route", async () => {
    const spy = stubJson({ id: "e1" }, 201);
    await recordEvidence(CREDENTIALS, {
      document_title: "Phyto certificate",
      document_type: "certificate",
      file_reference_or_uri: "registry://NG-2024-118",
    });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance-evidence");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["document_title"]).toBe("Phyto certificate");
    expect(body).not.toHaveProperty("requirement_ids");
  });

  it("records with requirement links only when supplied", async () => {
    const spy = stubJson({ id: "e1" }, 201);
    await recordEvidence(CREDENTIALS, {
      document_title: "T",
      document_type: "certificate",
      file_reference_or_uri: "uri://x",
      requirement_ids: ["44444444-4444-4444-4444-444444444444"],
    });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance-evidence/with-requirements");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["requirement_ids"]).toEqual(["44444444-4444-4444-4444-444444444444"]);
  });

  it("treats an empty requirement list as a bare record, not a linked one", async () => {
    const spy = stubJson({ id: "e1" }, 201);
    await recordEvidence(CREDENTIALS, {
      document_title: "T",
      document_type: "certificate",
      file_reference_or_uri: "uri://x",
      requirement_ids: [],
    });
    const [url] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance-evidence");
  });

  it("fetches evidence by identity with no body", async () => {
    const spy = stubJson({ id: "e1" });
    await fetchEvidence(CREDENTIALS, "e1-id");
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance-evidence/e1-id");
    expect(init.method).toBe("GET");
  });
});
