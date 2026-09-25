import { describe, expect, it, vi, afterEach } from "vitest";
import {
  ApiError,
  apiBaseUrl,
  apiFetch,
  buildAuthHeaders,
  userFacingErrorMessage,
} from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function stubFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  const spy = vi.fn(handler);
  vi.stubGlobal("fetch", spy);
  return spy;
}

type FetchCall = [string, RequestInit];

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("buildAuthHeaders", () => {
  it("prefers bearer tokens over the dev header", () => {
    expect(buildAuthHeaders({ token: "abc", devTenantId: "dev-1" })).toEqual({
      Authorization: "Bearer abc",
    });
  });

  it("uses the development header only when no token exists", () => {
    expect(buildAuthHeaders({ token: null, devTenantId: "dev-1" })).toEqual({
      "X-Development-Tenant-ID": "dev-1",
    });
  });

  it("sends no identity headers when unconfigured", () => {
    expect(buildAuthHeaders({ token: null, devTenantId: null })).toEqual({});
  });
});

describe("apiBaseUrl", () => {
  it("defaults to the local backend and strips trailing slashes", () => {
    vi.stubEnv("VITE_API_BASE_URL", undefined as unknown as string);
    delete process.env.VITE_API_BASE_URL;
    expect(apiBaseUrl()).toBe("http://localhost:8000");
  });
});

describe("apiFetch", () => {
  it("sends JSON with auth headers and parses the body", async () => {
    const spy = stubFetch(async () => jsonResponse(200, { ok: true }));
    const result = await apiFetch<{ ok: boolean }>(
      "/compliance/workflows/status",
      { token: "tok", devTenantId: null },
      { method: "POST", body: { workflow: {} } },
    );
    expect(result).toEqual({ ok: true });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/compliance/workflows/status");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Authorization"]).toBe("Bearer tok");
    expect(JSON.parse(init.body as string)).toEqual({ workflow: {} });
  });

  it("maps backend error envelopes to ApiError without inventing meaning", async () => {
    stubFetch(async () =>
      jsonResponse(409, { error: { code: "terminal_workflow", message: "Closed." } }),
    );
    const failure = await apiFetch("/x", { token: "t", devTenantId: null }).catch(
      (error: unknown) => error,
    );
    expect(failure).toBeInstanceOf(ApiError);
    const apiError = failure as ApiError;
    expect(apiError.status).toBe(409);
    expect(apiError.code).toBe("terminal_workflow");
    expect(apiError.message).toBe("Closed.");
  });

  it("falls back safely on non-JSON error bodies", async () => {
    stubFetch(async () => new Response("boom", { status: 500 }));
    const failure = await apiFetch("/x", { token: null, devTenantId: null }).catch(
      (error: unknown) => error,
    );
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(500);
  });

  it("maps network failure to an unreachable error, not a verdict", async () => {
    stubFetch(async () => {
      throw new TypeError("fetch failed");
    });
    const failure = await apiFetch("/x", { token: null, devTenantId: null }).catch(
      (error: unknown) => error,
    );
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).code).toBe("network_unreachable");
  });
});

describe("userFacingErrorMessage", () => {
  it("preserves backend semantics per code", () => {
    expect(userFacingErrorMessage(new ApiError(401, "authentication_required", "x"))).toMatch(
      /sign in/i,
    );
    expect(userFacingErrorMessage(new ApiError(403, "permission_denied", "x"))).toMatch(
      /role/i,
    );
    expect(userFacingErrorMessage(new ApiError(409, "terminal_workflow", "x"))).toMatch(
      /final/i,
    );
    expect(userFacingErrorMessage(new ApiError(409, "stale_analysis", "x"))).toMatch(
      /newer analysis/i,
    );
  });

  it("never invents compliance meaning", () => {
    for (const code of ["not_ready", "invalid_transition", "tenant_mismatch", "not_found"]) {
      const message = userFacingErrorMessage(new ApiError(409, code, "detail")).toLowerCase();
      expect(message).not.toMatch(/compliant|non-compliant|failed|verdict|score/);
    }
  });

  it("handles non-API failures", () => {
    expect(userFacingErrorMessage(new Error("down"))).toMatch(/connection/i);
    expect(userFacingErrorMessage("weird")).toMatch(/something went wrong/i);
  });
});
