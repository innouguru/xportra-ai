/**
 * Backend contract types for Xportra AI.
 *
 * These mirror `xportra/api/schemas.py` and the application DTOs.
 * They describe wire shapes only — the frontend MUST NOT derive
 * compliance conclusions from them beyond direct presentation.
 *
 * Backend state vocabularies (verbatim, never renamed):
 * - workflow state: created | information_provided | evidence_pending |
 *   applicability_determined | analysis_available | review_required |
 *   additional_evidence_requested | reanalysis_required |
 *   assessment_package_ready
 * - applicability outcome: applicable | not_applicable | unknown
 * - assessment: satisfied | not_satisfied | unknown
 */

/** Client-held workflow record (server keeps no session). */
export interface WorkflowRecord {
  id: string;
  tenant_id: string;
  case_id: string;
  shipment_id: string | null;
  state: string;
  rounds: WorkflowRound[];
  supplied_evidence_ids: string[];
  open_requirements: string[];
}

export interface WorkflowRound {
  round_index: number;
  report_id: string;
  analysis_ids: string[];
  trace_ids: string[];
  input_fingerprints: string[];
}

export interface WorkflowSummary {
  workflow_id: string;
  tenant_id: string;
  case_id: string;
  shipment_id: string | null;
  state: string;
  is_closed: boolean;
  round_count: number;
  rounds: Array<{
    round_index: number;
    report_id: string;
    analysis_ids: string[];
    trace_ids: string[];
  }>;
  supplied_evidence_ids: string[];
  open_requirements: string[];
}

export interface WorkflowActionResponse {
  workflow: WorkflowRecord;
  summary: WorkflowSummary;
}

export interface ApplicabilityResult {
  requirement_id: string;
  outcome: "applicable" | "not_applicable" | "unknown";
  reason: string;
}

export interface ApplicabilityResponse {
  counts: Record<string, number>;
  results: ApplicabilityResult[];
}

/** Recorded evidence artifact (reference only — never file bytes). */
export interface EvidenceRecord {
  id: string;
  tenant_id: string;
  source_id: string | null;
  document_title: string;
  document_type: string;
  file_reference_or_uri: string;
  content_hash: string | null;
  status: string;
  uploaded_at: string;
  created_at: string;
  updated_at: string;
}

/** One evidence-coverage gap, rendered verbatim. */
export interface ReadinessGap {
  requirement_id: string;
  kind: string;
  reason: string;
}

/** Case-readiness report: information coverage, not a verdict. */
export interface CaseReadiness {
  readiness_state: string;
  required_information: number;
  known_information: number;
  missing_information_count: number;
  gaps: ReadinessGap[];
  missing_evidence_requirements: string[];
  unknown_applicability_requirements: string[];
  unknown_assessment_requirements: string[];
}

/** One per-requirement analysis finding, rendered as received. */
export interface AnalysisFinding {
  analysis_id: string;
  requirement_id: string;
  requirement_text: string;
  applicability: string;
  assessment: string;
  explanation: string;
  uncertainty: string;
  uncertainty_explanation: string;
  evidence_sufficiency: string;
  sufficiency_explanation: string;
  contradiction_state: string;
  missing_information: string[];
  supporting_evidence: Array<Record<string, unknown>>;
  conflicting_evidence: Array<Record<string, unknown>>;
  knowledge_references: Array<Record<string, unknown>>;
  sources: Array<Record<string, unknown>>;
  missing_items: Array<Record<string, unknown>>;
}

/** Analysis report: ordered findings plus server-computed counts. */
export interface AnalysisReport {
  report_id: string;
  case_id: string;
  counts: Record<string, number>;
  requirements_with_missing_information: string[];
  uncertain_requirement_ids: string[];
  requirements_with_conflicting_evidence: string[];
  conflicting_evidence_count: number;
  findings: AnalysisFinding[];
}

export interface AnalyzeWorkflowResponse {
  workflow: WorkflowRecord;
  report: AnalysisReport;
}

/** Stored final assessment package (terminal, by reference). */
export interface FinalPackage {
  workflow_id: string;
  tenant_id: string;
  case_id: string;
  shipment_id: string | null;
  state: string;
  round_count: number;
  open_requirements: string[];
  report: AnalysisReport;
  decision_summary: Record<string, unknown> | null;
}

export interface FinalizeWorkflowResponse {
  workflow: WorkflowRecord;
  package: FinalPackage;
}

/** One grouped history entry (projection order, no timestamps). */
export interface HistoryEntry {
  sequence: number;
  kind: string;
  detail: string;
  references: Array<Record<string, string>>;
}

/** Workflow history projection as received (identifiers only). */
export interface HistoryResponse {
  workflow_id: string;
  tenant_id: string;
  case_id: string;
  shipment_id: string | null;
  state: string;
  entries: HistoryEntry[];
  supplied_evidence_ids: string[];
  open_requirements: string[];
  round_count: number;
  latest_report_id: string | null;
  decision_summary_present: boolean;
  readiness: Record<string, unknown> | null;
  final_package: Record<string, unknown> | null;
}

/** Readiness reason from a not-ready/stale 409 details payload. */
export interface ReadinessReason {
  code: string;
  detail: string;
}

/** Backend error envelope: {"error": {"code", "message", ...}}. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
