import { useState } from "react";
import { Link } from "react-router-dom";
import { noteEvidencePending, provideInformation } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
} from "../../components/StatusBits";
import { isTerminalState, workflowStateLabel } from "../../lib/workflow";

/**
 * Screen 2 — Shipment information.
 *
 * Structured sections (identity, then information steps)
 * rather than one giant form. Each action posts the
 * client-held record and retains the updated record from
 * the response.
 */
export function ShipmentInfoPage() {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const [error, setError] = useState<unknown>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [savedAction, setSavedAction] = useState<string | null>(null);

  if (!record) {
    return (
      <EmptyState
        title="No active shipment"
        body="Open a compliance case first."
        action={
          <Link className="primary-button" to="/">
            Start a new shipment
          </Link>
        }
      />
    );
  }

  const run = async (action: string, label: string, call: () => Promise<{ workflow: typeof record }>) => {
    setError(null);
    setSavedAction(null);
    setPendingAction(action);
    try {
      const response = await call();
      setRecord(response.workflow);
      setSavedAction(label);
    } catch (err) {
      setError(err);
    } finally {
      setPendingAction(null);
    }
  };

  const busy = pendingAction !== null;
  const closed = isTerminalState(record.state);
  const locked = busy || closed;

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Shipment record</p>
      </header>
      <section aria-label="Shipment identity">
        <h2>Shipment identity</h2>
        <dl className="field-grid">
          <Field label="Workflow">
            <Identifier value={record.id} />
          </Field>
          <Field label="Tenant">
            <Identifier value={record.tenant_id} />
          </Field>
          <Field label="Case">
            <Identifier value={record.case_id} />
          </Field>
          <Field label="Shipment reference">
            {record.shipment_id ? (
              <Identifier value={record.shipment_id} />
            ) : (
              <span className="muted">No shipment bound yet</span>
            )}
          </Field>
          <Field label="Current state">
            <span className="state-label">{workflowStateLabel(record.state)}</span>
          </Field>
        </dl>
      </section>
      <section aria-label="Information steps">
        <h2>Information steps</h2>
        <p className="muted">
          Recording information moves the workflow forward. Each step is a
          process marker — it judges nothing about the shipment.
        </p>
        {error ? <ErrorNotice error={error} /> : null}
        {closed ? (
          <p className="muted">
            This workflow is finalized and permanently closed: information steps can no longer be
            recorded, and the backend rejects any post-finalization mutation.
          </p>
        ) : null}
        {savedAction && !busy ? (
          <p className="form-hint" role="status">
            Saved — {savedAction} recorded on the workflow.
          </p>
        ) : null}
        <div className="action-row">
          <button
            type="button"
            className="primary-button"
            disabled={locked}
            onClick={() => run("provide", "Shipment information", () => provideInformation(auth, record))}
          >
            {pendingAction === "provide" ? "Recording…" : "Provide shipment information"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={locked}
            onClick={() => run("pending", "Evidence pending", () => noteEvidencePending(auth, record))}
          >
            {pendingAction === "pending" ? "Recording…" : "Mark evidence pending"}
          </button>
          <Link className="secondary-button" to="../requirements">
            Continue to requirements
          </Link>
        </div>
        {busy ? <LoadingState text="Updating workflow…" /> : null}
      </section>
    </div>
  );
}
