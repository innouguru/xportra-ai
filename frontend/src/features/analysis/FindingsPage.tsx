import { useState } from "react";
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

  type FindingGroup =
    | "all"
    | "needs-information"
    | "uncertain"
    | "contradictions"
    | "unresolved";
  const [group, setGroup] = useState<FindingGroup>("all");

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

  const missing = new Set(report.requirements_with_missing_information);
  const uncertain = new Set(report.uncertain_requirement_ids);
  const conflicting = new Set(report.requirements_with_conflicting_evidence);
  // A finding contradicts when the report rollup names it or when the
  // finding itself carries conflicting references — both are recorded
  // facts, and either deserves reviewer inspection.
  const contradicts = (requirementId: string) =>
    conflicting.has(requirementId) ||
    (report.findings.find((finding) => finding.requirement_id === requirementId)
      ?.conflicting_evidence.length ?? 0) > 0;
  const visible = report.findings.filter((finding) => {
    switch (group) {
      case "needs-information":
        return missing.has(finding.requirement_id);
      case "uncertain":
        return uncertain.has(finding.requirement_id);
      case "contradictions":
        return contradicts(finding.requirement_id);
      case "unresolved":
        return finding.assessment === "unknown";
      default:
        return true;
    }
  });
  const groups: Array<{ id: FindingGroup; label: string; count: number }> = [
    { id: "all", label: "All findings", count: report.findings.length },
    {
      id: "needs-information",
      label: "Needs information",
      count: report.findings.filter((finding) => missing.has(finding.requirement_id)).length,
    },
    {
      id: "uncertain",
      label: "Uncertain",
      count: report.findings.filter((finding) => uncertain.has(finding.requirement_id)).length,
    },
    {
      id: "contradictions",
      label: "Contradictions",
      count: report.findings.filter((finding) => contradicts(finding.requirement_id)).length,
    },
    {
      id: "unresolved",
      label: "Unresolved",
      count: report.findings.filter((finding) => finding.assessment === "unknown").length,
    },
  ];

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
      <div className="filter-chips" role="group" aria-label="Filter findings">
        {groups.map((option) => (
          <button
            key={option.id}
            type="button"
            className="chip"
            aria-pressed={group === option.id}
            onClick={() => setGroup(option.id)}
          >
            {option.label} ({option.count})
          </button>
        ))}
      </div>
      <p className="form-hint">
        Groups reflect the stored report: recorded missing information,
        recorded uncertainty, recorded conflicting references, and undecided
        assessments. Selecting a group filters this list only.
      </p>
      {visible.length === 0 ? (
        <p className="muted">No findings in this group.</p>
      ) : null}
      {visible.map((finding) => (
        <FindingCard
          key={finding.analysis_id}
          finding={finding}
          index={report.findings.indexOf(finding)}
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
