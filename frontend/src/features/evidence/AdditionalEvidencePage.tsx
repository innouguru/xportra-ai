import { useState } from "react";
import { Link } from "react-router-dom";
import { recordEvidence } from "../../api/evidence";
import { requestAdditionalEvidence, supplyEvidence } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useAnalysis } from "../../app/AnalysisContext";
import { useWorkflow } from "../../app/WorkflowContext";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
  TerminalNotice,
} from "../../components/StatusBits";
import { contradictionTone } from "../../lib/evidence";
import { assessmentTone, stateQualifier, uncertaintyTone } from "../../lib/findings";
import { applicabilityTone, isTerminalState, workflowStateLabel } from "../../lib/workflow";
import type { AnalysisFinding, EvidenceRecord } from "../../types/api";

/**
 * Screen 5c — Additional evidence loop (request → register → supply → re-run).
 *
 * Each action maps to exactly one existing backend use case, in journey
 * order. The screen shows why evidence was requested (open requirements
 * plus each finding's recorded missing information — never inferred),
 * accepts an evidence *reference* (there is no upload endpoint and none
 * is implied), associates it with a requirement when known, and supplies
 * it to the workflow.
 *
 * Supplying evidence records a reference: it does not establish
 * compliance and it never triggers analysis. Re-running analysis stays an
 * explicit, separate step on the Analysis screen.
 */
