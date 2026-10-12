import { afterEach, describe, expect, it, vi } from "vitest";
import {
  AUTH_CALLBACK_PATH,
  authCallbackUrl,
  getSupabaseClient,
  getSupabasePublicConfig,
  resetSupabaseClientForTests,
  safeReturnPath,
  supabaseConfigError,
} from "./supabaseClient";

afterEach(() => {
  vi.unstubAllEnvs();
  resetSupabaseClientForTests();
});

describe("getSupabasePublicConfig", () => {
  it("returns the public project configuration when both variables are set", () => {
    vi.stubEnv("VITE_SUPABASE_URL", "https://proj.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "public-anon-key");
    expect(getSupabasePublicConfig()).toEqual({
      url: "https://proj.supabase.co",
      anonKey: "public-anon-key",
    });
  });

  it("returns null when either variable is missing or blank", () => {
    vi.stubEnv("VITE_SUPABASE_URL", "https://proj.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "");
    expect(getSupabasePublicConfig()).toBeNull();
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "public-anon-key");
    vi.stubEnv("VITE_SUPABASE_URL", undefined as unknown as string);
    delete process.env.VITE_SUPABASE_URL;
    expect(getSupabasePublicConfig()).toBeNull();
  });

  it("describes the missing configuration without secrets", () => {
    const message = supabaseConfigError();
    expect(message).toMatch(/VITE_SUPABASE_URL/);
    expect(message).toMatch(/VITE_SUPABASE_ANON_KEY/);
  });
});

describe("getSupabaseClient", () => {
  it("returns null without configuration and caches the singleton", () => {
    vi.stubEnv("VITE_SUPABASE_URL", undefined as unknown as string);
    delete process.env.VITE_SUPABASE_URL;
    expect(getSupabaseClient()).toBeNull();
    expect(getSupabaseClient()).toBeNull();
  });

  it("builds one shared client when configured", () => {
    vi.stubEnv("VITE_SUPABASE_URL", "https://proj.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "public-anon-key");
    const first = getSupabaseClient();
    expect(first).not.toBeNull();
    expect(getSupabaseClient()).toBe(first);
  });
});

describe("authCallbackUrl", () => {
  it("targets the callback route on the given origin", () => {
    expect(authCallbackUrl("https://app.example.com/")).toBe(
      `https://app.example.com${AUTH_CALLBACK_PATH}`,
    );
  });
});

describe("safeReturnPath", () => {
  it("accepts allow-listed internal destinations", () => {
    expect(safeReturnPath("/dashboard")).toBe("/dashboard");
    expect(safeReturnPath("/shipments/abc/report")).toBe("/shipments/abc/report");
    expect(safeReturnPath("/workspace/evidence")).toBe("/workspace/evidence");
    expect(safeReturnPath("/start")).toBe("/start");
  });

  it("rejects external, protocol-relative, escaped, and unknown paths", () => {
    for (const hostile of [
      "https://evil.example.com/dashboard",
      "//evil.example.com/dashboard",
      "/\\evil.example.com",
      "/dashboard\\evil",
      "javascript:alert(1)",
      "/admin/secret",
      "/auth/callback?code=abc",
      "",
    ]) {
      expect(safeReturnPath(hostile)).toBe("/start");
    }
    expect(safeReturnPath(null)).toBe("/start");
    expect(safeReturnPath("%")).toBe("/start");
  });
});
