import { Link } from "react-router-dom";
import { useAnalysis } from "../../app/AnalysisContext";
import { useWorkflow } from "../../app/WorkflowContext";
import {
  Collapsible,
  EmptyState,
  Field,
  Identifier,
  StatusBadge,
} from "../../components/StatusBits";
import {
  isTerminalState,
  journeyStepStatuses,
  workflowStateLabel,
  type StepStatus,
} from "../../lib/workflow";

/**
 * Screen 0 — Shipment overview (command center).
 *
 * The shipment is the persistent product object; the workflow
 * is an implementation mechanism. This screen answers, from
 * already-available client state only:
 *
 * 1. What shipment am I looking at?
 * 2. What is its assessment state?
 * 3. What has been established?
 * 4. What needs attention?
 * 5. What can I do next?
 *
 * No scores, no verdicts, no invented attributes: every row
 * renders identifiers, counts, and states the backend (or
 * the client-held record) already reported. `unknown` and
 * missing information stay information needs, never failure.
 */

interface AreaState {
  id: string;
  label: string;
  to: string;
  status: StepStatus | "complete-closed";
  detail: string;
}

interface AttentionItem {
  title: string;
  detail: string;
  to: string;
  tone: "attention" | "neutral";
}

function areaTone(status: AreaState["status"]): "attention" | "neutral" {
  return status === "action-required" ? "attention" : "neutral";
}

function areaStateText(status: AreaState["status"]): string {
  switch (status) {
    case "complete":
      return "Established";
    case "complete-closed":
      return "Closed";
    case "current":
      return "In progress";
    case "action-required":
      return "Needs attention";
    default:
      return "Pending";
  }
}

