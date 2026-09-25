import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { AnalysisReport } from "../types/api";

/**
 * In-memory holder for the latest analysis report plus the
 * cases that produced it.
 *
 * Deliberately NOT persisted to sessionStorage: reasoning
 * content and provenance stay in memory only. The workflow
 * record (identifiers + process state) is the resumable
 * artifact; a report can always be re-read by identity
 * through the stored report endpoint in a later pass.
 */
interface AnalysisState {
  report: AnalysisReport | null;
  cases: Array<Record<string, unknown>>;
  setAnalysis: (report: AnalysisReport, cases: Array<Record<string, unknown>>) => void;
  clear: () => void;
}

const AnalysisContext = createContext<AnalysisState | null>(null);

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [cases, setCases] = useState<Array<Record<string, unknown>>>([]);

  const setAnalysis = useCallback(
    (next: AnalysisReport, usedCases: Array<Record<string, unknown>>) => {
      setReport(next);
      setCases(usedCases);
    },
    [],
  );

  const clear = useCallback(() => {
    setReport(null);
    setCases([]);
  }, []);

  const value = useMemo(
    () => ({ report, cases, setAnalysis, clear }),
    [report, cases, setAnalysis, clear],
  );
  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis(): AnalysisState {
  const state = useContext(AnalysisContext);
  if (state === null) {
    throw new Error("useAnalysis must be used inside <AnalysisProvider>");
  }
  return state;
}
