import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { startWorkflow } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { AppShell } from "../../components/AppShell";
import { ErrorNotice, LoadingState } from "../../components/StatusBits";

/**
 * Screen 1 — New shipment / workflow.
 *
 * Collects only what `POST /compliance/workflows/start`
 * accepts: a case ID and an optional shipment ID. Shows
 * the returned workflow identity and transitions into
 * the workspace, preserving the server response.
 */
function newUuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  const hex = "0123456789abcdef";
  const pick = () => hex[Math.floor(Math.random() * 16)];
  const section = (length: number) => Array.from({ length }, pick).join("");
  return `${section(8)}-${section(4)}-4${section(3)}-a${section(3)}-${section(12)}`;
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function NewShipmentPage() {
  const auth = useAuth();
  const { setRecord } = useWorkflow();
  const navigate = useNavigate();
  const [caseId, setCaseId] = useState("");
  const [shipmentId, setShipmentId] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFieldError(null);
    setRequestError(null);
    if (!UUID_PATTERN.test(caseId.trim())) {
      setFieldError("Case ID must be a valid UUID.");
      return;
    }
    if (shipmentId.trim() && !UUID_PATTERN.test(shipmentId.trim())) {
      setFieldError("Shipment ID must be a valid UUID when provided.");
      return;
    }
    setPending(true);
    try {
      const response = await startWorkflow(auth, {
        case_id: caseId.trim(),
        shipment_id: shipmentId.trim() || null,
      });
      setRecord(response.workflow);
      navigate("/workspace");
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        setFieldError(
          "Your role does not allow creating workflows. Contact a workspace owner.",
        );
      } else {
        setRequestError(error);
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <AppShell title="Start a shipment workspace">
      {!auth.isConfigured ? (
        <p className="lede">
          Connect your session first, then open a compliance case for a
          shipment. <a href="/session">Go to sign in</a>.
        </p>
      ) : (
        <>
          <p className="lede">
            Open a compliance case for a shipment. This workspace will establish:
          </p>
          <ul className="checklist">
            <li>Shipment context for the case under review</li>
            <li>Applicable requirements for that context</li>
            <li>Evidence coverage against those requirements</li>
            <li>Compliance analysis grounded in the evidence supplied</li>
            <li>An assessment package for final review</li>
          </ul>
          <p className="muted">
            Xportra records facts, maps requirements, and reviews findings with
            you — nothing is judged until evidence is supplied and analyzed,
            and no outcome here is a regulatory approval.
          </p>
          <form className="form" onSubmit={submit} aria-describedby={fieldError ? "new-shipment-error" : undefined}>
        {pending ? (
          <LoadingState text="Opening the compliance case…" />
        ) : (
          <button type="submit" className="primary-button" disabled={!auth.isConfigured}>
            Start compliance workflow
          </button>
        )}
        <section className="technical-details" aria-label="Technical identifiers">
          <h2>Technical identifiers</h2>
          <p className="muted">
            The workflow is tracked by system identifiers. Generate fresh
            ones here, or paste identifiers you already hold.
          </p>
          <div className="form-row">
            <label htmlFor="case-id">Case ID</label>
            <input
              id="case-id"
              type="text"
              autoComplete="off"
              spellCheck={false}
              value={caseId}
              onChange={(event) => setCaseId(event.target.value)}
              placeholder="e.g. cccccccc-cccc-cccc-cccc-cccccccccccc"
            />
            <button
              type="button"
              className="ghost-button"
              onClick={() => setCaseId(newUuid())}
            >
              Generate
            </button>
          </div>
          <div className="form-row">
            <label htmlFor="shipment-id">Shipment ID (optional)</label>
            <input
              id="shipment-id"
              type="text"
              autoComplete="off"
              spellCheck={false}
              value={shipmentId}
              onChange={(event) => setShipmentId(event.target.value)}
              placeholder="Bind an existing shipment, if you have one"
            />
            <button
              type="button"
              className="ghost-button"
              onClick={() => setShipmentId(newUuid())}
            >
              Generate
            </button>
          </div>
        </section>
        {fieldError ? (
          <p id="new-shipment-error" className="form-error" role="alert">
            {fieldError}
          </p>
        ) : null}
        {requestError ? <ErrorNotice error={requestError} /> : null}
          </form>
        </>
      )}
    </AppShell>
  );
}
