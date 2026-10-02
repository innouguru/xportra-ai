import { useState } from "react";
import { Link } from "react-router-dom";
import { useAnalysis } from "../../app/AnalysisContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { EmptyState } from "../../components/StatusBits";
import { isTerminalState } from "../../lib/workflow";
import { AnalysisPage } from "../analysis/AnalysisPage";
import { FindingsPage } from "../analysis/FindingsPage";
import { FinalReviewPage } from "./FinalReviewPage";
import { PackagePage } from "./PackagePage";
import { HistoryPage } from "./HistoryPage";

/**
 * Assessment — one journey across analysis stages.
 *
 * Tabs compose the existing assessment screens unchanged:
 * running analysis, reviewing findings, final review, the
 * stored package, and workflow history all keep their
 * backend contracts. The tabs only change how the stages
 * are reached — analysis rounds, findings, finalization
 * rules, and terminal closure are untouched.
 */

type AssessmentStage = "run" | "review" | "final" | "package" | "history";

const STAGES: Array<{ id: AssessmentStage; label: string; hint: string }> = [
  {
    id: "run",
    label: "Run analysis",
    hint: "Start or re-run an analysis round.",
  },
  {
    id: "review",
    label: "Review findings",
    hint: "Read what each recorded round established.",
  },
  {
    id: "final",
    label: "Final review",
    hint: "Check the package contents before finalizing.",
  },
  {
    id: "package",
    label: "Package",
    hint: "Read the finalized assessment package.",
  },
  {
    id: "history",
    label: "History",
    hint: "Workflow history and stored reports.",
  },
];

export function AssessmentPage() {
  const { record } = useWorkflow();
  const { report } = useAnalysis();
  const closed = record !== null && isTerminalState(record.state);
  const [stage, setStage] = useState<AssessmentStage>(() =>
    closed ? "package" : report ? "review" : "run",
  );

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

  const select = (next: AssessmentStage) => () => setStage(next);

  const onStageKeyDown = (event: React.KeyboardEvent) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") {
      return;
    }
    event.preventDefault();
    const order = STAGES.map((item) => item.id);
    const at = order.indexOf(stage);
    const step = event.key === "ArrowRight" ? 1 : -1;
    const next = order[(at + step + order.length) % order.length];
    setStage(next);
    document.getElementById(`assessment-tab-${next}`)?.focus();
  };

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Shipment assessment</p>
        <p className="lede">
          Analysis, findings, final review, and the assessment package as
          stages of one journey. Each stage reads what the backend already
          recorded — nothing here judges the shipment.
        </p>
      </header>
      <div className="filter-chips" role="tablist" aria-label="Assessment stages">
        {STAGES.map((item) => (
          <button
            key={item.id}
            id={`assessment-tab-${item.id}`}
            type="button"
            role="tab"
            aria-selected={stage === item.id}
            aria-controls={`assessment-panel-${item.id}`}
            tabIndex={stage === item.id ? 0 : -1}
            className="chip"
            title={item.hint}
            onClick={select(item.id)}
            onKeyDown={onStageKeyDown}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`assessment-panel-${stage}`}
        aria-labelledby={`assessment-tab-${stage}`}
      >
        {stage === "run" ? <AnalysisPage /> : null}
        {stage === "review" ? <FindingsPage /> : null}
        {stage === "final" ? <FinalReviewPage /> : null}
        {stage === "package" ? <PackagePage /> : null}
        {stage === "history" ? <HistoryPage /> : null}
      </div>
    </div>
  );
}
