/**
 * Typed evidence-recording endpoints.
 *
 * There is NO file-upload endpoint: intake registers a
 * reference (title, type, URI) that the backend records.
 * Functions transport records and surface backend errors
 * unchanged. No compliance logic lives here.
 *
 * Covered routes (router.py):
 * - POST /compliance-evidence (201, member-allowed)
 * - POST /compliance-evidence/with-requirements (201, member-allowed)
 * - GET /compliance-evidence/{evidence_id} (member-readable)
 */

import { apiFetch, type AuthCredentials } from "./client";
import type { EvidenceRecord } from "../types/api";

export interface RecordEvidenceInput {
  document_title: string;
  document_type: string;
  file_reference_or_uri: string;
  requirement_ids?: string[];
}

export function recordEvidence(
  credentials: AuthCredentials,
  input: RecordEvidenceInput,
): Promise<EvidenceRecord> {
  const { requirement_ids, ...rest } = input;
  if (requirement_ids !== undefined && requirement_ids.length > 0) {
    return apiFetch<EvidenceRecord>(
      "/compliance-evidence/with-requirements",
      credentials,
      { method: "POST", body: { ...rest, requirement_ids } },
    );
  }
  return apiFetch<EvidenceRecord>("/compliance-evidence", credentials, {
    method: "POST",
    body: rest,
  });
}

export function fetchEvidence(
  credentials: AuthCredentials,
  evidenceId: string,
): Promise<EvidenceRecord> {
  return apiFetch<EvidenceRecord>(
    `/compliance-evidence/${encodeURIComponent(evidenceId)}`,
    credentials,
  );
}
