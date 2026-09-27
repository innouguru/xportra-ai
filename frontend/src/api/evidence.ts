/**
 * Typed evidence endpoints.
 *
 * Reference recording registers a reference (title, type,
 * URI) that the backend records; file upload sends the
 * document bytes to `POST /compliance-evidence/uploads`
 * (base64 JSON transport, exactly the backend contract)
 * and download issues a short-lived signed URL via
 * `GET /compliance-evidence/{evidence_id}/download`.
 * Functions transport records and surface backend errors
 * unchanged. No compliance logic lives here.
 *
 * Covered routes (router.py + evidence_uploads.py):
 * - POST /compliance-evidence (201, member-allowed)
 * - POST /compliance-evidence/with-requirements (201, member-allowed)
 * - GET /compliance-evidence/{evidence_id} (member-readable)
 * - POST /compliance-evidence/uploads (201, member-allowed)
 * - GET /compliance-evidence/{evidence_id}/download (member-readable)
 */

import { apiFetch, type AuthCredentials } from "./client";
import type {
  EvidenceDownloadGrant,
  EvidenceRecord,
  EvidenceUploadPayload,
  EvidenceUploadResult,
} from "../types/api";

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

export interface UploadEvidenceFileInput {
  file: File;
  document_title?: string | null;
  document_type?: string | null;
  requirement_ids?: string[];
  workflow?: EvidenceUploadPayload["workflow"];
}

/**
 * Reads a user-selected file and uploads it through the
 * real backend upload endpoint. The backend remains
 * authoritative on type/size/content validation — the
 * client only encodes the bytes it was given.
 */
export async function uploadEvidenceFile(
  credentials: AuthCredentials,
  input: UploadEvidenceFileInput,
): Promise<EvidenceUploadResult> {
  const content_base64 = await fileToBase64(input.file);
  const payload: EvidenceUploadPayload = {
    filename: input.file.name,
    content_type: input.file.type || "application/octet-stream",
    content_base64,
  };
  if (input.document_title !== undefined) {
    payload.document_title = input.document_title;
  }
  if (input.document_type !== undefined) {
    payload.document_type = input.document_type;
  }
  if (input.requirement_ids !== undefined) {
    payload.requirement_ids = input.requirement_ids;
  }
  if (input.workflow !== undefined) {
    payload.workflow = input.workflow;
  }
  return apiFetch<EvidenceUploadResult>(
    "/compliance-evidence/uploads",
    credentials,
    { method: "POST", body: payload },
  );
}

/**
 * Requests an authorized download grant. The returned
 * signed URL is short-lived: callers must use it
 * immediately (open/navigate) and never persist it.
 */
export function fetchEvidenceDownload(
  credentials: AuthCredentials,
  evidenceId: string,
): Promise<EvidenceDownloadGrant> {
  return apiFetch<EvidenceDownloadGrant>(
    `/compliance-evidence/${encodeURIComponent(evidenceId)}/download`,
    credentials,
  );
}

/**
 * Encodes a File to base64 without data-URL prefixes.
 * Pure transport encoding — no validation happens here.
 */
export function fileToBase64(file: File): Promise<string> {
  return file.arrayBuffer().then((buffer) => {
    const bytes = new Uint8Array(buffer);
    const chunkSize = 0x8000;
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      const chunk = bytes.subarray(offset, offset + chunkSize);
      binary += String.fromCharCode(...chunk);
    }
    return btoa(binary);
  });
}
