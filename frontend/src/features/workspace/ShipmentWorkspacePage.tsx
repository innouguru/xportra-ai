import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAnalysis } from "../../app/AnalysisContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { EmptyState } from "../../primitives/feedback";
import { BackButton, PageHeader } from "../../primitives/layout";
import { RequirementLedgerRow } from "../../primitives/shipment";
import { StatusIndicator } from "../../primitives/status";
import { AuthenticatedShell } from "../../shell/AuthenticatedShell";
import { listShipments } from "../../lib/shipments";
import { describeWorkspace, type WorkspaceRequirement } from "./workspace";
import { DocumentDrawer, type DrawerRequirement } from "./DocumentDrawer";
import "./workspace.css";

/**
 * Shipment workspace (approved redesign reference
 * `docs/design/xportra-ui-redesign.*`).
 *
 * One continuous compliance workspace, top to
 * bottom: shipment identity, current state,
 * Xportra's briefing, what needs attention
 * (blocking requirements only), and the full
 * requirement ledger. Evidence belongs to the
 * requirement it supports and opens through the
 * requirement drawer — there is no parallel
 * Documents section. Completed shipments render
 * read-only with no mutating controls. No
 * scores, no charts, no invented data.
 */

function synthesisFor(
  kind: string,
  addressed: number,
  total: number,
  suppliedCount: number,
): string {
  if (kind === "findings") {
    const requirements =
      total === 1 ? "1 requirement recorded" : `${total} requirements recorded`;
    const done =
      addressed === total
        ? "all addressed"
        : `${addressed} of ${total} addressed`;
    const documents =
      suppliedCount === 0
        ? "no documents supplied yet"
        : suppliedCount === 1
          ? "1 document supplied"
          : `${suppliedCount} documents supplied`;
    return `This shipment has ${requirements}, ${done}, with ${documents}.`;
  }
  if (kind === "open-count") {
    return "What applies here is still being established.";
  }
  return "No requirements identified yet. What applies here is still being established.";
}

function LedgerList({
  items,
  onOpen,
}: {
  items: WorkspaceRequirement[];
  onOpen: (requirement: DrawerRequirement) => void;
}) {
  return (
    <ul className="xb-ledger">
      {items.map((item) => (
        <RequirementLedgerRow
          key={item.id}
          name={item.title}
          why={item.explanation ?? undefined}
          state={item.statusLabel}
          tone={item.tone}
          onOpen={() =>
            onOpen({
              id: item.requirementId,
              title: item.title,
              statusLabel: item.statusLabel,
              tone: item.tone,
              explanation: item.explanation,
            })
          }
        />
      ))}
    </ul>
  );
}

