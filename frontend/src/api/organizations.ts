import { apiFetch, type AuthCredentials } from "./client";
import type {
  OrganizationRegistrationInput,
  OrganizationRegistrationResult,
} from "../types/api";

/**
 * Organization registration API (Phase 10.11).
 *
 * Thin wrapper over the centralized client — no raw `fetch` here.
 * The request carries organization profile input only; identity,
 * tenant, and role are resolved server-side from the bearer token.
 * A `409 organization_already_registered` surfaces as an `ApiError`
 * so callers can treat "already a member" as a benign outcome.
 */
export function registerOrganization(
  credentials: AuthCredentials,
  input: OrganizationRegistrationInput,
  signal?: AbortSignal,
): Promise<OrganizationRegistrationResult> {
  return apiFetch<OrganizationRegistrationResult>("/organizations", credentials, {
    method: "POST",
    body: input,
    signal,
  });
}
