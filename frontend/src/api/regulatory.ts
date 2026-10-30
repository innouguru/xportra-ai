/**
 * Typed regulatory administration endpoints.
 *
 * Responses are rendered verbatim: statuses, supersession
 * relationships, extraction outcomes, and governance flags are shown
 * exactly as the backend records them. Nothing here infers
 * supersession, freshness, publication, or exporter applicability.
 *
 * Covered routes (all require global staff grants server-side):
 * - GET  /regulatory/authorities                       (GRANT_MANAGE)
 * - POST  /regulatory/sources                       (GRANT_MANAGE)
 * - GET  /regulatory/sources                       (GRANT_MANAGE)
 * - GET  /regulatory/sources/{id}                  (GRANT_MANAGE)
 * - GET  /regulatory/sources/{id}/artifacts        (GRANT_MANAGE)
 * - GET  /regulatory/sources/{id}/ingestion-jobs   (GRANT_MANAGE)
 * - GET  /regulatory/sources/{id}/candidates       (GRANT_MANAGE)
 * - GET  /regulatory/candidates/{id}               (GRANT_MANAGE)
 * - POST /regulatory/candidates/{id}/stage-a       (STAGE_A_VERIFY)
 * - GET  /regulatory/candidates/{id}/stage-a       (STAGE_A_VERIFY)
 * - GET  /regulatory/candidates/{id}/stage-a/history (STAGE_A_VERIFY)
 * - POST /regulatory/candidates/{id}/stage-b       (STAGE_B_APPROVE)
 * - GET  /regulatory/candidates/{id}/stage-b       (STAGE_B_APPROVE)
 * - GET  /regulatory/candidates/{id}/stage-b/history (STAGE_B_APPROVE)
 * - GET  /regulatory/sources/{id}/governance-flags (GRANT_MANAGE)
 * - GET  /regulatory/requirements/{id}/governance-flags (GRANT_MANAGE)
 */

import { apiFetch, type AuthCredentials } from "./client";

