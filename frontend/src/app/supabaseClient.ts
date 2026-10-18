import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Shared Supabase client for frontend authentication (R-10.10).
 *
 * Single home for the public Supabase configuration, the client
 * singleton, the PKCE callback destination, and the safe internal
 * return-path allowlist. Only public client identifiers are read
 * here (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`); backend
 * secrets must never appear in frontend code or `VITE_*` variables.
 */

export const SUPABASE_URL_ENV = "VITE_SUPABASE_URL";
export const SUPABASE_ANON_KEY_ENV = "VITE_SUPABASE_ANON_KEY";

/** PKCE callback route, registered in `App` ahead of the catch-all. */
export const AUTH_CALLBACK_PATH = "/auth/callback";

/** Password-recovery destination, registered in `App` ahead of the catch-all. */
export const PASSWORD_RESET_PATH = "/reset-password";

export interface SupabasePublicConfig {
  url: string;
  anonKey: string;
}

type EnvRecord = Record<string, string | undefined>;

export function getSupabasePublicConfig(
  env: EnvRecord = import.meta.env as unknown as EnvRecord,
): SupabasePublicConfig | null {
  const url = env[SUPABASE_URL_ENV]?.trim();
  const anonKey = env[SUPABASE_ANON_KEY_ENV]?.trim();
  if (!url || !anonKey) {
    return null;
  }
  return { url, anonKey };
}

export function supabaseConfigError(): string {
  return (
    "Sign-in is not configured for this build. " +
    `Set ${SUPABASE_URL_ENV} and ${SUPABASE_ANON_KEY_ENV} in the hosting ` +
    "environment and rebuild the frontend."
  );
}

let cachedClient: SupabaseClient | null | undefined;

export function getSupabaseClient(): SupabaseClient | null {
  if (cachedClient !== undefined) {
    return cachedClient;
  }
  const config = getSupabasePublicConfig();
  if (config === null) {
    cachedClient = null;
    return cachedClient;
  }
  cachedClient = createClient(config.url, config.anonKey, {
    auth: {
      // PKCE is required by R-10.10; the installed client defaults to
      // implicit, so this is set explicitly rather than assumed.
      flowType: "pkce",
      // The callback route exchanges the code explicitly via
      // `exchangeCodeForSession`; automatic URL detection stays off
      // so the code is never consumed twice.
      detectSessionInUrl: false,
      persistSession: true,
      autoRefreshToken: true,
    },
  });
  return cachedClient;
}

/** Test-only seam: forget the cached singleton between cases. */
export function resetSupabaseClientForTests(): void {
  cachedClient = undefined;
}

/** Absolute PKCE redirect destination for magic-link emails. */
export function authCallbackUrl(origin: string = window.location.origin): string {
  return `${origin.replace(/\/+$/, "")}${AUTH_CALLBACK_PATH}`;
}

/** Absolute PKCE redirect destination for password-recovery emails. */
export function passwordResetUrl(origin: string = window.location.origin): string {
  return `${origin.replace(/\/+$/, "")}${PASSWORD_RESET_PATH}`;
}

/** Internal route prefixes a post-sign-in return path may target. */
const SAFE_RETURN_PREFIXES = [
  "/dashboard",
  "/shipments",
  "/workspace",
  "/start",
  "/settings",
  "/session",
];

/**
 * Accept only safe internal return paths. Anything else — external
 * URLs, protocol-relative paths, escapes, or unknown routes —
 * falls back to `/start`. Query strings survive only when the path
 * itself is allow-listed.
 */
export function safeReturnPath(value: string | null | undefined): string {
  if (!value) {
    return "/start";
  }
  let decoded: string;
  try {
    decoded = decodeURIComponent(value);
  } catch {
    return "/start";
  }
  if (
    !decoded.startsWith("/") ||
    decoded.startsWith("//") ||
    decoded.includes("\\") ||
    /[\s]/.test(decoded)
  ) {
    return "/start";
  }
  const pathname = decoded.split("?")[0].split("#")[0];
  const allowed = SAFE_RETURN_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  return allowed ? decoded : "/start";
}
