import { describe, expect, it, vi, afterEach } from "vitest";
import {
  fetchEvidence,
  fetchEvidenceDownload,
  fileToBase64,
  recordEvidence,
  uploadEvidenceFile,
} from "./evidence";
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

describe("evidence upload API functions", () => {
  function pdfFile(): File {
    return new File(["%PDF-1.4 fake"], "certificate.pdf", {
      type: "application/pdf",
    });
  }

  it("encodes file bytes as plain base64", async () => {
    const file = new File(["abc"], "a.pdf", { type: "application/pdf" });
    await expect(fileToBase64(file)).resolves.toBe("YWJj");
  });

  it("posts the exact backend upload contract", async () => {
    const spy = stubJson({ evidence_id: "e9" }, 201);
    await uploadEvidenceFile(CREDENTIALS, { file: pdfFile() });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance-evidence/uploads");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["filename"]).toBe("certificate.pdf");
    expect(body["content_type"]).toBe("application/pdf");
    expect(typeof body["content_base64"]).toBe("string");
    expect(body["content_base64"]).not.toContain("data:");
    expect(body).not.toHaveProperty("tenant_id");
    expect(body).not.toHaveProperty("document_title");
    expect(body).not.toHaveProperty("workflow");
  });

  it("forwards optional title, links, and the workflow record", async () => {
    const spy = stubJson({ evidence_id: "e9" }, 201);
    const workflow = { id: "w1" };
    await uploadEvidenceFile(CREDENTIALS, {
      file: pdfFile(),
      document_title: "Phyto certificate",
      requirement_ids: ["44444444-4444-4444-4444-444444444444"],
      workflow: workflow as never,
    });
    const [, init] = spy.mock.calls[0] as unknown as FetchCall;
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["document_title"]).toBe("Phyto certificate");
    expect(body["requirement_ids"]).toEqual([
      "44444444-4444-4444-4444-444444444444",
    ]);
    expect(body["workflow"]).toEqual({ id: "w1" });
  });

  it("requests a download grant with no body", async () => {
    const spy = stubJson({ download_url: "https://signed/x" });
    const grant = await fetchEvidenceDownload(CREDENTIALS, "e9");
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance-evidence/e9/download");
    expect(init.method).toBe("GET");
    expect(grant.download_url).toBe("https://signed/x");
  });
});
