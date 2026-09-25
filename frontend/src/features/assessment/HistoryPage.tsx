import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchWorkflowHistory } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
} from "../../components/StatusBits";
import { historyKindLabel, readReference, referenceLabel } from "../../lib/history";
import { workflowStateLabel } from "../../lib/workflow";
import type { HistoryResponse } from "../../types/api";

/**
 * Screen 11 — Workflow history.
 *
 * The backend history is a PROJECTION over recorded identifiers, not
 * event sourcing: entries arrive grouped by kind in a fixed presentation
 * order, and the workflow retains no timestamps at all. This screen
 * therefore renders the received order without inventing chronology, and
 * copies no reasoning content into history.
 */
function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

export function HistoryPage() {
  const auth = useAuth();
  const { record } = useWorkflow();
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!record) {
      return;
    }
    let cancelled = false;
    setPending(true);
    setError(null);
    fetchWorkflowHistory(auth, record)
      .then((loaded) => {
        if (!cancelled) {
          setHistory(loaded);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPending(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record?.id]);

  if (!record) {
    return (
      <EmptyState
        title="No active shipment"
        body="Open a compliance case first."
        action={
          <Link className="primary-button" to="/">
            Start a new shipment
          </Link>
        }
      />
    );
  }

  if (pending) {
    return <LoadingState text="Reading workflow history…" />;
  }

  if (error) {
    return <ErrorNotice error={error} />;
  }

  if (!history) {
    return (
      <EmptyState
        title="No history yet"
        body="History appears once the workflow has recorded entries."
      />
    );
  }

  const readiness = asRecord(history.readiness);
  const finalPackage = asRecord(history.final_package);
  const readinessState = asString(readiness?.["readiness_state"]);
  const gaps = Array.isArray(readiness?.["gaps"]) ? (readiness?.["gaps"] as unknown[]) : [];
  const packageReportId = asString(finalPackage?.["report_id"]);

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Workflow record</p>
      </header>
      <section aria-label="History overview">
        <p className="eyebrow">Workflow history projection</p>
        <h2>Workflow history — {workflowStateLabel(history.state)}</h2>
        <dl className="field-grid">
          <Field label="Workflow">
            <Identifier value={history.workflow_id} short={36} />
          </Field>
          <Field label="Tenant">
            <Identifier value={history.tenant_id} short={36} />
          </Field>
          <Field label="Case">
            <Identifier value={history.case_id} short={36} />
          </Field>
          <Field label="Shipment">
            {history.shipment_id ? (
              <Identifier value={history.shipment_id} short={36} />
            ) : (
              <span className="muted">Not bound</span>
            )}
          </Field>
          <Field label="State">
            <StatusBadge value={history.state} tone="neutral" />
          </Field>
          <Field label="Rounds recorded">{history.round_count}</Field>
          <Field label="Latest report">
            {history.latest_report_id ? (
              <Link to={`../report/${encodeURIComponent(history.latest_report_id)}`}>
                <Identifier value={history.latest_report_id} short={36} />
              </Link>
            ) : (
              <span className="muted">None recorded.</span>
            )}
          </Field>
          <Field label="Evidence supplied">
            {history.supplied_evidence_ids.length} reference
            {history.supplied_evidence_ids.length === 1 ? "" : "s"}
          </Field>
          <Field label="Open requirements reported">
            {history.open_requirements.length}
          </Field>
          <Field label="Decision summary">
            {history.decision_summary_present ? (
              "Reported as carried on the latest result."
            ) : (
              <span className="muted">Not reported in this projection.</span>
            )}
          </Field>
          <Field label="Final package">
            {finalPackage ? (
              <>
                Referenced as ready — round count {String(finalPackage["round_count"] ?? "—")}
                {packageReportId ? (
                  <>
                    {" "}
                    ·{" "}
                    <Link to={`../report/${encodeURIComponent(packageReportId)}`}>
                      <Identifier value={packageReportId} short={36} />
                    </Link>
                  </>
                ) : null}
              </>
            ) : (
              <span className="muted">
                Not reported in this projection — the package is readable on the Assessment
                package screen once finalized.
              </span>
            )}
          </Field>
        </dl>
        <p className="muted">
          History lists identifiers the workflow already recorded. It is a projection, not an
          event stream: the workflow stores no timestamps, so none are shown, and entries appear
          in the backend&apos;s grouped order rather than a merged chronology.
        </p>
      </section>

      {readiness ? (
        <section aria-label="Readiness in this projection">
          <h2>Readiness in this projection</h2>
          <dl className="field-grid">
            <Field label="Readiness state">
              {readinessState ? (
                <StatusBadge value={readinessState} tone="neutral" />
              ) : (
                <span className="muted">Not reported.</span>
              )}
            </Field>
            <Field label="Required information">
              {asNumber(readiness["required_information"]) ?? "—"}
            </Field>
            <Field label="Known information">
              {asNumber(readiness["known_information"]) ?? "—"}
            </Field>
            <Field label="Missing information items">
              {asNumber(readiness["missing_information_count"]) ?? "—"}
            </Field>
            <Field label="Gaps reported">{gaps.length}</Field>
          </dl>
          <p className="form-hint">
            Readiness describes information coverage. It is not a compliance verdict, and this
            screen draws no conclusion from it.
          </p>
        </section>
      ) : null}

      <section aria-label="History entries">
        <h2>Entries in recorded order</h2>
        {history.entries.length === 0 ? (
          <p className="muted">No entries recorded for this workflow yet.</p>
        ) : (
          <ol className="history-projection">
            {history.entries.map((entry) => (
              <li key={entry.sequence} className="history-entry">
                <p className="eyebrow">
                  {entry.sequence + 1} · {historyKindLabel(entry.kind)}
                </p>
                <p>{entry.detail}</p>
                {entry.references.length > 0 ? (
                  <dl className="field-grid history-references">
                    {entry.references.map((reference, index) => {
                      const view = readReference(reference);
                      return (
                        <Field
                          key={`${entry.sequence}-${index}`}
                          label={
                            view.label ? referenceLabel(view.label) : `reference ${index + 1}`
                          }
                        >
                          <Identifier value={view.value} short={36} />
                        </Field>
                      );
                    })}
                  </dl>
                ) : null}
              </li>
            ))}
          </ol>
        )}
        <p className="form-hint">
          Entries are grouped by kind and shown in the order the backend recorded them. Reasoning
          content lives with its findings and report, not here.
        </p>
      </section>
    </div>
  );
}

