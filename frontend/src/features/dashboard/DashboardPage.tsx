import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useWorkflow } from "../../app/WorkflowContext";
import { ErrorState, EmptyState, LoadingState } from "../../primitives/feedback";
import { PageHeader } from "../../primitives/layout";
import { ShipmentWorklistRow } from "../../primitives/shipment";
import { AuthenticatedShell } from "../../shell/AuthenticatedShell";
import {
  loadDashboard,
  openShipment,
  type DashboardLoad,
  type DashboardShipment,
} from "./dashboard";
import "./dashboard.css";

/**
 * Dashboard: Your shipments (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * A shipment-resumption workspace, not an
 * analytics dashboard: a "Needs your attention"
 * block (hidden when empty), a compact recent
 * worklist, and a "View all" link. No KPI tiles,
 * no scores, no charts. All content derives from
 * the existing device-local registry
 * (`lib/shipments`) and existing process states
 * (`lib/workflow`); unavailable backend facts
 * (timestamps, missing-detail counts, scores)
 * are omitted, never fabricated. Rows open
 * through the existing workspace mechanism.
 */

function rowName(item: DashboardShipment): string {
  const product = item.entry.profile.product.trim();
  return product || item.title;
}

function rowRoute(item: DashboardShipment): string | undefined {
  const destination = item.entry.profile.destination.trim();
  return destination ? `→ ${destination}` : undefined;
}

export function DashboardPage() {
  const { setRecord } = useWorkflow();
  const navigate = useNavigate();
  const [load, setLoad] = useState<DashboardLoad | { status: "loading" }>({ status: "loading" });

  useEffect(() => {
    setLoad(loadDashboard());
  }, []);

  const reload = () => {
    setLoad({ status: "loading" });
    setLoad(loadDashboard());
  };

  const open = (item: DashboardShipment) =>
    openShipment(item.entry, setRecord, navigate, item.action.destination);

  return (
    <AuthenticatedShell crumbs={[{ label: "Dashboard" }]}>
      <PageHeader
        title="Your shipments"
        actions={
          <Link className="primary-button" to="/start">
            New shipment
          </Link>
        }
      />
      {load.status === "loading" ? <LoadingState text="Loading your shipments…" /> : null}
      {load.status === "error" ? (
        <ErrorState
          title="We couldn't load your shipments right now."
          message="Please try again."
          onRetry={reload}
        />
      ) : null}
      {load.status === "ready" && load.model.entries.length === 0 ? (
        <EmptyState
          title="You don't have any shipments yet."
          body="Start one to see what it needs."
          action={
            <Link className="primary-button" to="/start">
              New shipment
            </Link>
          }
        />
      ) : null}
      {load.status === "ready" && load.model.attention.length > 0 ? (
        <section aria-labelledby="dashboard-attention" className="xb-attention-block">
          <h2 id="dashboard-attention" className="xb-attention-block__label">
            Needs your attention
          </h2>
          <ul className="xb-attention-block__list">
            {load.model.attention.map((item) => (
              <li key={item.entry.caseId} className="xb-attention-block__item">
                <div className="xb-attention-block__main">
                  <p className="xb-attention-block__name">{rowName(item)}</p>
                  <p className="xb-attention-block__why">{item.attention}</p>
                </div>
                <button type="button" className="xb-row__go" onClick={() => open(item)}>
                  {item.action.label} <span aria-hidden="true">→</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {load.status === "ready" && load.model.recent.length > 0 ? (
        <section aria-labelledby="dashboard-recent">
          <div className="xb-dash-section-head">
            <h2 id="dashboard-recent">Recent shipments</h2>
            <Link className="xb-dash-section-head__link" to="/shipments">
              View all
            </Link>
          </div>
          <ul className="xb-worklist">
            {load.model.recent.map((item) => (
              <ShipmentWorklistRow
                key={item.entry.caseId}
                name={rowName(item)}
                route={rowRoute(item)}
                state={item.attention ?? item.statusLabel}
                tone={item.tone}
                href={item.action.destination}
                onSelect={() => open(item)}
              />
            ))}
          </ul>
        </section>
      ) : null}
    </AuthenticatedShell>
  );
}