export function WorkspaceOverview() {
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

  const closed = isTerminalState(record.state);
  const journey = journeyStepStatuses(record.state);
  const shortReference = record.shipment_id
    ? `${record.shipment_id.slice(0, 8)}…`
    : "Unbound shipment";
  const assessmentLine = closed
    ? "Assessment finalized"
    : record.state === "review_required"
      ? "Assessment in review"
      : "Assessment in progress";

  const areas: AreaState[] = [
    {
      id: "shipment",
      label: "Shipment",
      to: "info",
      status: journey.shipment,
      detail: record.shipment_id ? "Reference bound" : "No reference bound",
    },
    {
      id: "requirements",
      label: "Requirements",
      to: "requirements",
      status: journey.requirements,
      detail:
        record.open_requirements.length > 0
          ? `${record.open_requirements.length} flagged open`
          : "None flagged open",
    },
    {
      id: "evidence",
      label: "Evidence",
      to: "evidence",
      status: journey.evidence,
      detail: `${record.supplied_evidence_ids.length} supplied`,
    },
    {
      id: "analysis",
      label: "Analysis",
      to: "analysis",
      status: journey.analysis,
      detail:
        record.rounds.length === 0
          ? "No rounds yet"
          : `${record.rounds.length} round${record.rounds.length === 1 ? "" : "s"} recorded`,
    },
    {
      id: "assessment",
      label: "Assessment",
      to: closed ? "package" : "final-review",
      status: closed
        ? "complete-closed"
        : record.state === "review_required"
          ? "current"
          : "upcoming",
      detail: closed
        ? "Package finalized"
        : record.rounds.length === 0
          ? "Nothing to review yet"
          : "Findings recorded",
    },
  ];

  const attention: AttentionItem[] = [];
  if (closed) {
    attention.push({
      title: "Finalized — read-only",
      detail:
        "This workflow is permanently closed. The assessment package and its report stay readable; nothing here can change them.",
      to: "package",
      tone: "neutral",
    });
  } else {
    if (record.state === "additional_evidence_requested") {
      attention.push({
        title: "Additional evidence requested",
        detail:
          record.open_requirements.length > 0
            ? `${record.open_requirements.length} requirement${record.open_requirements.length === 1 ? " is" : "s are"} flagged open. Supplying evidence records information — it does not establish compliance.`
            : "The workflow records that more information is needed. Supplying evidence records information — it does not establish compliance.",
        to: "additional-evidence",
        tone: "attention",
      });
    }
    if (record.state === "reanalysis_required") {
      attention.push({
        title: "Re-analysis required",
        detail:
          "Evidence was supplied since the last recorded round. Re-running analysis is your explicit decision — it never happens automatically.",
        to: "analysis",
        tone: "attention",
      });
    }
    if (record.state === "review_required") {
      attention.push({
        title: "Findings ready for review",
        detail: "The latest analysis round is recorded and waiting for your review.",
        to: "review",
        tone: "attention",
      });
    }
    if (record.open_requirements.length > 0 && record.state !== "additional_evidence_requested") {
      attention.push({
        title: `${record.open_requirements.length} open requirement${record.open_requirements.length === 1 ? "" : "s"}`,
        detail: "Requirements flagged open on this workflow still need information.",
        to: "additional-evidence",
        tone: "attention",
      });
    }
    if (record.supplied_evidence_ids.length === 0) {
      attention.push({
        title: "No evidence supplied yet",
        detail: "Register an evidence reference, then supply it so analysis can consider it.",
        to: "evidence",
        tone: "attention",
      });
    }
    if (record.rounds.length === 0) {
      attention.push({
        title: "No analysis yet",
        detail: "Run the first analysis round once shipment information is recorded.",
        to: "analysis",
        tone: "attention",
      });
    }
    if (report) {
      if (report.requirements_with_missing_information.length > 0) {
        attention.push({
          title: `${report.requirements_with_missing_information.length} with missing information`,
          detail: "The latest report records information that is still needed — an information need, not non-compliance.",
          to: "review",
          tone: "attention",
        });
      }
      if (report.uncertain_requirement_ids.length > 0) {
        attention.push({
          title: `${report.uncertain_requirement_ids.length} uncertain`,
          detail: "Undecided states in the latest report need a closer look — undecided, not failed.",
          to: "review",
          tone: "attention",
        });
      }
      if (report.conflicting_evidence_count > 0) {
        attention.push({
          title: `${report.conflicting_evidence_count} conflicting evidence item${report.conflicting_evidence_count === 1 ? "" : "s"}`,
          detail: "Recorded contradictions are preserved for review — shown as recorded, not resolved.",
          to: "review",
          tone: "attention",
        });
      }
    }
  }

  const latestReportId =
    record.rounds.length > 0 ? record.rounds[record.rounds.length - 1].report_id : null;

  return (
    <div className="overview">
      <header className="overview-identity">
        <p className="page-kicker">Export shipment</p>
        <h2 className="overview-reference">{shortReference}</h2>
        <p className="overview-state">
          <StatusBadge value={record.state} tone="neutral" />{" "}
          <span className="state-label">{assessmentLine}</span>{" "}
          <span className="muted">— {workflowStateLabel(record.state)}</span>
        </p>
      </header>

      <section aria-label="Assessment status">
        <h3 className="overview-heading">Assessment status</h3>
        <ol className="status-strip" aria-label="Assessment areas">
          {areas.map((area) => (
            <li key={area.id} className={`status-cell status-cell--${area.status}`}>
              <p className="eyebrow">{area.label}</p>
              <p className="status-cell__state">
                <StatusBadge value={areaStateText(area.status)} tone={areaTone(area.status)} />
              </p>
              <p className="status-cell__detail">{area.detail}</p>
              <p className="status-cell__action">
                <Link to={area.to}>Open {area.label.toLowerCase()}</Link>
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-label="Attention">
        <h3 className="overview-heading">Attention</h3>
        {attention.length === 0 ? (
          <p className="muted">
            No open items recorded. Information coverage beyond this screen lives with the
            findings review and evidence gaps.
          </p>
        ) : (
          <ul className="attention-list">
            {attention.map((item) => (
              <li key={item.title} className={`attention-item attention-item--${item.tone}`}>
                <div>
                  <p className="attention-item__title">{item.title}</p>
                  <p className="muted">{item.detail}</p>
                </div>
                <Link className="secondary-button" to={item.to}>
                  {closed ? "Open package" : "Review now"}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Workspace areas">
        <h3 className="overview-heading">Workspace</h3>
        <dl className="workspace-areas">
          <div>
            <dt>
              <Link to="info">Shipment information</Link>
            </dt>
            <dd>Record the facts this case is built on.</dd>
          </div>
          <div>
            <dt>
              <Link to="requirements">Requirements</Link>
            </dt>
            <dd>Establish what applies to this shipment.</dd>
          </div>
          <div>
            <dt>
              <Link to="evidence">Evidence</Link>
            </dt>
            <dd>Register and supply evidence references.</dd>
          </div>
          <div>
            <dt>
              <Link to="analysis">Analysis</Link>
            </dt>
            <dd>
              {record.rounds.length === 0
                ? "Run the first analysis round."
                : `Review rounds or run round ${record.rounds.length + 1}.`}
            </dd>
          </div>
          <div>
            <dt>
              <Link to={closed ? "package" : "final-review"}>Assessment</Link>
            </dt>
            <dd>
              {closed
                ? "Read the finalized assessment package."
                : "Review findings before finalizing."}
            </dd>
          </div>
          {latestReportId ? (
            <div>
              <dt>
                <Link to={`report/${encodeURIComponent(latestReportId)}`}>Latest report</Link>
              </dt>
              <dd>Read the latest stored analysis report.</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <Collapsible title="Technical details">
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
          <Field label="Shipment">
            {record.shipment_id ? (
              <Identifier value={record.shipment_id} />
            ) : (
              <span className="muted">Unbound</span>
            )}
          </Field>
          <Field label="Workflow state">
            <Identifier value={record.state} />
          </Field>
          <Field label="Rounds recorded">{record.rounds.length}</Field>
        </dl>
      </Collapsible>
    </div>
  );
}
