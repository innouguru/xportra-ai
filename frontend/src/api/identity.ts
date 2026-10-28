/**
 * Current-account identity API (Phase: account identity display).
 *
 * Thin wrapper over the centralized client. The request carries no user
 * or tenant id — identity, membership, and tenant scope are resolved
 * server-side from the bearer token. Returns only the identity fields
 * the authenticated shell needs to display who is signed in and which
 * organization they are working under.
 */

import { apiFetch, type AuthCredentials } from "./client";
import type { Identity } from "../types/api";

export function fetchIdentity(
  credentials: AuthCredentials,
  signal?: AbortSignal,
): Promise<Identity> {
  return apiFetch<Identity>("/me", credentials, {
    method: "GET",
    signal,
  });
}
