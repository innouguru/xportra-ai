import { Link } from "react-router-dom";
import {
  sourcePath,
  type NextAction,
  type ProgressStep,
  type SourceTab,
} from "./regulatoryUi";

/**
 * Where this source stands, drawn only from recorded rows. Each step is
 * labelled in text (not colour alone) and the current step carries
 * ``aria-current="step"``.
 */
export function SourceProgress({ steps }: { steps: ProgressStep[] }) {
  return (
    <ol className="reg-steps" aria-label="Source progress">
      {steps.map((step, index) => (
        <li
          key={step.key}
          className={`reg-step reg-step--${step.state}`}
          aria-current={step.state === "current" || step.state === "attention" ? "step" : undefined}
        >
          <span className="reg-step-label">
            <span className="reg-step-mark" aria-hidden="true">
              {step.state === "done" ? "✓" : step.state === "attention" ? "!" : index + 1}
            </span>
            {step.label}
          </span>
          <span className="reg-step-detail">{step.detail}</span>
        </li>
      ))}
    </ol>
  );
}

/**
 * One highlighted, single next step — the thing to do right now. The
 * link is offered only when it leads somewhere other than the tab the
 * person is already on, so it never duplicates the controls below it.
 */
export function NextActionCard({
  next,
  sourceId,
  activeTab,
}: {
  next: NextAction;
  sourceId: string;
  activeTab?: SourceTab;
}) {
  return (
    <section
      className={`reg-next reg-next--${next.kind}`}
      aria-label="Next step"
    >
      <div className="reg-next-text">
        <p className="reg-next-title">{next.title}</p>
        <p className="reg-next-body">{next.body}</p>
      </div>
      {next.tab !== activeTab ? (
        <Link to={sourcePath(sourceId, next.tab)} className="secondary-button">
          {next.cta}
        </Link>
      ) : null}
    </section>
  );
}
