import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { runAnalysis } from "../../api/analysis";
import { assessCaseReadiness } from "../../api/assessments";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { useAnalysis } from "../../app/AnalysisContext";
import type { CaseReadiness } from "../../types/api";
import { CaseBuilder, buildCases, newCaseDraft, type CaseDraft } from "../../components/CaseBuilder";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
  TerminalNotice,
} from "../../components/StatusBits";
import { readinessTone } from "../../lib/evidence";
import { isTerminalState } from "../../lib/workflow";

/**
 * Screen 6 — Analysis run (first run and re-runs).
 *
 * Analysis is an operation, not a permanent truth: the
 * state machine routes passes, and each run appends a
 * distinguishable round. Before execution the screen
 * shows evidence coverage, the current workflow state
 * and the rounds already recorded; it never computes
 * readiness itself. Every run is started by the user —
 * supplying evidence never triggers analysis. Duplicate
 * submission is prevented while a run is in flight;
 * failures preserve usable state and surface backend
 * semantics unchanged.
 */
export function AnalysisPage() {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const { setAnalysis } = useAnalysis();
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState<CaseDraft[]>([newCaseDraft()]);
  const [coverage, setCoverage] = useState<CaseReadiness | null>(null);
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

  const isFirstRun = record.rounds.length === 0;
  const latestRound = isFirstRun ? null : record.rounds[record.rounds.length - 1];
  const closed = isTerminalState(record.state);
  const waitingOnReanalysis = record.state === "reanalysis_required";
  const busy = pending !== null;

  const checkCoverage = async () => {
    setError(null);
    setPending("coverage");
    try {
      const cases = buildCases(record.tenant_id, record.case_id, drafts);
      const result = await assessCaseReadiness(auth, cases);
      setCoverage(result);
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const run = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setPending("analysis");
    try {
      const cases = buildCases(record.tenant_id, record.case_id, drafts);
      const response = await runAnalysis(auth, record, { cases });
      setRecord(response.workflow);
      setAnalysis(response.report, cases);
      navigate("../review");
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Compliance analysis</p>
        <p className="lede">
          Running analysis weighs the supplied evidence against the case
          views below and records a new round with its findings. The
          deterministic assessment stays authoritative — analysis organizes
          what is known, missing, uncertain, and contradictory for review.
        </p>
      </header>
      {closed ? (
        <TerminalNotice title="This workflow is finalized — analysis cannot be rerun">
          <p>
            The assessment package is final and the workflow is permanently closed. No new
            analysis round can be started, and the findings stay as finalized.
          </p>
          <div className="action-row">
            <Link className="secondary-button" to="../package">
              Assessment package
            </Link>
            {latestRound ? (
              <Link
                className="secondary-button"
                to={`../report/${encodeURIComponent(latestRound.report_id)}`}
              >
                Latest stored report
              </Link>
            ) : null}
          </div>
        </TerminalNotice>
      ) : null}
      {waitingOnReanalysis ? (
        <div className="notice" role="status">
          <p>
            Evidence has been supplied since the last recorded round. The workflow records that a
            new analysis is required — re-running it is your decision and is never automatic.
          </p>
        </div>
      ) : null}
      <section aria-label="Analysis readiness">
        <h2>Analysis readiness</h2>
        <p className="muted">
          Analysis runs against the case views below using the
          shipment&apos;s current workflow state (
          <strong>{record.state}</strong>, round {record.rounds.length + 1}).
          Coverage is informational — the backend alone
          decides whether a run may proceed.
        </p>
        <div className="action-row">
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={checkCoverage}
          >
            {pending === "coverage" ? "Checking…" : "Check evidence coverage"}
          </button>
        </div>
        {coverage ? (
          <dl className="field-grid">
            <Field label="Coverage">
              <StatusBadge value={coverage.readiness_state} tone={readinessTone(coverage.readiness_state)} />
            </Field>
            <Field label="Known / required">
              {coverage.known_information} / {coverage.required_information}
            </Field>
            <Field label="Missing items">{coverage.missing_information_count}</Field>
          </dl>
        ) : null}
      </section>
      <section aria-label="Analysis rounds">
        <h2>Recorded analysis rounds</h2>
        <p className="muted">
          Each completed run appends a round and leaves earlier rounds untouched. Rounds are
          identified by the backend in recorded order; the workflow stores no timestamps, so none
          are shown.
        </p>
        {record.rounds.length === 0 ? (
          <p className="muted">No round is recorded yet. A run appends round 1.</p>
        ) : (
          <>
            <p className="lede">
              Reviewing round {record.rounds.length}
              {latestRound ? (
                <>
                  {" "}
                  — latest report <Identifier value={latestRound.report_id} short={36} />
                </>
              ) : null}
              . A recorded round describes process progress only; it is not a compliance result.
            </p>
            <table className="data-table">
              <caption className="muted">Rounds in recorded order</caption>
              <thead>
                <tr>
                  <th scope="col">Round</th>
                  <th scope="col">Report</th>
                  <th scope="col">Findings analysed</th>
                  <th scope="col">Decision traces</th>
                </tr>
              </thead>
              <tbody>
                {record.rounds.map((round) => (
                  <tr key={round.round_index}>
                    <td className="numeric">{round.round_index}</td>
                    <td>
                      <Link to={`../report/${encodeURIComponent(round.report_id)}`}>
                        <Identifier value={round.report_id} short={36} />
                      </Link>
                    </td>
                    <td className="numeric">{round.analysis_ids.length}</td>
                    <td className="numeric">{round.trace_ids.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
      <section aria-label="Analysis cases">
        <h2>Cases under analysis</h2>
        {closed ? (
          <p className="muted">
            Analysis is closed on this workflow: the finalized package carries the last recorded
            round, and no further run is possible.
          </p>
        ) : (
          <>
            <p className="muted">
              Assemble the case views, then start the run. Supplying evidence never starts
              analysis — every round begins with an explicit action here.
            </p>
            <form className="form" onSubmit={run}>
              <CaseBuilder
                drafts={drafts}
                onChange={setDrafts}
                suppliedEvidenceIds={record.supplied_evidence_ids}
                idPrefix="analysis"
              />
              {error ? <ErrorNotice error={error} /> : null}
              {pending === "analysis" ? (
                <LoadingState text="Running analysis — retrieval and reasoning take a while. Do not close this page." />
              ) : (
                <button type="submit" className="primary-button" disabled={busy}>
                  {isFirstRun ? "Run analysis" : "Re-run analysis"}
                </button>
              )}
            </form>
          </>
        )}
      </section>
    </div>
  );
}
