import { useState } from "react";
import { Link } from "react-router-dom";
import { recordEvidence } from "../../api/evidence";
import { supplyEvidence } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
} from "../../components/StatusBits";
import type { EvidenceRecord } from "../../types/api";
import { isTerminalState } from "../../lib/workflow";

/**
 * Screen 4 — Evidence intake (reference-based).
 *
 * There is NO file-upload endpoint: intake registers a
 * reference (title, type, URI, optional requirement
 * links) and then supplies the recorded evidence ID to
 * the workflow. The form states this explicitly so the
 * UI never pretends to upload bytes.
 */
export function EvidencePage() {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("");
  const [reference, setReference] = useState("");
  const [requirementIds, setRequirementIds] = useState("");
  const [recorded, setRecorded] = useState<EvidenceRecord[]>([]);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<string | null>(null);

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

  const parseIds = (value: string): string[] =>
    value
      .split(/[\s,]+/)
      .map((part) => part.trim())
      .filter((part) => part.length > 0);

  const closed = isTerminalState(record.state);
  const locked = pending !== null || closed;

  const register = async (event: React.FormEvent) => {
    event.preventDefault();
    setFieldError(null);
    setError(null);
    if (!title.trim() || !docType.trim() || !reference.trim()) {
      setFieldError("Document title, document type, and file reference are all required.");
      return;
    }
    setPending("register");
    try {
      const row = await recordEvidence(auth, {
        document_title: title.trim(),
        document_type: docType.trim(),
        file_reference_or_uri: reference.trim(),
        requirement_ids: parseIds(requirementIds),
      });
      setRecorded((current) => [...current, row]);
      setTitle("");
      setDocType("");
      setReference("");
      setRequirementIds("");
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const supply = async (evidenceId: string) => {
    setError(null);
    setPending(`supply-${evidenceId}`);
    try {
      const response = await supplyEvidence(auth, record, evidenceId);
      setRecord(response.workflow);
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const supplied = new Set(record.supplied_evidence_ids);
  const registeredUnsupplied = recorded.filter((row) => !supplied.has(row.id));

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Evidence workspace</p>
        <p className="lede">
          Xportra currently records evidence references. Document upload is
          not enabled in this workflow — references you register below are
          what analysis can consider.
        </p>
      </header>
      <section aria-label="Supplied evidence">
        <h2>Supplied to this workflow ({record.supplied_evidence_ids.length})</h2>
        {record.supplied_evidence_ids.length === 0 ? (
          <p className="muted">
            No evidence has been supplied to this workflow yet. Register a
            reference below, then supply it so analysis can consider it.
          </p>
        ) : (
          <ul className="reference-list">
            {record.supplied_evidence_ids.map((id) => (
              <li key={id}>
                <Identifier value={id} />
              </li>
            ))}
          </ul>
        )}
        {error ? <ErrorNotice error={error} /> : null}
        {pending && !pending.startsWith("supply-") && pending !== "register" ? (
          <LoadingState text="Updating workflow…" />
        ) : null}
      </section>
      <section aria-label="Needed evidence">
        <h2>Needed ({record.open_requirements.length})</h2>
        <p className="muted">
          Requirements flagged open on this workflow — information still
          needed, not non-compliance. Absence alone decides nothing.
        </p>
        {record.open_requirements.length === 0 ? (
          <p className="muted">No requirements are currently flagged open.</p>
        ) : (
          <ul className="reference-list">
            {record.open_requirements.map((id) => (
              <li key={id}>
                <p className="eyebrow">Open requirement</p>
                <p className="reference-id">
                  <Identifier value={id} short={36} />
                </p>
              </li>
            ))}
          </ul>
        )}
        <div className="action-row">
          <Link className="secondary-button" to="../gaps">
            What information is missing
          </Link>
          <Link className="secondary-button" to="../additional-evidence">
            Supply requested evidence
          </Link>
        </div>
      </section>
      <section aria-label="Evidence attention">
        <h2>Attention</h2>
        {closed ? (
          <p className="muted">
            This workflow is finalized — the evidence record is read-only.
          </p>
        ) : (
          <ul className="attention-list">
            {record.state === "additional_evidence_requested" ? (
              <li className="attention-item attention-item--attention">
                <div>
                  <p className="attention-item__title">Additional evidence was requested</p>
                  <p className="muted">
                    Review what is open, register a reference below, and supply it.
                  </p>
                </div>
                <Link className="secondary-button" to="../additional-evidence">
                  Open request
                </Link>
              </li>
            ) : null}
            {registeredUnsupplied.length > 0 ? (
              <li className="attention-item attention-item--attention">
                <div>
                  <p className="attention-item__title">
                    {registeredUnsupplied.length} registered, not yet supplied
                  </p>
                  <p className="muted">
                    These references exist but analysis cannot consider them until supplied.
                  </p>
                </div>
                <a className="secondary-button" href="#registered-evidence">
                  Review list
                </a>
              </li>
            ) : null}
            {record.state !== "additional_evidence_requested" &&
            registeredUnsupplied.length === 0 ? (
              <li className="attention-item attention-item--neutral">
                <div>
                  <p className="attention-item__title">
                    {recorded.length === 0 ? "No references yet" : "Nothing needs attention"}
                  </p>
                  <p className="muted">
                    {recorded.length === 0
                      ? "Register a reference below to get started."
                      : "Every reference registered this session has been supplied."}
                  </p>
                </div>
              </li>
            ) : null}
          </ul>
        )}
      </section>
      <section aria-label="Register evidence reference">
        <h2>Register evidence reference</h2>
        <p className="muted">
          Xportra records a <strong>reference</strong> to your document — its
          title, type, and where it can be found — rather than uploading
          file bytes. No file upload is available.
        </p>
        {closed ? (
          <p className="muted">
            This workflow is finalized and permanently closed: evidence can no longer be
            registered or supplied, and the backend rejects any post-finalization mutation.
          </p>
        ) : null}
        <form className="form" onSubmit={register}>
          <div className="form-grid">
            <div className="form-row">
              <label htmlFor="evidence-title">Document title</label>
              <input
                id="evidence-title"
                type="text"
                value={title}
                disabled={closed}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Phytosanitary certificate NG-2024-118"
              />
            </div>
            <div className="form-row">
              <label htmlFor="evidence-type">Document type</label>
              <input
                id="evidence-type"
                type="text"
                value={docType}
                disabled={closed}
                onChange={(event) => setDocType(event.target.value)}
                placeholder="e.g. certificate"
              />
            </div>
            <div className="form-row">
              <label htmlFor="evidence-reference">File reference or URI</label>
              <input
                id="evidence-reference"
                type="text"
                value={reference}
                disabled={closed}
                onChange={(event) => setReference(event.target.value)}
                placeholder="e.g. registry number or storage URI"
              />
            </div>
            <div className="form-row">
              <label htmlFor="evidence-requirements">
                Requirement IDs <span className="muted">(optional, comma or space separated)</span>
              </label>
              <input
                id="evidence-requirements"
                type="text"
                value={requirementIds}
                disabled={closed}
                onChange={(event) => setRequirementIds(event.target.value)}
                placeholder="Associate at intake when known"
              />
            </div>
          </div>
          {fieldError ? (
            <p className="form-error" role="alert">
              {fieldError}
            </p>
          ) : null}
          <button type="submit" className="primary-button" disabled={locked}>
            {pending === "register" ? "Registering…" : "Register evidence reference"}
          </button>
        </form>
      </section>
      <section aria-label="Registered evidence" id="registered-evidence">
        <h2>Registered this session</h2>
        {recorded.length === 0 ? (
          <p className="muted">No evidence references registered yet in this session.</p>
        ) : (
          <ul className="reference-list">
            {recorded.map((row) => (
              <li key={row.id}>
                <dl className="field-grid">
                  <Field label="Title">{row.document_title}</Field>
                  <Field label="Type">{row.document_type}</Field>
          <Field label="Reference">
            <Identifier value={row.file_reference_or_uri} short={48} />
          </Field>
                  <Field label="Evidence ID">
                    <Identifier value={row.id} short={36} />
                  </Field>
                  <Field label="Workflow status">
                    {supplied.has(row.id) ? (
                      <span>Supplied to this workflow</span>
                    ) : (
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={locked}
                        onClick={() => supply(row.id)}
                      >
                        {pending === `supply-${row.id}` ? "Supplying…" : "Supply to workflow"}
                      </button>
                    )}
                  </Field>
                </dl>
              </li>
            ))}
          </ul>
        )}
      </section>
      <div className="action-row">
          <Link className="secondary-button" to="../gaps">
            Review evidence gaps
          </Link>
          <Link className="secondary-button" to="../analysis">
            Continue to analysis
          </Link>
        </div>
    </div>
  );
}
