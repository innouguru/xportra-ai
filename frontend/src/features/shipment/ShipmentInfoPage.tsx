import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { noteEvidencePending, provideInformation } from "../../api/workflows";
import { fetchShipmentDetail } from "../../api/shipments";
import { fetchCatalogRequirements, type CatalogRequirementItem } from "../../api/catalog";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
} from "../../components/StatusBits";
import { isTerminalState, workflowStateLabel } from "../../lib/workflow";

/**
 * Screen 2 — Shipment information.
 *
 * Structured sections (identity, then information steps)
 * rather than one giant form. Each action posts the
 * client-held record and retains the updated record from
 * the response.
 */
export function ShipmentInfoPage() {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const [error, setError] = useState<unknown>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [savedAction, setSavedAction] = useState<string | null>(null);

  // Regulatory catalog state (component scope)
  const [regulatoryRequirements, setRegulatoryRequirements] = useState<{
    items: CatalogRequirementItem[];
    total: number;
    limit: number;
    offset: number;
  } | null>(null);
  const [regulatoryLoading, setRegulatoryLoading] = useState(false);
  const [regulatoryError, setRegulatoryError] = useState<unknown>(null);

  // Shipment detail state (authoritative source for product/origin/destination)
  const [shipmentLoading, setShipmentLoading] = useState(false);

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

  const run = async (action: string, label: string, call: () => Promise<{ workflow: typeof record }>) => {
    setError(null);
    setSavedAction(null);
    setPendingAction(action);
    try {
      const response = await call();
      setRecord(response.workflow);
      setSavedAction(label);
    } catch (err) {
      setError(err);
    } finally {
      setPendingAction(null);
    }
  };

  // Fetch shipment detail and regulatory requirements when record changes
  useEffect(() => {
    let cancelled = false;

    const loadShipmentAndCatalog = async () => {
      setRegulatoryRequirements(null);
      setRegulatoryError(null);
      setRegulatoryLoading(false);

      if (!record.shipment_id) {
        setRegulatoryError(
          new Error(
            "Shipment requires product, origin country, and destination country to determine applicable regulatory requirements. Please ensure these fields are completed."
          )
        );
        setRegulatoryRequirements({ items: [], total: 0, limit: 20, offset: 0 });
        return;
      }

      setShipmentLoading(true);
      try {
        const entry = await fetchShipmentDetail(auth, record.shipment_id);
        if (cancelled) return;
        // entry used for scope below

        if (!entry) {
          setRegulatoryError(new Error("Shipment not found or not accessible."));
          setRegulatoryRequirements({ items: [], total: 0, limit: 20, offset: 0 });
          return;
        }

        const product = entry.profile.product.trim();
        const origin = entry.profile.origin.trim();
        const destination = entry.profile.destination.trim();

        if (!product || !origin || !destination) {
          setRegulatoryRequirements({ items: [], total: 0, limit: 20, offset: 0 });
          setRegulatoryError(
            new Error(
              "Shipment requires product, origin country, and destination country to determine applicable regulatory requirements. Please ensure these fields are completed."
            )
          );
          return;
        }

        setRegulatoryLoading(true);
        setRegulatoryError(null);

        try {
          const response = await fetchCatalogRequirements(auth, {
            product,
            origin_country: origin,
            destination_country: destination,
            limit: 20,
            offset: 0,
          });
          if (cancelled) return;
          setRegulatoryRequirements(response);
        } catch (err) {
          if (cancelled) return;
          setRegulatoryError(err);
          setRegulatoryRequirements(null);
        } finally {
          if (!cancelled) setRegulatoryLoading(false);
        }
      } catch (err) {
        if (cancelled) return;
        setRegulatoryError(err);
        setRegulatoryRequirements(null);
        setRegulatoryLoading(false);
      } finally {
        if (!cancelled) setShipmentLoading(false);
      }
    };

    loadShipmentAndCatalog();

    return () => {
      cancelled = true;
    };
  }, [record.shipment_id, auth.token, auth.devTenantId]);

  const renderRegulatoryRequirementsSection = () => {
    const items: CatalogRequirementItem[] = regulatoryRequirements?.items ?? [];
    const total = regulatoryRequirements?.total ?? 0;

    const allApplicable = items.every(
      (item: CatalogRequirementItem) => item.applicability.outcome === "applicable"
    );
    const hasUnknownApplicability = items.some(
      (item: CatalogRequirementItem) => item.applicability.outcome !== "applicable" && item.applicability.outcome !== "not_applicable"
    );

    const applicabilityStatus = total === 0
      ? "No requirements found for this shipment's scope"
      : hasUnknownApplicability
      ? `Some requirements have unverified applicability. ${total} requirement${total !== 1 ? "s" : ""} returned, but applicability is not confirmed for all.`
      : allApplicable
      ? `${total} requirement${total !== 1 ? "s" : ""} applicable to this shipment's scope`
      : `${total} requirement${total !== 1 ? "s" : ""} returned, but not all are applicable to this shipment's scope`;

    if (shipmentLoading || regulatoryLoading) {
      return (
        <div className="xb-requirements-section">
          <h2>Regulatory Requirements</h2>
          <LoadingState text="Loading regulatory requirements…" />
        </div>
      );
    }

    if (regulatoryError) {
      return (
        <div className="xb-requirements-section">
          <h2>Regulatory Requirements</h2>
          <ErrorNotice error={regulatoryError} />
        </div>
      );
    }

    if (items.length === 0) {
      return (
        <div className="xb-requirements-section">
          <h2>Regulatory Requirements</h2>
          <EmptyState
            title="No regulatory requirements"
            body={applicabilityStatus}
            action={
              <p className="muted">No published requirements are applicable to this shipment's product, origin, and destination scope.</p>
            }
          />
        </div>
      );
    }

    return (
      <div className="xb-requirements-section">
        <h2>Regulatory Requirements</h2>
        <p className="muted">{applicabilityStatus}</p>
        <ol className="xb-requirements-list">
          {items.map((item: CatalogRequirementItem) => (
            <li key={item.requirement_id} className="xb-requirement-item">
              <div className="xb-requirement-header">
                <h3 className="xb-requirement-title">{item.requirement_text}</h3>
                <div className="xb-requirement-meta">
                  <span className="xb-source-reference">
                    Source: {item.source.source_title}
                  </span>
                  <span className="xb-jurisdiction">
                    {item.source.source_jurisdiction}
                  </span>
                  <span className="xb-applicability-badge">
                    {item.applicability.outcome === "applicable" ? "Applicable" : item.applicability.outcome}
                  </span>
                </div>
              </div>
              <p className="xb-requirement-description">
                {item.requirement_text}
              </p>
              <div className="xb-requirement-scope">
                <span>Product: {item.requirement_type || "—"}</span>
                <span>Origin: {item.applicability.context_fingerprint || "—"}</span>
                <span>Destination: {item.stage_b_pilot_scope || "—"}</span>
              </div>
              <div className="xb-requirement-citation">
                Citation: {item.citation.normalized_document_id ? "Available" : "—"}
              </div>
            </li>
          ))}
        </ol>
      </div>
    );
  };


  const busy = pendingAction !== null;
  const closed = isTerminalState(record.state);
  const locked = busy || closed;

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Shipment record</p>
      </header>
      <section aria-label="Shipment identity">
        <h2>Shipment identity</h2>
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
          <Field label="Shipment reference">
            {record.shipment_id ? (
              <Identifier value={record.shipment_id} />
            ) : (
              <span className="muted">No shipment bound yet</span>
            )}
          </Field>
          <Field label="Current state">
            <span className="state-label">{workflowStateLabel(record.state)}</span>
          </Field>
        </dl>
      </section>
      <section aria-label="Information steps">
        <h2>Information steps</h2>
        <p className="muted">
          Recording information moves the workflow forward. Each step is a
          process marker — it judges nothing about the shipment.
        </p>
        {error ? <ErrorNotice error={error} /> : null}
        {closed ? (
          <p className="muted">
            This workflow is finalized and permanently closed: information steps can no longer be
            recorded, and the backend rejects any post-finalization mutation.
          </p>
        ) : null}
        {savedAction && !busy ? (
          <p className="form-hint" role="status">
            Saved — {savedAction} recorded on the workflow.
          </p>
        ) : null}
        <div className="action-row">
          <button
            type="button"
            className="primary-button"
            disabled={locked}
            onClick={() => run("provide", "Shipment information", () => provideInformation(auth, record))}
          >
            {pendingAction === "provide" ? "Recording…" : "Provide shipment information"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={locked}
            onClick={() => run("pending", "Evidence pending", () => noteEvidencePending(auth, record))}
          >
            {pendingAction === "pending" ? "Recording…" : "Mark evidence pending"}
          </button>
          <Link className="secondary-button" to="../requirements">
            Continue to requirements
          </Link>
        </div>

        {busy ? <LoadingState text="Updating workflow…" /> : null}
      </section>
      {renderRegulatoryRequirementsSection()}
    </div>
  );
}