export function ShipmentWorkspacePage() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const { record, setRecord } = useWorkflow();
  const { report } = useAnalysis();
  const [drawer, setDrawer] = useState<DrawerRequirement | null>(null);

  const entry = listShipments().find((item) => item.caseId === caseId) ?? null;

  useEffect(() => {
    if (entry && (!record || record.case_id !== entry.record.case_id)) {
      setRecord(entry.record);
    }
  }, [entry, record, setRecord]);

  const active = entry?.record ?? (record && record.case_id === caseId ? record : null);

  if (!active) {
    return (
      <AuthenticatedShell crumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Shipment" }]}>
        <BackButton label="Back" onBack={() => navigate("/dashboard")} />
        <PageHeader title="Shipment workspace" />
        <EmptyState
          title="No shipment open"
          body="Choose a shipment from your dashboard to open its workspace."
          action={
            <Link className="primary-button" to="/dashboard">
              Back to dashboard
            </Link>
          }
        />
      </AuthenticatedShell>
    );
  }

  const model = describeWorkspace(active, entry, report);
  const crumbs = [
    { label: "Dashboard", href: "/dashboard" },
    { label: "View Shipments", href: "/shipments" },
    { label: model.title },
  ];

  const attentionItems =
    model.requirements.kind === "findings"
      ? model.requirements.items.filter((item) => item.tone === "warning" || item.tone === "danger")
      : [];

  const meta: string[] = [];
  if (entry) {
    const quantity = entry.profile.quantity.trim();
    const unit = entry.profile.unit.trim();
    const amount = [quantity, unit].filter(Boolean).join(" ");
    if (amount) {
      meta.push(amount);
    }
    if (entry.profile.shipmentDate.trim()) {
      meta.push(entry.profile.shipmentDate.trim());
    }
  }

  const synthesis =
    model.requirements.kind === "findings" && model.progress
      ? synthesisFor("findings", model.progress.addressed, model.progress.total, model.suppliedCount)
      : model.requirements.kind === "open-count"
        ? synthesisFor("open-count", 0, 0, model.suppliedCount)
        : synthesisFor("none", 0, 0, model.suppliedCount);

  return (
    <AuthenticatedShell crumbs={crumbs}>
      {model.readOnly ? (
        <p className="xb-hist-banner" role="note">
          This shipment is <strong>complete</strong> and read-only. It&rsquo;s kept as a
          compliance record.
        </p>
      ) : null}
      <BackButton label="Your shipments" onBack={() => navigate("/shipments")} />
      <div className="xb-ws-identity">
        <p className="xb-ws-eyebrow">{model.readOnly ? "Completed shipment" : "Shipment"}</p>
        <h1 className="xb-ws-title">{model.title}</h1>
        {meta.length > 0 ? <p className="xb-ws-meta">{meta.join(" · ")}</p> : null}
      </div>

      <div className="xb-ws-state">
        <span
          className={`xb-row__dot xb-row__dot--${model.statusTone}`}
          aria-hidden="true"
        />
        <div>
          <p className="xb-ws-state__text">{model.briefing}</p>
          {model.briefingDetail ? (
            <p className="xb-ws-state__sub">{model.briefingDetail}</p>
          ) : null}
        </div>
      </div>

      <section className="xb-ws-briefing" aria-label="Xportra's briefing">
        <p className="xb-ws-briefing__label">Xportra&rsquo;s briefing</p>
        <p className="xb-ws-briefing__text">{synthesis}</p>
        {model.primaryAction && !model.readOnly ? (
          <p className="xb-ws-briefing__action">
            <Link className="primary-button" to={model.primaryAction.destination}>
              {model.primaryAction.label}
            </Link>
          </p>
        ) : null}
        {model.primaryAction && model.readOnly ? (
          <p className="xb-ws-briefing__action">
            <Link className="secondary-button" to={model.primaryAction.destination}>
              {model.primaryAction.label}
            </Link>
          </p>
        ) : null}
      </section>

      {attentionItems.length > 0 ? (
        <section aria-labelledby="xb-ws-attention">
          <h2 className="xb-ws-section-title" id="xb-ws-attention">
            What needs attention{" "}
            <span className="xb-ws-section-title__count">{attentionItems.length}</span>
          </h2>
          <LedgerList items={attentionItems} onOpen={setDrawer} />
        </section>
      ) : null}

      <section aria-labelledby="xb-ws-requirements">
        <h2 className="xb-ws-section-title" id="xb-ws-requirements">
          Requirements{" "}
          {model.requirements.kind === "findings" && model.progress ? (
            <span className="xb-ws-section-title__count">
              {model.progress.addressed} of {model.progress.total} addressed
            </span>
          ) : null}
        </h2>
        {model.requirements.kind === "findings" ? (
          <LedgerList items={model.requirements.items} onOpen={setDrawer} />
        ) : null}
        {model.requirements.kind === "open-count" ? (
          <p className="xb-ws-muted">
            {model.requirements.count} requirement{model.requirements.count === 1 ? " is" : "s are"} flagged
            open on this shipment.{" "}
            <Link to="/workspace/requirements">Review requirements</Link> to establish what
            applies before analysis runs.
          </p>
        ) : null}
        {model.requirements.kind === "none" ? (
          <p className="xb-ws-muted">
            No requirements identified yet.{" "}
            <Link to="/workspace/requirements">Establish requirements</Link> to begin.
          </p>
        ) : null}
      </section>

      <p className="xb-ws-status-line">
        <StatusIndicator tone={model.statusTone} label={model.statusLabel} />
      </p>
      {drawer ? (
        <DocumentDrawer requirement={drawer} onClose={() => setDrawer(null)} />
      ) : null}
    </AuthenticatedShell>
  );
}
