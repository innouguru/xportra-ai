import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { WorkflowRecord } from "../types/api";

const STORAGE_KEY = "xportra.workflow-record.v1";

/**
 * Client-held workflow record.
 *
 * The server keeps no session: every mutating response
 * returns the updated record and the UI retains it. The
 * record is persisted to sessionStorage so a reload
 * resumes the in-flight workflow. Records contain only
 * identifiers and process state — no reasoning content.
 */
interface WorkflowState {
  record: WorkflowRecord | null;
  setRecord: (record: WorkflowRecord | null) => void;
  clear: () => void;
}

const WorkflowContext = createContext<WorkflowState | null>(null);

function readStoredRecord(): WorkflowRecord | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed === "object" && parsed !== null && "id" in parsed) {
      return parsed as WorkflowRecord;
    }
    return null;
  } catch {
    return null;
  }
}

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [record, setRecordState] = useState<WorkflowRecord | null>(readStoredRecord);

  const setRecord = useCallback((next: WorkflowRecord | null) => {
    setRecordState(next);
    try {
      if (next === null) {
        sessionStorage.removeItem(STORAGE_KEY);
      } else {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      }
    } catch {
      // Storage is a convenience; the in-memory record is authoritative.
    }
  }, []);

  const clear = useCallback(() => setRecord(null), [setRecord]);

  const value = useMemo(() => ({ record, setRecord, clear }), [record, setRecord, clear]);
  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>;
}

export function useWorkflow(): WorkflowState {
  const state = useContext(WorkflowContext);
  if (state === null) {
    throw new Error("useWorkflow must be used inside <WorkflowProvider>");
  }
  return state;
}
