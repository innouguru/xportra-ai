import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useWorkflow } from "../../app/WorkflowContext";
import { AppShell } from "../../components/AppShell";
import { Stepper } from "../../components/Stepper";
import { Collapsible, EmptyState, Field, Identifier } from "../../components/StatusBits";
import { isTerminalState, journeyStepForState, workflowStateLabel } from "../../lib/workflow";

/**
 * Shipment workspace shell: header with shipment reference,
 * workflow state and current step, journey stepper, and
 * section navigation. Requires an active workflow record.
 */
export function WorkspacePage() {
  const { record } = useWorkflow();
  const navigate = useNavigate();

  if (!record) {
    return (
      <AppShell title="Shipment workspace">
        <EmptyState
          title="No active shipment"
          body="Open a compliance case first. The workspace shows the shipment, its requirements, evidence, analysis, and assessment once a case exists."
          action={
            <Link className="primary-button" to="/">
              Start a new shipment
            </Link>
          }
        />
      </AppShell>
    );
  }

  const step = journeyStepForState(record.state);
  const closed = isTerminalState(record.state);

  return (
    <AppShell
      title="Shipment workspace"
      actions={
        <button type="button" className="ghost-button" onClick={() => navigate("/")}>
          New shipment
        </button>
      }
    >
      <header className="page-intro">
        <p className="page-kicker">Export compliance workspace</p>
      </header>
      <section className="shipment-hero" aria-label="Active shipment">
        <p className="eyebrow">Active shipment</p>
        <p className="shipment-hero__reference">
          {record.shipment_id ? record.shipment_id : "Unbound shipment"}
        </p>
        <dl className="shipment-hero__meta">
          <div>
            <dt>Workflow state</dt>
            <dd>
              <span className="state-label">{workflowStateLabel(record.state)}</span>
              <span className="muted">
                {closed
                  ? " — permanently closed; the assessment package is final"
                  : " — process position, not a compliance verdict"}
              </span>
            </dd>
          </div>
          <div>
            <dt>Evidence supplied</dt>
            <dd>{record.supplied_evidence_ids.length} references</dd>
          </div>
          <div>
            <dt>Analysis rounds</dt>
            <dd>{record.rounds.length} completed</dd>
          </div>
        </dl>
      </section>
      <Collapsible title="Workflow identifiers">
        <dl className="field-grid">
          <Field label="Workflow">
            <Identifier value={record.id} />
          </Field>
          <Field label="Case">
            <Identifier value={record.case_id} />
          </Field>
          <Field label="Shipment">
            {record.shipment_id ? <Identifier value={record.shipment_id} /> : <span className="muted">Unbound</span>}
          </Field>
        </dl>
      </Collapsible>
      <Stepper state={record.state} current={step} />
      <nav className="section-nav" aria-label="Workspace sections">
        <div className="section-nav__group">
          <span className="section-nav__label" aria-hidden="true">
            Workspace
          </span>
          <NavLink to="info" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Shipment information
          </NavLink>
          <NavLink to="requirements" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Requirements
          </NavLink>
          <NavLink to="evidence" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Evidence
          </NavLink>
          <NavLink to="gaps" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Evidence gaps
          </NavLink>
          <NavLink
            to="additional-evidence"
            title="Supply the evidence that was requested, then re-run analysis"
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            Additional evidence
          </NavLink>
          <NavLink to="analysis" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Analysis
          </NavLink>
          <NavLink to="review" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Review
          </NavLink>
        </div>
        <div className="section-nav__group">
          <span className="section-nav__label" aria-hidden="true">
            Assessment
          </span>
          <NavLink to="final-review" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Final review
          </NavLink>
          <NavLink to="package" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Assessment package
          </NavLink>
          {record.rounds.length > 0 ? (
            <NavLink
              to={`report/${encodeURIComponent(record.rounds[record.rounds.length - 1].report_id)}`}
              className={({ isActive }) => (isActive ? "active" : undefined)}
            >
              Latest report
            </NavLink>
          ) : null}
          <NavLink to="history" className={({ isActive }) => (isActive ? "active" : undefined)}>
            History
          </NavLink>
        </div>
      </nav>
      <Outlet />
    </AppShell>
  );
}
