import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../app/AuthContext";
import { useWorkflow } from "../app/WorkflowContext";
import { workflowStateLabel } from "../lib/workflow";

/**
 * Persistent application shell: brand, workflow context,
 * primary navigation, session area. Navigation follows the
 * shipment workflow; no hypothetical modules.
 */
export function AppShell({ title, actions, children }: {
  title: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const auth = useAuth();
  const { record, clear } = useWorkflow();
  const navigate = useNavigate();

  const startOver = () => {
    clear();
    navigate("/");
  };

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <div className="brand">
          <span className="brand-glyph" aria-hidden="true">
            X
          </span>
          <span className="brand-stack">
            <Link to="/" className="brand-mark" aria-label="Xportra AI home">
              Xportra&nbsp;AI
            </Link>
            <span className="brand-sub">Export Compliance Intelligence</span>
          </span>
        </div>
        <nav className="primary-nav" aria-label="Primary">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : undefined)}>
            New shipment
          </NavLink>
          <NavLink
            to="/workspace"
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            Workspace
          </NavLink>
        </nav>
        <div className="session-area">
          {record ? (
            <span className="session-context" title={`Workflow ${record.id}`}>
              <span className="session-dot session-dot--signed-in" aria-hidden="true" />
              {record.shipment_id ? `Shipment ${record.shipment_id.slice(0, 8)}…` : "Shipment"} ·{" "}
              {workflowStateLabel(record.state)}
            </span>
          ) : (
            <span className="session-context muted">
              <span className="session-dot" aria-hidden="true" />
              No active shipment
            </span>
          )}
          {record && (
            <button type="button" className="ghost-button" onClick={startOver}>
              Start over
            </button>
          )}
          {auth.isConfigured ? (
            <button type="button" className="ghost-button" onClick={auth.clear}>
              Sign out
            </button>
          ) : (
            <Link className="ghost-button" to="/session">
              Sign in
            </Link>
          )}
        </div>
      </header>
      <main id="main" className="main">
        <div className="page-head">
          <h1>{title}</h1>
          {actions ? <div className="page-actions">{actions}</div> : null}
        </div>
        {children}
      </main>
    </div>
  );
}
