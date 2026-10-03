import { useEffect, useRef, useState } from "react";
import { fetchStoredReport } from "../api/workflows";
import type { AnalysisReport, WorkflowRecord } from "../types/api";
import { useAnalysis } from "./AnalysisContext";
import { useAuth } from "./AuthContext";
import { useWorkflow } from "./WorkflowContext";

/**
 * Shared persisted-report rehydration.
 *
 * The analysis report lives in the in-memory
 * `AnalysisContext` but is persisted server-side;
 * after a reload the workflow record may reference
 * rounds whose report is no longer in memory. This
 * hook resolves the effective report with one
 * precedence and no second rendering path:
 *
 * 1. the in-memory report (never refetched),
 * 2. the latest recorded round's report, fetched once
 *    through the existing stored-report endpoint and
 *    adopted into the context,
 * 3. genuinely absent (no rounds, no report).
 *
 * Nothing is duplicated into browser persistence:
 * only identifiers already on the workflow record
 * are used. A fetch in flight never clobbers a newer
 * in-memory report adopted meanwhile.
 */

export type StoredReportStatus = "ready" | "loading" | "empty" | "error";

export interface StoredReport {
  report: AnalysisReport | null;
  status: StoredReportStatus;
  error: unknown;
}

export function latestStoredReportId(record: WorkflowRecord | null): string | null {
  const rounds = record?.rounds ?? [];
  if (rounds.length === 0) {
    return null;
  }
  return rounds[rounds.length - 1].report_id;
}

export function useStoredReport(): StoredReport {
  const auth = useAuth();
  const { record } = useWorkflow();
  const { report, cases, setAnalysis } = useAnalysis();
  const [fetched, setFetched] = useState<AnalysisReport | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  const inMemoryId = report?.report_id ?? null;
  const storedId = latestStoredReportId(record);

  const liveRef = useRef({ report, cases });
  liveRef.current = { report, cases };

  useEffect(() => {
    if (inMemoryId !== null) {
      return;
    }
    if (storedId === null) {
      return;
    }
    if (fetched?.report_id === storedId) {
      return;
    }
    let cancelled = false;
    setPending(true);
    setError(null);
    fetchStoredReport(auth, storedId)
      .then((loaded) => {
        if (cancelled) {
          return;
        }
        setFetched(loaded);
        const live = liveRef.current;
        if ((live.report?.report_id ?? null) !== loaded.report_id) {
          setAnalysis(loaded, live.cases);
        }
      })
      .catch((fetchError: unknown) => {
        if (!cancelled) {
          setError(fetchError);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPending(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inMemoryId, storedId, fetched]);

  const effective =
    report ?? (fetched?.report_id === storedId ? fetched : null);
  if (effective !== null) {
    return { report: effective, status: "ready", error: null };
  }
  if (error !== null) {
    return { report: null, status: "error", error };
  }
  if (pending) {
    return { report: null, status: "loading", error: null };
  }
  return { report: null, status: "empty", error: null };
}
