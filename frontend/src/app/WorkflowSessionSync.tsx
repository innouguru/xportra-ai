import { useEffect } from "react";
import { useAuth } from "./AuthContext";
import { useAnalysis } from "./AnalysisContext";
import { useAssessment } from "./AssessmentContext";
import { useWorkflow } from "./WorkflowContext";

/**
 * Session/workflow coordination boundary.
 *
 * The client-held workflow record is scoped to a signed-in
 * session: it exists to resume an in-flight workflow across
 * reloads, never to keep a signed-out visitor in workspace
 * state. This boundary clears it whenever the session is
 * unconfigured (after sign-out, or when a stale record
 * survives in sessionStorage), while leaving initialized,
 * authenticated workflows untouched.
 *
 * It is deliberately a separate component so that neither
 * `AuthContext` nor `WorkflowContext` depends on the other.
 * The durable archive on the server and the device-local
 * shipment registry are not affected, so a shipment created
 * before sign-out stays recoverable.
 */
export function WorkflowSessionSync() {
  const auth = useAuth();
  const { record, clear } = useWorkflow();
  const { clear: clearAnalysis } = useAnalysis();
  const { clear: clearAssessment } = useAssessment();

  useEffect(() => {
    if (auth.initializing || auth.isConfigured || record === null) {
      if (!auth.initializing && !auth.isConfigured) {
        clearAnalysis();
        clearAssessment();
      }
      return;
    }
    clear();
    clearAnalysis();
    clearAssessment();
  }, [auth.initializing, auth.isConfigured, record, clear, clearAnalysis, clearAssessment]);

  return null;
}
