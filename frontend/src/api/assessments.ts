/**
 * Typed case-readiness endpoint.
 *
 * Transports caller-supplied case views and returns the
 * backend readiness report unchanged. Readiness is
 * computed server-side; nothing here interprets it.
 *
 * Covered routes:
 * - POST /compliance/assessments/case-readiness
 *   (member-readable)
 */

import { apiFetch, type AuthCredentials } from "./client";
import type { CaseReadiness } from "../types/api";

export function assessCaseReadiness(
  credentials: AuthCredentials,
  cases: Array<Record<string, unknown>>,
): Promise<CaseReadiness> {
  return apiFetch<CaseReadiness>(
    "/compliance/assessments/case-readiness",
    credentials,
    { method: "POST", body: { cases } },
  );
}