export interface RegulatorySource {
  id: string;
  authority_id: string;
  jurisdiction: string;
  title: string;
  version: string | null;
  status: string;
  effective_date: string | null;
  publication_date: string | null;
  source_url: string | null;
  retrieval_timestamp: string | null;
  supersedes_source_id: string | null;
  superseded_by_source_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Payload for registering a new regulatory source. */
export interface RegulatorySourceCreateRequest {
  authority_id: string;
  jurisdiction: string;
  title: string;
  version?: string | null;
  status?: string;
  effective_date?: string | null;
  publication_date?: string | null;
  source_url?: string | null;
}

/** A regulatory authority record, used to populate the authority selector. */
export interface RegulatoryAuthority {
  id: string;
  name: string;
  jurisdiction: string;
  authority_type: string;
  status: string;
}

/** Valid source statuses recognized by the backend. */
export const REGULATORY_SOURCE_STATUSES = [
  "draft",
  "active",
  "superseded",
  "withdrawn",
  "archived",
] as const;

export interface RegulatoryArtifact {
  id: string;
  source_id: string;
  content_hash: string;
  content_length: number;
  content_type: string;
  acquisition_channel: string;
  acquired_at: string;
  status: string;
  source_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegulatoryIngestionJob {
  id: string;
  artifact_id: string;
  source_id: string;
  status: string;
  attempt_number: number;
  started_at: string | null;
  completed_at: string | null;
  error_details: string | null;
  parser_version: string;
  actor_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegulatoryCandidate {
  id: string;
  source_id: string;
  artifact_id: string;
  normalized_document_id: string | null;
  requirement_text: string;
  requirement_type: string;
  source_location: Record<string, unknown>;
  position: number;
  actor: string | null;
  status: string;
  extraction_outcome: string;
  parser_version: string | null;
  manual_entry: boolean;
  reviewer_user_id: string | null;
  reviewed_at: string | null;
  ingestion_job_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegulatoryStageAState {
  id: string;
  requirement_id: string;
  source_id: string | null;
  stage_a_status: string;
  stage_a_reviewer_user_id: string | null;
  stage_a_reviewed_at: string | null;
  stage_a_rationale: string | null;
}

export interface RegulatoryStageAHistoryEntry {
  id: string;
  requirement_id: string;
  stage_a_status: string;
  reviewer_user_id: string | null;
  reviewed_at: string | null;
  rationale: string;
  source_id: string | null;
  created_at: string;
}

export interface RegulatoryStageBState {
  id: string;
  requirement_id: string;
  source_id: string | null;
  stage_b_status: string;
  stage_b_reviewer_user_id: string | null;
  stage_b_reviewed_at: string | null;
  stage_b_rationale: string | null;
  stage_b_pilot_scope: string | null;
}

export interface RegulatoryStageBHistoryEntry {
  id: string;
  requirement_id: string;
  stage_b_status: string;
  reviewer_user_id: string | null;
  reviewed_at: string | null;
  rationale: string;
  pilot_scope: string | null;
  /**
   * Backend records `evidence_references` as a JSONB list of reference
   * objects (`list[dict]` in `RegulatoryStageBReviewRequest`); entries are
   * rendered verbatim by the page, never interpreted into applicability.
   */
  evidence_references: Array<string | Record<string, unknown>>;
  same_person_exception: boolean;
  exception_authorizer_user_id: string | null;
  exception_authorization_ref: string | null;
  exception_justification: string | null;
  created_at: string;
}

export interface RegulatoryGovernanceFlag {
  id: string;
  requirement_id: string | null;
  trigger_source_id: string | null;
  trigger_type: string;
  status: string;
  actor_user_id: string | null;
  rationale: string;
  created_at: string;
  updated_at: string;
}

export function listRegulatorySources(
  credentials: AuthCredentials,
): Promise<{ items: RegulatorySource[]; total: number }> {
  return apiFetch("/regulatory/sources", credentials);
}

export function listRegulatoryAuthorities(
  credentials: AuthCredentials,
): Promise<RegulatoryAuthority[]> {
  return apiFetch("/regulatory/authorities", credentials);
}

export function registerRegulatorySource(
  credentials: AuthCredentials,
  payload: RegulatorySourceCreateRequest,
): Promise<RegulatorySource> {
  return apiFetch("/regulatory/sources", credentials, {
    method: "POST",
    body: payload,
  });
}

export function getRegulatorySource(
  credentials: AuthCredentials,
  sourceId: string,
): Promise<RegulatorySource> {
  return apiFetch(`/regulatory/sources/${encodeURIComponent(sourceId)}`, credentials);
}

export function listSourceArtifacts(
  credentials: AuthCredentials,
  sourceId: string,
): Promise<{ items: RegulatoryArtifact[]; total: number }> {
  return apiFetch(`/regulatory/sources/${encodeURIComponent(sourceId)}/artifacts`, credentials);
}

export function listSourceJobs(
  credentials: AuthCredentials,
  sourceId: string,
): Promise<{ items: RegulatoryIngestionJob[]; total: number }> {
  return apiFetch(`/regulatory/sources/${encodeURIComponent(sourceId)}/ingestion-jobs`, credentials);
}

export function listSourceCandidates(
  credentials: AuthCredentials,
  sourceId: string,
): Promise<{ items: RegulatoryCandidate[]; total: number }> {
  return apiFetch(`/regulatory/sources/${encodeURIComponent(sourceId)}/candidates`, credentials);
}

export function getRegulatoryCandidate(
  credentials: AuthCredentials,
  candidateId: string,
): Promise<RegulatoryCandidate> {
  return apiFetch(`/regulatory/candidates/${encodeURIComponent(candidateId)}`, credentials);
}

export function getCandidateStageA(
  credentials: AuthCredentials,
  candidateId: string,
): Promise<RegulatoryStageAState> {
  return apiFetch(`/regulatory/candidates/${encodeURIComponent(candidateId)}/stage-a`, credentials);
}

export function listStageAHistory(
  credentials: AuthCredentials,
  candidateId: string,
): Promise<{ items: RegulatoryStageAHistoryEntry[]; total: number }> {
  return apiFetch(`/regulatory/candidates/${encodeURIComponent(candidateId)}/stage-a/history`, credentials);
}

export function submitStageADecision(
  credentials: AuthCredentials,
  candidateId: string,
  payload: {
    stage_a_status: "verified" | "rejected" | "clarification_required";
    rationale: string;
  },
): Promise<RegulatoryStageAState> {
  return apiFetch(
    `/regulatory/candidates/${encodeURIComponent(candidateId)}/stage-a`,
    credentials,
    { method: "POST", body: payload },
  );
}

export function getCandidateStageB(
  credentials: AuthCredentials,
  candidateId: string,
): Promise<RegulatoryStageBState> {
  return apiFetch(`/regulatory/candidates/${encodeURIComponent(candidateId)}/stage-b`, credentials);
}

export function listStageBHistory(
  credentials: AuthCredentials,
  candidateId: string,
): Promise<{ items: RegulatoryStageBHistoryEntry[]; total: number }> {
  return apiFetch(`/regulatory/candidates/${encodeURIComponent(candidateId)}/stage-b/history`, credentials);
}

export function submitStageBDecision(
  credentials: AuthCredentials,
  candidateId: string,
  payload: {
    stage_b_status: "approved" | "rejected" | "clarification_required";
    rationale: string;
    /** Mandatory server-side (`RegulatoryStageBReviewRequest`); never null. */
    pilot_scope: string;
  },
): Promise<RegulatoryStageBState> {
  return apiFetch(
    `/regulatory/candidates/${encodeURIComponent(candidateId)}/stage-b`,
    credentials,
    { method: "POST", body: payload },
  );
}

export function listSourceGovernanceFlags(
  credentials: AuthCredentials,
  sourceId: string,
): Promise<{ items: RegulatoryGovernanceFlag[]; total: number }> {
  return apiFetch(`/regulatory/sources/${encodeURIComponent(sourceId)}/governance-flags`, credentials);
}

export function listRequirementGovernanceFlags(
  credentials: AuthCredentials,
  requirementId: string,
): Promise<{ items: RegulatoryGovernanceFlag[]; total: number }> {
  return apiFetch(
    `/regulatory/requirements/${encodeURIComponent(requirementId)}/governance-flags`,
    credentials,
  );
}
