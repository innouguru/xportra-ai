import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { FinalPackage } from "../types/api";

/**
 * In-memory holder for the latest final assessment package.
 *
 * Deliberately NOT persisted to sessionStorage: the package
 * (report, findings, provenance, carried summary) is
 * re-readable at any time through the stored package
 * endpoint for the current workflow record. Only the
 * workflow record itself is the resumable artifact.
 */
interface AssessmentState {
  package: FinalPackage | null;
  setPackage: (pkg: FinalPackage | null) => void;
  clear: () => void;
}

const AssessmentContext = createContext<AssessmentState | null>(null);

export function AssessmentProvider({ children }: { children: ReactNode }) {
  const [pkg, setPkg] = useState<FinalPackage | null>(null);

  const setPackage = useCallback((next: FinalPackage | null) => {
    setPkg(next);
  }, []);

  const clear = useCallback(() => setPackage(null), [setPackage]);

  const value = useMemo(
    () => ({ package: pkg, setPackage, clear }),
    [pkg, setPackage, clear],
  );
  return <AssessmentContext.Provider value={value}>{children}</AssessmentContext.Provider>;
}

export function useAssessment(): AssessmentState {
  const state = useContext(AssessmentContext);
  if (state === null) {
    throw new Error("useAssessment must be used inside <AssessmentProvider>");
  }
  return state;
}
