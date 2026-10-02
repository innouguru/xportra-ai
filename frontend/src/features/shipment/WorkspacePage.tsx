import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useWorkflow } from "../../app/WorkflowContext";
import { AppShell } from "../../components/AppShell";
import { Collapsible, EmptyState, Field, Identifier } from "../../components/StatusBits";
import { isTerminalState, workflowStateLabel } from "../../lib/workflow";
import { listShipments } from "../../lib/shipments";
import { AskXportraButton } from "../conversation/AskXportraButton";
import { ConversationPanel } from "../conversation/ConversationPanel";
import { ConversationProvider } from "../conversation/ConversationContext";

/**
 * Shipment workspace shell: shipment identity, contextual
 * section navigation (Overview, Documents, Requirements,
 * Assessment), and the shared conversation surface.
 *
 * Identity leads with the human shipment profile
 * remembered on this device (origin → destination,
 * product); system identifiers stay secondary. Workflow
 * capabilities keep working through the established
 * screens, which remain mounted as deep links.
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
            <Link className="primary-button" to="/start">
              Start a new shipment
            </Link>
          }
        />
      </AppShell>
    );
  }

  const closed = isTerminalState(record.state);
  const profile =
    listShipments().find((item) => item.caseId === record.case_id)?.profile ?? null;
  const route = profile && profile.origin.trim() && profile.destination.trim()
    ? `${profile.origin.trim()} → ${profile.destination.trim()}`
    : null;
  const productLine = [
    profile?.product.trim() || null,
    [profile?.quantity.trim(), profile?.unit.trim()].filter(Boolean).join(" ") || null,
    profile?.shipmentDate.trim() || null,
  ].filter(Boolean);

  return (
    <ConversationProvider>
      <AppShell
        title="Shipment workspace"
        actions={
          <button type="button" className="ghost-button" onClick={() => navigate("/start")}>
            New shipment
          </button>
        }
        askAction={
          <AskXportraButton
            seed={{ intent: "summarize_shipment_state", focus: "shipment" }}
            label="Ask Xportra"
            className="ghost-button"
          />
        }
      >
        <header className="page-intro">
          <p className="page-kicker">Export compliance workspace</p>
        </header>
        <section className="shipment-hero" aria-label="Active shipment">
          <p className="eyebrow">Active shipment</p>
          <p className="shipment-hero__reference">
            {route ?? (record.shipment_id ? record.shipment_id : "Unbound shipment")}
          </p>
          {productLine.length > 0 ? (
            <p className="shipment-hero__product">{productLine.join(" · ")}</p>
          ) : null}
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
        <nav className="section-nav" aria-label="Shipment sections">
          <div className="section-nav__group">
            <NavLink to="." end className={({ isActive }) => (isActive ? "active" : undefined)}>
              Overview
            </NavLink>
            <NavLink to="documents" className={({ isActive }) => (isActive ? "active" : undefined)}>
              Documents
            </NavLink>
            <NavLink to="requirements" className={({ isActive }) => (isActive ? "active" : undefined)}>
              Requirements
            </NavLink>
            <NavLink to="assessment" className={({ isActive }) => (isActive ? "active" : undefined)}>
              Assessment
            </NavLink>
          </div>
          <div className="section-nav__group">
            <span className="section-nav__label" aria-hidden="true">
              Details
            </span>
            <NavLink to="info" className={({ isActive }) => (isActive ? "active" : undefined)}>
              Shipment details
            </NavLink>
            <NavLink to="shipments" className={({ isActive }) => (isActive ? "active" : undefined)}>
              All shipments
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
        <Outlet />
        <ConversationPanel />
      </AppShell>
    </ConversationProvider>
  );
}
