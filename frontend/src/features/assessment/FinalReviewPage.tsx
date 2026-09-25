import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { fetchStoredReport, finalizeStoredPackage } from "../../api/workflows";
import { useAnalysis } from "../../app/AnalysisContext";
import { useAssessment } from "../../app/AssessmentContext";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { FindingCard } from "../../components/FindingCard";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
  TerminalNotice,
} from "../../components/StatusBits";
import { isTerminalState, workflowStateLabel } from "../../lib/workflow";
import type { AnalysisReport, ReadinessReason } from "../../types/api";

/**
 * Screen 8 — Final review before terminal finalization.
 *
 * Shows what will become the final assessment package, using
 * only what the backend already reported: shipment/workspace
 * identity, the latest analysis round and its findings
 * (applicability, assessment, explanations, evidence
 * references, sufficiency, missing information, contradictions,
 * uncertainty), the open-requirement snapshot, and whatever
 * blockers the backend returns.
 *
 * Nothing is recomputed or reinterpreted: `unknown` stays
 * undecided, missing evidence stays an information need, and no
 * overall verdict, score, percentage or ranking exists here.
 * Finalization is a separate, explicit, two-step user action.
 */
function readinessReasons(error: unknown): ReadinessReason[] {
  if (!(error instanceof ApiError)) {
    return [];
  }
  const details = error.details as
    | { reasons?: Array<{ code?: string; detail?: string }> }
    | null
    | undefined;
  if (!details || !Array.isArray(details.reasons)) {
    return [];
  }
  return details.reasons
    .filter(
      (reason): reason is { code: string; detail: string } =>
        typeof reason?.code === "string" && typeof reason?.detail === "string",
    )
    .map((reason) => ({ code: reason.code, detail: reason.detail }));
}