function parseIds(value: string): string[] {
  return value
    .split(/[\s,]+/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

export function AdditionalEvidencePage() {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const { report } = useAnalysis();
  const [requirementIds, setRequirementIds] = useState("");
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("");
  const [reference, setReference] = useState("");
  const [associateIds, setAssociateIds] = useState("");
  const [recorded, setRecorded] = useState<EvidenceRecord[]>([]);
  const [evidenceId, setEvidenceId] = useState("");
  const [supplyRequirementId, setSupplyRequirementId] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
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

  const closed = isTerminalState(record.state);
  const busy = pending !== null;
  const locked = busy || closed;
  const openRequirements = record.open_requirements;
  const latestReportId =
    record.rounds.length > 0 ? record.rounds[record.rounds.length - 1].report_id : null;
  const findingsByRequirement = new Map<string, AnalysisFinding>(
    (report?.findings ?? []).map((finding) => [finding.requirement_id, finding]),
  );

  const request = async (event: React.FormEvent) => {
    event.preventDefault();
    if (locked) return;
    setFieldError(null);
    setError(null);
    setNotice(null);
    const ids = parseIds(requirementIds);
    if (ids.length === 0) {
      setFieldError("At least one requirement ID is required to request evidence.");
      return;
    }
    setPending("request");
    try {
      const response = await requestAdditionalEvidence(auth, record, ids);
      setRecord(response.workflow);
      setRequirementIds("");
      setNotice(
        `Additional evidence requested. The workflow records ${ids.length} requirement${
          ids.length === 1 ? "" : "s"
        } as open.`,
      );
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const register = async (event: React.FormEvent) => {
    event.preventDefault();
    if (locked) return;
    setFieldError(null);
    setError(null);
    setNotice(null);
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
        requirement_ids: parseIds(associateIds),
      });
      setRecorded((current) => [...current, row]);
      setTitle("");
      setDocType("");
      setReference("");
      setAssociateIds("");
      setNotice(
        "Reference recorded. Supplying it to the workflow is a separate step — recording neither supplies nor analyses anything.",
      );
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const supply = async (event: React.FormEvent) => {
    event.preventDefault();
    if (locked) return;
    setFieldError(null);
    setError(null);
    setNotice(null);
    if (!evidenceId.trim()) {
      setFieldError(
        "An evidence ID is required. Record a reference on this screen first, then supply it.",
      );
      return;
    }
    setPending("supply");
    try {
      const response = await supplyEvidence(
        auth,
        record,
        evidenceId.trim(),
        supplyRequirementId.trim() || null,
      );
      setRecord(response.workflow);
      setEvidenceId("");
      setSupplyRequirementId("");
      setNotice(
        "Evidence supplied to the workflow. Supplying evidence does not establish compliance and does not run analysis — re-run analysis when you are ready.",
      );
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Evidence requested</p>
      </header>
      {closed ? (
        <TerminalNotice title="This workflow is finalized — additional evidence can no longer be supplied">
          <p>
            The assessment package is final and the workflow is permanently closed. Evidence
            intake, analysis runs and review steps are no longer offered here. The stored
            package and its report stay readable.
          </p>
          <div className="action-row">
            <Link className="secondary-button" to="../package">
              Assessment package
            </Link>
            <Link className="secondary-button" to="../history">
              Workflow history
            </Link>
          </div>
        </TerminalNotice>
      ) : null}

      <section aria-label="Why additional evidence was requested">
        <h2>Why additional evidence was requested</h2>
        <p className="muted">
          Everything below is what the backend already recorded: the workflow&apos;s open
          requirements and each finding&apos;s recorded missing information. Nothing here is
          inferred, recalculated, or scored.
        </p>
        <dl className="field-grid">
          <Field label="Workflow state">
            <StatusBadge value={record.state} tone="neutral" />{" "}
            <span className="muted">— {workflowStateLabel(record.state)}</span>
          </Field>
          <Field label="Open requirements reported">{openRequirements.length}</Field>
          <Field label="Evidence supplied so far">
            {record.supplied_evidence_ids.length} reference
            {record.supplied_evidence_ids.length === 1 ? "" : "s"}
          </Field>
          <Field label="Analysis rounds recorded">{record.rounds.length}</Field>
        </dl>
        <p className="form-hint">
          A request for additional evidence flags information that is still needed. It is not a
          finding of non-compliance, and supplying evidence does not by itself establish
          compliance.
        </p>
        <h3>Open requirements and what is missing</h3>
        {openRequirements.length === 0 ? (
          <p className="muted">
            No requirement is currently flagged open on the client-held workflow record.
            {record.state === "additional_evidence_requested"
              ? " The workflow itself records that additional evidence was requested; the flagged identities were not retained in this record."
              : " Requests are raised from this screen or from the findings review."}
          </p>
        ) : (
          <ul className="reference-list">
            {openRequirements.map((id) => {
              const finding = findingsByRequirement.get(id);
              return (
                <li key={id}>
                  <p className="eyebrow">Open requirement</p>
                  <p className="reference-id">
                    <Identifier value={id} short={36} />
                  </p>
                  {finding ? (
                    <FindingDetail finding={finding} />
                  ) : report ? (
                    <p className="muted">
                      The latest analysis round recorded no finding for this requirement.
                    </p>
                  ) : (
                    <p className="muted">
                      The latest analysis report is not loaded in this session, so its recorded
                      detail is not shown here.{" "}
                      {latestReportId ? (
                        <Link to={`../report/${encodeURIComponent(latestReportId)}`}>
                          Read the latest stored report
                        </Link>
                      ) : (
                        <Link to="../analysis">Run an analysis</Link>
                      )}
                      .
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-label="Request additional evidence">
        <h2>Request additional evidence</h2>
        <p className="muted">
          Flags requirements needing user action. The backend accepts the request only from a
          workflow state that permits it — otherwise it rejects the transition and this screen
          shows the reason unchanged.
        </p>
        <form className="form" onSubmit={request}>
          <div className="form-row">
            <label htmlFor="additional-requirement-ids">Requirement IDs</label>
            <input
              id="additional-requirement-ids"
              type="text"
              autoComplete="off"
              spellCheck={false}
              value={requirementIds}
              disabled={locked}
              onChange={(event) => setRequirementIds(event.target.value)}
              placeholder="Space- or comma-separated requirement IDs"
            />
            <p className="form-hint">
              Supply the identities the review identified, or{" "}
              <button
                type="button"
                className="link-button"
                disabled={locked || openRequirements.length === 0}
                onClick={() => setRequirementIds(openRequirements.join(", "))}
              >
                use the requirements already flagged open
              </button>
              .
            </p>
          </div>
          {fieldError ? (
            <p className="form-error" role="alert">
              {fieldError}
            </p>
          ) : null}
          <button type="submit" className="secondary-button" disabled={locked}>
            {pending === "request" ? "Requesting…" : "Request additional evidence"}
          </button>
        </form>
      </section>

      <section aria-label="Record an evidence reference">
        <h2>Record another evidence reference</h2>
        <p className="muted">
          Xportra records a <strong>reference</strong> to the document — its title, type, and
          where it can be found — rather than uploading file bytes. There is no file upload in
          this workspace, and document content is never stored by this application.
        </p>
        <form className="form" onSubmit={register} aria-describedby="additional-intake-hint">
          <div className="form-grid">
            <div className="form-row">
              <label htmlFor="additional-document-title">Document title</label>
              <input
                id="additional-document-title"
                type="text"
                value={title}
                disabled={locked}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Phytosanitary certificate"
              />
            </div>
            <div className="form-row">
              <label htmlFor="additional-document-type">Document type</label>
              <input
                id="additional-document-type"
                type="text"
                value={docType}
                disabled={locked}
                onChange={(event) => setDocType(event.target.value)}
                placeholder="e.g. certificate"
              />
            </div>
            <div className="form-row">
              <label htmlFor="additional-file-reference">File reference or URI</label>
              <input
                id="additional-file-reference"
                type="text"
                autoComplete="off"
                spellCheck={false}
                value={reference}
                disabled={locked}
                onChange={(event) => setReference(event.target.value)}
                placeholder="e.g. registry number or storage URI"
              />
            </div>
            <div className="form-row">
              <label htmlFor="additional-associate-requirements">
                Associate requirement IDs <span className="muted">(optional)</span>
              </label>
              <input
                id="additional-associate-requirements"
                type="text"
                autoComplete="off"
                spellCheck={false}
                value={associateIds}
                disabled={locked}
                onChange={(event) => setAssociateIds(event.target.value)}
                placeholder="Comma- or space-separated requirement IDs"
              />
            </div>
          </div>
          <p id="additional-intake-hint" className="form-hint">
            Intake accepts an evidence reference/URI only. The application never receives or
            stores document bytes.
          </p>
          <button type="submit" className="primary-button" disabled={locked}>
            {pending === "register" ? "Recording…" : "Record evidence reference"}
          </button>
        </form>
        {recorded.length > 0 ? (
          <ul className="reference-list">
            {recorded.map((row) => (
              <li key={row.id}>
                <p className="eyebrow">Recorded reference</p>
                <p>{row.document_title}</p>
                <dl className="field-grid">
                  <Field label="Type">{row.document_type}</Field>
                  <Field label="Reference">
                    <Identifier value={row.file_reference_or_uri} short={48} />
                  </Field>
                  <Field label="Evidence ID">
                    <Identifier value={row.id} short={36} />
                  </Field>
                </dl>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={locked}
                  onClick={() => {
                    setEvidenceId(row.id);
                    setNotice(
                      "Reference selected. Supply it to the workflow below when you are ready.",
                    );
                  }}
                >
                  Use this evidence ID for supply
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section aria-label="Supply evidence to the workflow">
        <h2>Supply evidence to the workflow</h2>
        <p className="muted">
          Supplying attaches a recorded evidence reference to this shipment&apos;s workflow. It
          does not establish compliance, does not change any recorded assessment outcome, and
          does not run analysis.
        </p>
        <form className="form" onSubmit={supply}>
          <div className="form-grid">
            <div className="form-row">
              <label htmlFor="additional-supply-evidence-id">Evidence ID</label>
              <input
                id="additional-supply-evidence-id"
                type="text"
                autoComplete="off"
                spellCheck={false}
                value={evidenceId}
                disabled={locked}
                onChange={(event) => setEvidenceId(event.target.value)}
                placeholder="Recorded evidence identifier"
              />
            </div>
            <div className="form-row">
              <label htmlFor="additional-supply-requirement-id">
                Requirement ID <span className="muted">(optional)</span>
              </label>
              <input
                id="additional-supply-requirement-id"
                type="text"
                autoComplete="off"
                spellCheck={false}
                list="additional-open-requirements"
                value={supplyRequirementId}
                disabled={locked}
                onChange={(event) => setSupplyRequirementId(event.target.value)}
                placeholder="Associate with a requirement when known"
              />
              <datalist id="additional-open-requirements">
                {openRequirements.map((id) => (
                  <option key={id} value={id} />
                ))}
              </datalist>
              <p className="form-hint">
                Association is optional; the requirements currently flagged open are offered as
                suggestions.
              </p>
            </div>
          </div>
          <button type="submit" className="primary-button" disabled={locked}>
            {pending === "supply" ? "Supplying…" : "Supply to workflow"}
          </button>
        </form>
      </section>

      {error ? <ErrorNotice error={error} /> : null}
      {notice && !busy ? (
        <p className="form-hint" role="status" aria-live="polite">
          {notice}
        </p>
      ) : null}
      {busy ? <LoadingState text="Updating workflow…" /> : null}

      <section aria-label="Next step">
        <h2>Next step</h2>
        <p className="muted">
          Supplying evidence moves the workflow to a re-analysis point. Analysis is never run
          automatically: start a new round explicitly, then review its findings again.
        </p>
        <div className="action-row">
          <Link className="secondary-button" to="../analysis">
            Go to analysis and re-run
          </Link>
          <Link className="secondary-button" to="../review">
            Back to findings review
          </Link>
        </div>
      </section>
    </div>
  );
}

/** One finding's recorded detail, rendered verbatim for the open requirement. */
function FindingDetail({ finding }: { finding: AnalysisFinding }) {
  const assessmentNote = stateQualifier("assessment", finding.assessment);
  const sufficiencyNote = stateQualifier("sufficiency", finding.evidence_sufficiency);
  return (
    <>
      <p className="reference-requirement">{finding.requirement_text}</p>
      <dl className="field-grid">
        <Field label="Applicability">
          <StatusBadge
            value={finding.applicability}
            tone={applicabilityTone(finding.applicability)}
          />
        </Field>
        <Field label="Assessment">
          <StatusBadge value={finding.assessment} tone={assessmentTone(finding.assessment)} />
          {assessmentNote ? <span className="muted"> — {assessmentNote}</span> : null}
        </Field>
        <Field label="Evidence sufficiency">
          <StatusBadge value={finding.evidence_sufficiency} tone="neutral" />
          {sufficiencyNote ? <span className="muted"> — {sufficiencyNote}</span> : null}
        </Field>
        <Field label="Uncertainty">
          <StatusBadge value={finding.uncertainty} tone={uncertaintyTone(finding.uncertainty)} />
        </Field>
        <Field label="Contradiction">
          <StatusBadge
            value={finding.contradiction_state}
            tone={contradictionTone(finding.contradiction_state)}
          />
        </Field>
      </dl>
      <h4>Missing information recorded for this requirement</h4>
      {finding.missing_information.length === 0 ? (
        <p className="muted">No missing-information item was recorded on this finding.</p>
      ) : (
        <ul>
          {finding.missing_information.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </>
  );
}

