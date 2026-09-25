/**
 * Typed analysis endpoint.
 *
 * Transports the client-held workflow record plus
 * caller-supplied case views; the backend routes first
 * runs vs re-runs and returns the updated record with
 * the report. No retrieval, reasoning, or verdict logic
 * lives here.
 *
 * Covered routes (member may NOT run analysis —
 * RUN_COMPLIANCE_ANALYSIS is owner-only):
 * - POST /compliance/workflows/analyze
 */

import { apiFetch, type AuthCredentials } from "./client";
import type { AnalyzeWorkflowResponse, WorkflowRecord } from "../types/api";

export interface RunAnalysisInput {
  cases: Array<Record<string, unknown>>;
  mode?: "semantic" | "lexical" | "hybrid";
  max_context_characters?: number;
  top_k?: number | null;
  candidate_pool?: number | null;
  decision_summary?: Record<string, unknown> | null;
}

export function runAnalysis(
  credentials: AuthCredentials,
  workflow: WorkflowRecord,
  input: RunAnalysisInput,
): Promise<AnalyzeWorkflowResponse> {
  return apiFetch<AnalyzeWorkflowResponse>(
    "/compliance/workflows/analyze",
    credentials,
    {
      method: "POST",
      body: {
        workflow,
        cases: input.cases,
        ...(input.mode !== undefined ? { mode: input.mode } : {}),
        ...(input.max_context_characters !== undefined
          ? { max_context_characters: input.max_context_characters }
          : {}),
        ...(input.top_k !== undefined && input.top_k !== null
          ? { top_k: input.top_k }
          : {}),
        ...(input.candidate_pool !== undefined && input.candidate_pool !== null
          ? { candidate_pool: input.candidate_pool }
          : {}),
        ...(input.decision_summary !== undefined
          ? { decision_summary: input.decision_summary }
          : {}),
      },
    },
  );
}
