import { Link } from "react-router-dom";
import { useAnalysis } from "../../app/AnalysisContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { FindingCard } from "../../components/FindingCard";
import { EmptyState, Field, Identifier } from "../../components/StatusBits";

/**
 * Screen 7 — Findings Review (Pass 2 centerpiece).
 *
 * Renders the latest analysis report exactly as received:
 * every finding with requirement, applicability,
 * assessment, explanation, evidence, sufficiency, missing
 * information, sources, and uncertainty. Contradictions
 * are preserved; nothing is scored, ranked, or verdicted.
 */
export function FindingsPage() {
  const { record } = useWorkflow();
  const { report } = useAnalysis();

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

  if (!report) {
    return (
      <EmptyState
        title="No analysis yet"
        body="Run an analysis first. Its findings will appear here for review — what was considered, what supports each finding, what is missing, and where it came from."
        action={
          <Link className="primary-button" to="../analysis">
            Go to analysis
          </Link>
        }
      />
    );
  }

  const attentionCount =
    report.requirements_with_missing_information.length +
    report.uncertain_requirement_ids.length;
  const round = record.rounds.find((item) => item.report_id === report.report_id);
  const latestRound = record.rounds.length > 0 ? record.rounds[record.rounds.length - 1] : null;
  const reviewingNewRound =
    round !== undefined && latestRound !== null && round.round_index === latestRound.round_index;

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Analysis findings</p>
      </header>
      <section aria-label="Report overview">
        <h2>
          Findings review — {report.findings.length}{" "}
          {report.findings.length === 1 ? "requirement" : "requirements"} reviewed
        </h2>
        <dl className="field-grid">
          <Field label="Report">
            <Identifier value={report.report_id} short={36} />
          </Field>
          <Field label="Analysis round">
            {round ? (
              <>
                Round {round.round_index} of {record.rounds.length} recorded
              </>
            ) : (
              <span className="muted">Not recorded on the client-held workflow record.</span>
            )}
          </Field>
          <Field label="Requirements needing attention">{attentionCount}</Field>
          <Field label="With supporting evidence">
            {report.findings.length - report.requirements_with_missing_information.length}
          </Field>
          <Field label="Conflicting evidence items">{report.conflicting_evidence_count}</Field>
        </dl>
        {reviewingNewRound && round && round.round_index > 1 ? (
          <p className="form-hint" role="status">
            You are reviewing the latest analysis round (round {round.round_index}). Earlier
            rounds stay recorded and remain readable from the Analysis screen.
          </p>
        ) : null}
        <p className="muted">
          Counts describe the report as received. They are not a
          compliance score and this screen renders no verdict.
        </p>
      </section>
      {report.findings.map((finding, position) => (
        <FindingCard
          key={finding.analysis_id}
          finding={finding}
          index={position}
          total={report.findings.length}
        />
      ))}
      <div className="action-row">
        <Link
          className="secondary-button"
          to={`../report/${encodeURIComponent(report.report_id)}`}
        >
          Open stored report
        </Link>
        <Link className="secondary-button" to="../evidence">
          Supply additional evidence
        </Link>
        <Link className="secondary-button" to="../additional-evidence">
          Request additional evidence
        </Link>
        <Link className="secondary-button" to="../analysis">
          Re-run analysis
        </Link>
        <Link className="secondary-button" to="../final-review">
          Continue to final review
        </Link>
      </div>
    </div>
  );
}