export function FinalReviewPage() {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const { report: sessionReport } = useAnalysis();
  const { setPackage } = useAssessment();
  const navigate = useNavigate();
  const [report, setReport] = useState<AnalysisReport | null>(sessionReport);
  const [reportError, setReportError] = useState<unknown>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [reasons, setReasons] = useState<ReadinessReason[]>([]);
  const [reloadKey, setReloadKey] = useState(0);

  const latestReportId =
    record && record.rounds.length > 0
      ? record.rounds[record.rounds.length - 1].report_id
      : null;
  const sessionReportIsLatest =
    sessionReport !== null && sessionReport.report_id === latestReportId;

  useEffect(() => {
    if (sessionReportIsLatest) {
      setReport(sessionReport);
      return;
    }
    if (!latestReportId) {
      return;
    }
    let cancelled = false;
    setLoadingReport(true);
    setReportError(null);
    fetchStoredReport(auth, latestReportId)
      .then((loaded) => {
        if (!cancelled) {
          setReport(loaded);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setReportError(err);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingReport(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionReportIsLatest, latestReportId, reloadKey]);

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
  const roundIndex =
    report === null
      ? null
      : record.rounds.find((item) => item.report_id === report.report_id)?.round_index ?? null;

  const finalize = async () => {
    setError(null);
    setReasons([]);
    setPending(true);
    try {
      const response = await finalizeStoredPackage(auth, record);
      setRecord(response.workflow);
      setPackage(response.package);
      navigate("../package");
    } catch (err) {
      setError(err);
      setReasons(readinessReasons(err));
      setConfirming(false);
    } finally {
      setPending(false);
    }
  };

  const attentionCount =
    report === null
      ? 0
      : report.requirements_with_missing_information.length +
        report.uncertain_requirement_ids.length;

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Deliberate checkpoint</p>
        <p className="lede">
          Review the assessment before permanently closing this workflow.
          What follows is what finalization will preserve — nothing more.
        </p>
      </header>
      {closed ? (
        <TerminalNotice title="This workflow is finalized — the final review is closed">
          <p>
            The assessment package is final and permanent. Additional evidence can no longer be
            supplied, analysis cannot be rerun, and the current workflow offers no reopen or
            versioning operation.
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

      <section aria-label="Review summary">
        <p className="eyebrow">Final review</p>
        <h2>
          {report
            ? `${report.findings.length} ${
                report.findings.length === 1 ? "finding" : "findings"
              } under review${
                roundIndex !== null ? ` — analysis round ${roundIndex}` : ""
              }`
            : "Latest analysis not loaded"}
        </h2>
        <dl className="field-grid">
          <Field label="Workflow">
            <Identifier value={record.id} short={36} />
          </Field>
          <Field label="Tenant">
            <Identifier value={record.tenant_id} short={36} />
          </Field>
          <Field label="Case">
            <Identifier value={record.case_id} short={36} />
          </Field>
          <Field label="Shipment">
            {record.shipment_id ? (
              <Identifier value={record.shipment_id} short={36} />
            ) : (
              <span className="muted">Unbound</span>
            )}
          </Field>
          <Field label="Workflow state">
            <StatusBadge value={record.state} tone="neutral" />{" "}
            <span className="muted">— {workflowStateLabel(record.state)}</span>
          </Field>
          <Field label="Rounds recorded">{record.rounds.length}</Field>
          {report ? (
            <Field label="Report">
              <Identifier value={report.report_id} short={36} />
            </Field>
          ) : null}
        </dl>
        <p className="muted">
          Final review is read-only. Nothing here recomputes an assessment, and no verdict, score
          or percentage is derived from the states below.
        </p>
      </section>

      {loadingReport ? <LoadingState text="Reading the latest stored report…" /> : null}
      {reportError ? (
        <ErrorNotice error={reportError} onRetry={() => setReloadKey((key) => key + 1)} />
      ) : null}

      {!report && !loadingReport && !reportError ? (
        <EmptyState
          title="Nothing to finalize yet"
          body="Final review needs the latest analysis report. Run an analysis first, review its findings, then return here to finalize."
          action={
            <Link className="primary-button" to="../analysis">
              Go to analysis
            </Link>
          }
        />
      ) : null}

      {report ? (
        <>
          <section aria-label="What the package will contain">
            <h2>What the finalized package will contain</h2>
            <p className="muted">
              The decision finalization asks of you: that you have reviewed
              the assessment below and are ready to create the final package.
              Counts describe the latest report as received — not a score.
            </p>
            <dl className="checkpoint-list">
              <div>
                <dt>Findings</dt>
                <dd>
                  {report.findings.length} under review —{" "}
                  <Link to={`../report/${encodeURIComponent(report.report_id)}`}>
                    open the stored report
                  </Link>
                </dd>
              </div>
              <div>
                <dt>Evidence supplied</dt>
                <dd>
                  {record.supplied_evidence_ids.length} reference
                  {record.supplied_evidence_ids.length === 1 ? "" : "s"} —{" "}
                  <Link to="../evidence">evidence workspace</Link>
                </dd>
              </div>
              <div>
                <dt>Open information needs</dt>
                <dd>
                  {record.open_requirements.length === 0 ? (
                    <span className="muted">None recorded on this workflow.</span>
                  ) : (
                    <ul className="reference-list reference-list--plain">
                      {record.open_requirements.map((id) => (
                        <li key={id}>
                          <Identifier value={id} short={36} />
                        </li>
                      ))}
                    </ul>
                  )}
                </dd>
              </div>
              <div>
                <dt>Requirements with missing information</dt>
                <dd>{report.requirements_with_missing_information.length}</dd>
              </div>
              <div>
                <dt>Uncertain requirements</dt>
                <dd>{report.uncertain_requirement_ids.length}</dd>
              </div>
              <div>
                <dt>Conflicting evidence</dt>
                <dd>
                  {report.requirements_with_conflicting_evidence.length} requirements ·{" "}
                  {report.conflicting_evidence_count} items — recorded, not resolved
                </dd>
              </div>
              <div>
                <dt>Needing attention</dt>
                <dd>{attentionCount}</dd>
              </div>
            </dl>
            <p className="form-hint">
              Undecided states stay <code>unknown</code>, and missing evidence stays an
              information need — neither is presented as failure. The carried decision summary
              travels with the latest result and is shown in full on the package.
            </p>
            <div className="action-row">
              <Link
                className="secondary-button"
                to={`../report/${encodeURIComponent(report.report_id)}`}
              >
                Open the stored report
              </Link>
            </div>
          </section>

          <section aria-label="Findings as they will be finalized">
            <h2>Findings as they will be finalized</h2>
            {report.findings.map((finding, position) => (
              <FindingCard
                key={finding.analysis_id}
                finding={finding}
                index={position}
                total={report.findings.length}
              />
            ))}
          </section>
        </>
      ) : null}

      <section aria-label="Finalize assessment package">
        <h2>Finalize assessment package</h2>
        {closed ? (
          <p className="muted">
            This workflow is already finalized. The controls that would change it are no longer
            offered, and the backend rejects any post-finalization mutation.
          </p>
        ) : !report ? (
          <p className="muted">
            Finalization becomes available once the latest analysis is loaded and reviewed.
          </p>
        ) : !confirming ? (
          <>
            <p className="muted">
              Review is complete on your side when you choose to proceed. Finalization is a
              separate, explicit step and is never triggered automatically.
            </p>
            <div className="action-row">
              <button
                type="button"
                className="primary-button"
                disabled={pending}
                onClick={() => {
                  setError(null);
                  setReasons([]);
                  setConfirming(true);
                }}
              >
                Review complete
              </button>
            </div>
          </>
        ) : (
          <div className="confirm-panel" role="group" aria-label="Finalization confirmation">
            <p>
              <strong>Finalization is permanent.</strong> The workflow becomes closed: additional
              evidence cannot be supplied afterward, analysis cannot be rerun, and the current
              workflow offers no reopen or versioning operation.
            </p>
            <p className="muted">
              The package is created from the latest recorded analysis round. Finalizing
              recalculates nothing.
            </p>
            {error ? <ErrorNotice error={error} /> : null}
            <BlockerList reasons={reasons} />
            <div className="action-row">
              <button
                type="button"
                className="primary-button"
                disabled={pending}
                onClick={finalize}
              >
                {pending ? "Finalizing…" : "Finalize assessment package"}
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={pending}
                onClick={() => setConfirming(false)}
              >
                Back to review
              </button>
            </div>
            {pending ? <LoadingState text="Finalizing assessment package…" /> : null}
          </div>
        )}
      </section>

      {!confirming && error ? (
        <section aria-label="Readiness blockers reported by the backend">
          <h2>Readiness blockers reported by the backend</h2>
          <ErrorNotice error={error} />
          <BlockerList reasons={reasons} />
        </section>
      ) : null}

      <section aria-label="Continue after finalization">
        <h2>After finalization</h2>
        <p className="muted">
          A finalized workflow is read through the assessment package. Its report stays readable
          by identity, and the workflow history remains available as a projection.
        </p>
        <div className="action-row">
          <Link className="secondary-button" to="../package">
            Assessment package
          </Link>
          <Link className="secondary-button" to="../history">
            Workflow history
          </Link>
        </div>
      </section>
    </div>
  );
}

/** Backend readiness reasons, rendered verbatim (codes and details). */
function BlockerList({ reasons }: { reasons: ReadinessReason[] }) {
  if (reasons.length === 0) {
    return null;
  }
  return (
    <ul className="reference-list reference-list--plain">
      {reasons.map((reason) => (
        <li key={`${reason.code}-${reason.detail}`}>
          <StatusBadge value={reason.code} tone="attention" /> <span>{reason.detail}</span>
        </li>
      ))}
    </ul>
  );
}

