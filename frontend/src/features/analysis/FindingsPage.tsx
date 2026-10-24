import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useStoredReport } from "../../app/useStoredReport";
import { useWorkflow } from "../../app/WorkflowContext";
import { FindingCard } from "../../components/FindingCard";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
} from "../../components/StatusBits";
import { isUuidLike } from "../../lib/conversation";
import { countRequirementsNeedingAttention } from "../../lib/findings";
import { isTerminalState } from "../../lib/workflow";
import { AskXportraButton } from "../conversation/AskXportraButton";

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
  // In-memory report first, else the persisted report
  // rehydrated from the latest recorded round — the
  // rendering below is identical either way.
  const { report, status, error } = useStoredReport();

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
          <Link className="primary-button" to="/start">
            Start a new shipment
          </Link>
        }
      />
    );
  }

  if (!report) {
    if (status === "loading") {
      return <LoadingState text="Reading the stored analysis…" />;
    }
    if (status === "error") {
      // A missing stored report is absence; any other
      // failure is an error, never a clean "no analysis".
      if (
        error instanceof ApiError &&
        (error.code === "not_found" || error.code === "resource_not_found")
      ) {
        return (
          <EmptyState
            title="Report unavailable"
            body="The stored report could not be loaded for this workspace."
          />
        );
      }
      return <ErrorNotice error={error} />;
    }
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

  const attentionCount = countRequirementsNeedingAttention(report);
  const round = record.rounds.find((item) => item.report_id === report.report_id);
  const latestRound = record.rounds.length > 0 ? record.rounds[record.rounds.length - 1] : null;
  const reviewingNewRound =
    round !== undefined && latestRound !== null && round.round_index === latestRound.round_index;
  const needsEvidenceReview =
    report.requirements_with_missing_information.length > 0 ||
    report.uncertain_requirement_ids.length > 0 ||
    report.requirements_with_conflicting_evidence.length > 0 ||
    report.conflicting_evidence_count > 0 ||
    report.findings.some(
      (finding) =>
        finding.assessment === "unknown" ||
        finding.uncertainty === "uncertain" ||
        finding.uncertainty === "unknown" ||
        finding.contradiction_state === "present" ||
        finding.contradiction_state === "unknown" ||
        ["missing", "insufficient", "unknown"].includes(finding.evidence_sufficiency) ||
        finding.missing_information.length > 0 ||
        finding.conflicting_evidence.length > 0,
    );
  const nextAction = isTerminalState(record.state)
    ? { label: "View assessment package", destination: "../package" }
    : record.state === "reanalysis_required"
      ? { label: "Review changes and run analysis", destination: "../analysis" }
      : record.state === "additional_evidence_requested" || needsEvidenceReview
        ? { label: "Review shipment evidence", destination: "../evidence" }
        : { label: "Continue to final review", destination: "../final-review" };

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
        <p className="page-kicker">Shipment assessment</p>
      </header>
      <section aria-label="Report overview">
        <h2>Your analysis results</h2>
        <p className="muted">
          {round ? `Round ${round.round_index} recorded ${report.findings.length} finding${report.findings.length === 1 ? "" : "s"}.` : `${report.findings.length} finding${report.findings.length === 1 ? "" : "s"} recorded.`}
          {reviewingNewRound && round && round.round_index > 1
            ? ` This is the latest round; earlier rounds remain in Analysis history.`
            : ""}
        </p>
        <dl className="field-grid">
          <Field label="Findings recorded">{report.findings.length}</Field>
          <Field label="Requirements with missing information">
            {report.requirements_with_missing_information.length}
          </Field>
          <Field label="Requirements with uncertainty">{report.uncertain_requirement_ids.length}</Field>
          <Field label="Distinct requirements in those groups">{attentionCount}</Field>
          <Field label="Conflicting evidence items">{report.conflicting_evidence_count}</Field>
        </dl>
        <p className="muted">
          These are counts from Xportra&apos;s recorded analysis. They are not a compliance score,
          government decision, or approval to export.
        </p>
        {report.findings.length === 0 ? (
          <p className="muted" role="note">
            No findings were recorded in this analysis. That does not establish compliance or
            confirm that the shipment is cleared for export.
          </p>
        ) : null}
        <details className="finding-details">
          <summary>Report details</summary>
          <dl className="field-grid">
            <Field label="Report ID"><Identifier value={report.report_id} short={36} /></Field>
            <Field label="Shipment case"><Identifier value={report.case_id} short={36} /></Field>
            <Field label="Analysis round">
              {round ? `Round ${round.round_index} of ${record.rounds.length}` : "Not recorded on the current workflow"}
            </Field>
          </dl>
        </details>
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
        Filters use categories recorded in the report. Selecting one narrows this list only.
      </p>
      {visible.length === 0 ? (
        <p className="muted">No findings match this filter. Choose “All findings” to see the full report.</p>
      ) : null}
      {visible.map((finding) => (
        <FindingCard
          key={finding.analysis_id}
          finding={finding}
          index={report.findings.indexOf(finding)}
          total={report.findings.length}
          askAction={
            <AskXportraButton
              seed={{
                intent: "explain_finding",
                ...(isUuidLike(finding.requirement_id)
                  ? { requirementId: finding.requirement_id }
                  : {}),
                focus: "finding",
                suggestedText: "Why was this finding recorded?",
              }}
              label="Ask Xportra"
              className="link-button"
            />
          }
        />
      ))}
      <section className="finding-next-step" aria-label="Next shipment step">
        <h2>Next step</h2>
        <p className="muted">Continue based on this shipment&apos;s current workflow state.</p>
        <Link className="primary-button" to={nextAction.destination}>{nextAction.label}</Link>
      </section>
      <details className="finding-details">
        <summary>Other shipment actions</summary>
        <nav className="action-row" aria-label="Other shipment actions">
          <Link className="secondary-button" to={`../report/${encodeURIComponent(report.report_id)}`}>Open stored report</Link>
          <Link className="secondary-button" to="../evidence">Review shipment evidence</Link>
          <Link className="secondary-button" to="../additional-evidence">Request additional evidence</Link>
          <Link className="secondary-button" to="../analysis">Open analysis history</Link>
          <Link className="secondary-button" to="../final-review">Continue to final review</Link>
        </nav>
      </details>
    </div>
  );
}
