import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { useStoredReport } from "../../app/useStoredReport";
import { EmptyState, LoadingState } from "../../primitives/feedback";
import { ErrorNotice } from "../../components/StatusBits";
import { BackButton, PageHeader } from "../../primitives/layout";
import { RequirementLedgerRow } from "../../primitives/shipment";
import { AuthenticatedShell } from "../../shell/AuthenticatedShell";
import { fetchShipmentList, DISCOVERY_PAGE_SIZE } from "../../api/shipments";
import { startWorkflow } from "../../api/workflows";
import { listShipments, rememberShipment, type ShipmentEntry } from "../../lib/shipments";
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
              sources: item.sources,
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
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  // Rehydrated persisted report when memory is empty, so a
  // reload never loses completed analysis from the workspace.
  const { report } = useStoredReport();
  const [drawer, setDrawer] = useState<DrawerRequirement | null>(null);
  const [serverEntry, setServerEntry] = useState<ShipmentEntry | null>(null);
  const [binding, setBinding] = useState(false);
  const [bindError, setBindError] = useState<unknown>(null);

  const cached = listShipments().find((item) => item.caseId === caseId) ?? null;
  // Server state wins: the durable entry shadows the
  // device cache whenever both resolve.
  const entry = serverEntry ?? cached;

  const recordRef = useRef(record);
  recordRef.current = record;

  useEffect(() => {
    let cancelled = false;
    // Resolve the durable entry so a reload resumes
    // from server state, not a stale snapshot. Where
    // the backend has no listing boundary the fetch
    // fails and the cached entry keeps working.
    fetchShipmentList(auth, { limit: DISCOVERY_PAGE_SIZE })
      .then((entries) => {
        if (cancelled) {
          return;
        }
        const found = entries.find((item) => item.caseId === caseId) ?? null;
        setServerEntry(found);
        const serverRecord = found?.record ?? null;
        if (
          serverRecord !== null &&
          JSON.stringify(serverRecord) !== JSON.stringify(recordRef.current)
        ) {
          setRecord(serverRecord);
        }
      })
      .catch(() => {
        // Keep the cached entry; it stays the fallback.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  useEffect(() => {
    if (entry && (!record || record.case_id !== entry.record?.case_id)) {
      if (entry.record) {
        setRecord(entry.record);
      }
    }
  }, [entry, record, setRecord]);

  const active = entry?.record ?? (record && record.case_id === caseId ? record : null);

  const beginWorkspace = async () => {
    if (!entry?.shipmentId || !entry) {
      return;
    }
    setBinding(true);
    setBindError(null);
    try {
      // Bind the saved shipment through the existing
      // start endpoint (identity only — the server
      // owns the profile). No new contract.
      const response = await startWorkflow(auth, {
        case_id: entry.caseId,
        shipment_id: entry.shipmentId,
      });
      setRecord(response.workflow);
      rememberShipment({ ...entry, record: response.workflow });
    } catch (error) {
      setBindError(error);
    } finally {
      setBinding(false);
    }
  };

  if (!active) {
    if (entry?.shipmentId) {
      return (
        <AuthenticatedShell crumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Shipment" }]}>
          <BackButton label="Back" onBack={() => navigate("/dashboard")} />
          <PageHeader title="Shipment workspace" />
          <EmptyState
            title="Saved shipment — begin its compliance workspace"
            body="This shipment is saved on the server but has no compliance workspace yet. Continue to begin where the shipment left off."
            action={
              binding ? (
                <LoadingState text="Beginning the workspace…" />
              ) : (
                <button type="button" className="primary-button" onClick={beginWorkspace}>
                  Continue
                </button>
              )
            }
          />
          {bindError ? <ErrorNotice error={bindError} /> : null}
        </AuthenticatedShell>
      );
    }
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

  const synthesis = model.suppliedCount === 1
    ? "1 document supplied to this workflow."
    : `${model.suppliedCount} documents supplied to this workflow.`;

  return (
    <AuthenticatedShell crumbs={crumbs}>
      {model.readOnly ? (
        <p className="xb-hist-banner" role="note">
          The Xportra assessment package is <strong>complete</strong> and read-only. This does not
          mean a government authority has approved or cleared the shipment.
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
          <p className="xb-ws-state__text">
            {model.statusLabel} <span aria-hidden="true">—</span> {model.briefing}
          </p>
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

      <section aria-labelledby="xb-ws-requirements">
        <h2 className="xb-ws-section-title" id="xb-ws-requirements">
          {model.requirements.kind === "findings" ? "Requirements and findings" : "Requirements"}{" "}
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
            {model.requirements.count} information item{model.requirements.count === 1 ? " is" : "s are"} flagged
            open, but details are not available in this shipment view.{" "}
            <Link to="/workspace/evidence">View shipment documents</Link> or inspect the existing
            records on the <Link to="/workspace/requirements">requirements page</Link>.
          </p>
        ) : null}
        {model.requirements.kind === "none" ? (
          <p className="xb-ws-muted">
            No requirement records are available to show here. You can still upload shipment
            documents; Xportra is not presenting a complete export checklist.{" "}
            <Link to="/workspace/evidence">View shipment documents</Link>.
          </p>
        ) : null}
      </section>

      {drawer ? (
        <DocumentDrawer requirement={drawer} onClose={() => setDrawer(null)} />
      ) : null}
    </AuthenticatedShell>
  );
}
