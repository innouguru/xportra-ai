import { useState } from "react";
import { Link } from "react-router-dom";
import { noteEvidencePending, provideInformation } from "../../api/workflows";
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
import type { CatalogRequirementItem } from "../../api/regulatory";
import { apiFetch } from "../../api/client";
import type { AuthCredentials } from "../../api/client";

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

    // Fetch regulatory requirements when a shipment record is available
    if (record) {
      fetchRegulatoryRequirements(auth);
    }
  };

  // Fetch regulatory requirements for the current shipment's scope
  const fetchRegulatoryRequirements = async (credentials: AuthCredentials) => {
    if (!record) return;

    const product = record.profile.product.trim();
    const origin = record.profile.origin.trim();
    const destination = record.profile.destination.trim();

    // Fail closed when essential scope information is missing
    if (!product || !origin || !destination) {
      setRegulatoryRequirements({
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
      });
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
      const response = await apiFetch<{
        items: CatalogRequirementItem[];
        total: number;
        limit: number;
        offset: number;
      }>("/catalog/requirements", credentials, {
        method: "GET",
        body: {
          product,
          origin_country: origin,
          destination_country: destination,
          limit: 20,
          offset: 0,
        },
      });

      setRegulatoryRequirements(response);
    } catch (err) {
      setRegulatoryError(err);
      setRegulatoryRequirements(null);
    } finally {
      setRegulatoryLoading(false);
    }
  };

  // Regulatory requirements state
  const [regulatoryRequirements, setRegulatoryRequirements] = useState<
    | {
        items: CatalogRequirementItem[];
        total: number;
        limit: number;
        offset: number;
      }
    | null
  >(null);
  const [regulatoryLoading, setRegulatoryLoading] = useState(false);
  const [regulatoryError, setRegulatoryError] = useState<unknown>(null);

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
{renderRegulatoryRequirementsSection()}
        {busy ? <LoadingState text="Updating workflow…" /> : null}
      </section>
    </div>
    );
  }
  
  // Render the regulatory requirements section
  const renderRegulatoryRequirementsSection = () => {
    const { items, total } = regulatoryRequirements ?? {};
    
    // Determine if applicability is verified
    const allApplicable = items.every(
      (item) => item.applicability.outcome === "applicable"
    );
    const hasUnknownApplicability = items.some(
      (item) => item.applicability.outcome !== "applicable" && item.applicability.outcome !== "not_applicable"
    );
    
    // If there are items with unknown applicability, communicate that
    const applicabilityStatus = total === 0
      ? "No requirements found for this shipment's scope"
      : hasUnknownApplicability
      ? `Some requirements have unverified applicability. ${total} requirement${total !== 1 ? "s" : ""} returned, but applicability is not confirmed for all.`
      : allApplicable
      ? `${total} requirement${total !== 1 ? "s" : ""} applicable to this shipment's scope`
      : `${total} requirement${total !== 1 ? "s" : ""} returned, but not all are applicable to this shipment's scope`;
    
    if (regulatoryLoading) {
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
    
    if (!items || items.length === 0) {
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
          {items.map((item) => (
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
