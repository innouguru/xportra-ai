/**
 * Typed workflow-use-case endpoints.
 *
 * One function per backend route, each delegating to the
 * centralized client. No compliance logic lives here:
 * functions transport records/DTOs and surface backend
 * errors unchanged.
 *
 * Covered routes (all POST, `action` = one use case):
 * - /compliance/workflows/start (201)
 * - /compliance/workflows/provide-information
 * - /compliance/workflows/note-evidence-pending
 * - /compliance/workflows/record-applicability
 * - /compliance/workflows/submit-for-review
 * - /compliance/workflows/request-additional-evidence
 * - /compliance/workflows/supply-evidence
 * - /compliance/workflows/status
 * - /compliance/workflows/history
 * - /compliance/workflows/is-closed
 * - /compliance/workflows/analyze
 * - /compliance/workflows/finalize (201)
 * - /compliance/workflows/package
 * - GET /compliance/reports/{report_id}
 * - POST /compliance/assessments/applicability
 * - POST /compliance/assessments/case-readiness
 */

import { apiFetch, type AuthCredentials } from "./client";
import type {
  AnalysisReport,
  ApplicabilityResponse,
  FinalPackage,
  FinalizeWorkflowResponse,
  HistoryResponse,
  WorkflowActionResponse,
  WorkflowRecord,
  WorkflowSummary,
} from "../types/api";

export interface StartWorkflowInput {
  case_id: string;
  shipment_id?: string | null;
}

export function startWorkflow(
  credentials: AuthCredentials,
  input: StartWorkflowInput,
): Promise<WorkflowActionResponse> {
  return apiFetch<WorkflowActionResponse>("/compliance/workflows/start", credentials, {
    method: "POST",
    body: input,
  });
}

function actionWithRecord(
  path: string,
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
  extraBody: Record<string, unknown> = {},
): Promise<WorkflowActionResponse> {
  return apiFetch<WorkflowActionResponse>(path, credentials, {
    method: "POST",
    body: { workflow, ...extraBody },
  });
}

export function provideInformation(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
): Promise<WorkflowActionResponse> {
  return actionWithRecord(
    "/compliance/workflows/provide-information",
    credentials,
    workflow,
  );
}

export function noteEvidencePending(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
): Promise<WorkflowActionResponse> {
  return actionWithRecord(
    "/compliance/workflows/note-evidence-pending",
    credentials,
    workflow,
  );
}

export function recordApplicability(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
): Promise<WorkflowActionResponse> {
  return actionWithRecord(
    "/compliance/workflows/record-applicability",
    credentials,
    workflow,
  );
}

export function submitForReview(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
): Promise<WorkflowActionResponse> {
  return actionWithRecord(
    "/compliance/workflows/submit-for-review",
    credentials,
    workflow,
  );
}

export function supplyEvidence(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
  evidenceId: string,
  requirementId?: string | null,
): Promise<WorkflowActionResponse> {
  return actionWithRecord(
    "/compliance/workflows/supply-evidence",
    credentials,
    workflow,
    {
      evidence_id: evidenceId,
      ...(requirementId ? { requirement_id: requirementId } : {}),
    },
  );
}

export function requestAdditionalEvidence(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
  requirementIds: string[],
): Promise<WorkflowActionResponse> {
  return actionWithRecord(
    "/compliance/workflows/request-additional-evidence",
    credentials,
    workflow,
    { requirement_ids: requirementIds },
  );
}

export interface ApplicabilityInput {
  requirements: Array<Record<string, unknown>>;
  exporter?: Record<string, unknown> | null;
  product?: Record<string, unknown> | null;
  destination?: Record<string, unknown> | null;
  actor_role?: string | null;
  business_characteristics?: Record<string, unknown> | null;
}

export function determineApplicability(
  credentials: AuthCredentials,
  input: ApplicabilityInput,
): Promise<ApplicabilityResponse> {
  return apiFetch<ApplicabilityResponse>(
    "/compliance/assessments/applicability",
    credentials,
    { method: "POST", body: input },
  );
}

export function fetchWorkflowStatus(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
): Promise<WorkflowSummary> {
  return apiFetch<WorkflowSummary>("/compliance/workflows/status", credentials, {
    method: "POST",
    body: { workflow },
  });
}

export function finalizeStoredPackage(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
): Promise<FinalizeWorkflowResponse> {
  return apiFetch<FinalizeWorkflowResponse>(
    "/compliance/workflows/finalize",
    credentials,
    { method: "POST", body: { workflow } },
  );
}

export function fetchStoredPackage(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
): Promise<FinalPackage> {
  return apiFetch<FinalPackage>("/compliance/workflows/package", credentials, {
    method: "POST",
    body: { workflow },
  });
}

export function fetchStoredReport(
  credentials: AuthCredentials,
  reportId: string,
): Promise<AnalysisReport> {
  return apiFetch<AnalysisReport>(
    `/compliance/reports/${encodeURIComponent(reportId)}`,
    credentials,
  );
}

export function fetchWorkflowHistory(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
): Promise<HistoryResponse> {
  return apiFetch<HistoryResponse>("/compliance/workflows/history", credentials, {
    method: "POST",
    body: { workflow },
  });
}
