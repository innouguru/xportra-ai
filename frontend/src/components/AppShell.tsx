import { Link, NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../app/AuthContext";
import { useSignOut } from "../app/useSignOut";
import { useWorkflow } from "../app/WorkflowContext";
import { workflowStateLabel } from "../lib/workflow";
import { BrandMark } from "./BrandMark";

/**
 * Persistent application shell: brand, primary navigation,
 * session area. Navigation follows product concepts, not
 * internal workflow stages:
 *
 * - Without an active shipment: the public site map
 *   (Product, How It Works, For Exporters, Resources)
 *   plus Sign in and Start a shipment.
 * - With an active shipment: Overview, Shipments,
 *   Documents, Requirements, Assessment, plus secondary
 *   Ask Xportra (provided by the workspace) and Settings.
 */
export function AppShell({ title, actions, askAction, children }: {
  title: string;
  actions?: React.ReactNode;
  /** Secondary conversational entry; rendered only where provided. */
  askAction?: React.ReactNode;
  children: React.ReactNode;
}) {
  const auth = useAuth();
  const { record, clear } = useWorkflow();
  const navigate = useNavigate();
  const signOut = useSignOut();
  const [signOutError, setSignOutError] = useState(false);
  // Session state, not the client-held workflow record, decides
  // whether authenticated product navigation is rendered.
  const signedIn = auth.isConfigured;

  const startOver = () => {
    clear();
    navigate("/start");
  };

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <BrandMark />
        {signedIn && record ? (
          <>
            <nav className="primary-nav" aria-label="Primary">
              <NavLink to="/workspace" end className={({ isActive }) => (isActive ? "active" : undefined)}>
                Overview
              </NavLink>
              <NavLink
                to="/workspace/shipments"
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                Shipments
              </NavLink>
              <NavLink
                to="/workspace/documents"
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                Documents
              </NavLink>
              <NavLink
                to="/workspace/requirements"
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                Requirements
              </NavLink>
              <NavLink
                to="/workspace/assessment"
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                Assessment
              </NavLink>
            </nav>
            <nav className="shipment-nav" aria-label="Secondary">
              {askAction}
              <NavLink
                to="/settings"
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                Settings
              </NavLink>
            </nav>
          </>
        ) : (
          <>
            <nav className="primary-nav" aria-label="Primary">
              <a href="/#product">Product</a>
              <a href="/#how-it-works">How It Works</a>
              <a href="/#for-exporters">For Exporters</a>
              <a href="/#resources">Resources</a>
            </nav>
            <nav className="shipment-nav" aria-label="Secondary">
              <NavLink
                to="/session"
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                Sign in
              </NavLink>
              <NavLink
                to="/start"
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                Start a shipment
              </NavLink>
            </nav>
          </>
        )}
        <div className="session-area">
          {signedIn && record ? (
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
          {signedIn && record && (
            <button type="button" className="ghost-button" onClick={startOver}>
              Start over
            </button>
          )}
          {signedIn ? (
            <button
              type="button"
              className="ghost-button"
              onClick={async () => setSignOutError(!(await signOut()))}
            >
              Sign out
            </button>
          ) : (
            <Link className="ghost-button" to="/session">
              Sign in
            </Link>
          )}
          {signOutError ? <p role="alert">We could not sign you out. Check your connection and try again.</p> : null}
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
