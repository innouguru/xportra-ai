import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchStoredReport } from "../../api/workflows";
import { fetchEvidence, fetchEvidenceDownload } from "../../api/evidence";
import { useAuth } from "../../app/AuthContext";
import { EmptyState, ErrorState, LoadingState } from "../../primitives/feedback";
import { BackButton, PageHeader } from "../../primitives/layout";
import { RequirementLedgerRow } from "../../primitives/shipment";
import { StatusIndicator } from "../../primitives/status";
import { AuthenticatedShell } from "../../shell/AuthenticatedShell";
import { listShipments, shipmentDisplayName } from "../../lib/shipments";
import { isTerminalState } from "../../lib/workflow";
import type { AnalysisReport, EvidenceRecord } from "../../types/api";
import { requirementVocabulary } from "../workspace/workspace";

/**
 * Historical compliance report (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * Read-only record for a completed shipment: a
 * persistent read-only banner, shipment
 * identity, a past-tense final assessment, and
 * the full requirements ledger in its final
 * state. Supplied documents stay readable;
 * regulatory sources stay secondary. No
 * timestamps, scores, identifiers, or reasoning
 * internals are shown — none exist at the
 * boundary. No mutation control renders here
 * under any circumstance; non-terminal
 * shipments get an honest redirect notice
 * instead. There is no PDF boundary, so no
 * Download PDF control.
 */

interface SourceView {
  key: string;
  title: string;
  detail: string | null;
}

/** Only safe human-readable string fields; shapes vary, so cherry-pick. */
function sourceViews(sources: Array<Record<string, unknown>>): SourceView[] {
  const seen = new Set<string>();
  const views: SourceView[] = [];
  sources.forEach((source, index) => {
    const title =
      (typeof source["title"] === "string" && source["title"]) ||
      (typeof source["identifier"] === "string" && source["identifier"]) ||
      (typeof source["source_id"] === "string" && source["source_id"]) ||
      null;
    const detail =
      (typeof source["url"] === "string" && source["url"]) ||
      (typeof source["source_url"] === "string" && source["source_url"]) ||
      (typeof source["location"] === "string" && source["location"]) ||
      (typeof source["source_location"] === "string" && source["source_location"]) ||
      null;
    if (title || detail) {
      const key = `${title ?? ""}||${detail ?? ""}`;
      if (!seen.has(key)) {
        seen.add(key);
        views.push({ key: `${index}-${key}`, title: title ?? "Recorded source", detail });
      }
    }
  });
  return views;
}

type ReportLoad =
  | { status: "loading" }
  | { status: "ready"; report: AnalysisReport | null }
  | { status: "error" };

export function HistoricalReportPage() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const [load, setLoad] = useState<ReportLoad>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [evidence, setEvidence] = useState<Record<string, EvidenceRecord | null>>({});

  const entry = listShipments().find((item) => item.caseId === caseId) ?? null;
  const record = entry?.record ?? null;
  const terminal = record ? isTerminalState(record.state) : false;
  const reportId =
    terminal && record && record.rounds.length > 0
      ? record.rounds[record.rounds.length - 1].report_id
      : null;

  useEffect(() => {
    if (!terminal || !reportId) {
      setLoad({ status: "ready", report: null });
      return;
    }
    let cancelled = false;
    setLoad({ status: "loading" });
    fetchStoredReport(auth, reportId)
      .then((loaded) => {
        if (!cancelled) {
          setLoad({
            status: "ready",
            report: loaded.case_id === record?.case_id ? loaded : null,
          });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoad({ status: "error" });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId, attempt]);

  useEffect(() => {
    if (!terminal || !record || record.supplied_evidence_ids.length === 0) {
      return;
    }
    let cancelled = false;
    void (async () => {
      const rows = await Promise.all(
        record.supplied_evidence_ids.map(async (id): Promise<[string, EvidenceRecord | null]> => {
          try {
            return [id, await fetchEvidence(auth, id)];
          } catch {
            return [id, null];
          }
        }),
      );
      if (!cancelled) {
        setEvidence((current) => {
          const next = { ...current };
          for (const [id, row] of rows) {
            if (!(id in next)) {
              next[id] = row;
            }
          }
          return next;
        });
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record?.supplied_evidence_ids.join(",")]);

  const openDocument = async (evidenceId: string) => {
    try {
      const grant = await fetchEvidenceDownload(auth, evidenceId);
      window.open(grant.download_url, "_blank", "noopener,noreferrer");
    } catch {
      // Download failures stay silent here: the row already
      // identifies the document and the workspace stays usable.
    }
  };

  const crumbs = [
    { label: "Dashboard", href: "/dashboard" },
    { label: "View Shipments", href: "/shipments" },
    { label: "Historical report" },
  ];

  if (!entry || !record) {
    return (
      <AuthenticatedShell crumbs={crumbs}>
        <BackButton label="Back to Your shipments" onBack={() => navigate("/shipments")} />
        <PageHeader title="Historical report" />
        <EmptyState
          title="Report unavailable"
          body="No completed shipment on this device matches that reference."
          action={
            <Link className="primary-button" to="/shipments">
              Back to Your shipments
            </Link>
          }
        />
      </AuthenticatedShell>
    );
  }

  if (!terminal) {
    return (
      <AuthenticatedShell crumbs={crumbs}>
        <BackButton label="Back to Your shipments" onBack={() => navigate("/shipments")} />
        <PageHeader title="Historical report" />
        <EmptyState
          title="This shipment is still active."
          body="Historical reports cover completed shipments only. Active work continues in the shipment workspace."
          action={
            <Link className="primary-button" to={`/shipments/${entry.caseId}`}>
              Open shipment workspace
            </Link>
          }
        />
      </AuthenticatedShell>
    );
  }

  const title = shipmentDisplayName(entry);
  const report = load.status === "ready" ? load.report : null;
  const findings = report?.findings ?? [];
  const addressed = findings.filter((finding) => finding.assessment === "satisfied").length;
  const sources = sourceViews(findings.flatMap((finding) => finding.sources));
  const profile = entry.profile;
  const detailRows = [
    { label: "Product", value: profile.product.trim() || null },
    { label: "Origin", value: profile.origin.trim() || null },
    { label: "Destination", value: profile.destination.trim() || null },
    { label: "Quantity", value: profile.quantity.trim() || null },
    { label: "Unit", value: profile.unit.trim() || null },
    { label: "Shipment date", value: profile.shipmentDate.trim() || null },
  ].filter((row) => row.value !== null);
  const meta: string[] = [];
  const amount = [profile.quantity.trim(), profile.unit.trim()].filter(Boolean).join(" ");
  if (amount) {
    meta.push(amount);
  }
  if (profile.shipmentDate.trim()) {
    meta.push(profile.shipmentDate.trim());
  }

  return (
    <AuthenticatedShell crumbs={crumbs}>
      <p className="xb-hist-banner" role="note">
        This shipment is <strong>complete</strong> and read-only. It&rsquo;s kept as a
        compliance record.
      </p>
      <BackButton label="Back to Your shipments" onBack={() => navigate("/shipments")} />
      <div className="xb-ws-identity">
        <p className="xb-ws-eyebrow">Completed shipment</p>
        <h1 className="xb-ws-title">{title}</h1>
        {meta.length > 0 ? <p className="xb-ws-meta">{meta.join(" · ")}</p> : null}
      </div>
      <p className="xb-ws-status-line">
        <StatusIndicator tone="success" label="Completed" />
      </p>
      <div className="xb-ws-layout">
        <div className="xb-ws-main">
          <section aria-label="Final result">
            <div className="xb-ws-briefing">
              <p className="xb-ws-briefing__message">Assessment finalized.</p>
              <p className="xb-ws-briefing__detail">
                {findings.length > 0
                  ? `${addressed} of ${findings.length} requirements addressed. This record cannot be changed, reopened, or re-finalized.`
                  : "No recorded findings for this shipment. This record cannot be changed, reopened, or re-finalized."}
              </p>
            </div>
          </section>
          {load.status === "loading" ? <LoadingState text="Reading the stored report…" /> : null}
          {load.status === "error" ? (
            <ErrorState
              title="We couldn’t read the stored report."
              message="The shipment summary above is intact — please try again for the findings."
              onRetry={() => setAttempt((count) => count + 1)}
            />
          ) : null}
          {load.status === "ready" && findings.length > 0 ? (
            <section aria-labelledby="xb-hist-requirements">
              <h2 className="xb-ws-section-title" id="xb-hist-requirements">
                Requirements{" "}
                <span className="xb-ws-section-title__count">
                  {addressed} of {findings.length} satisfied
                </span>
              </h2>
              <ul className="xb-ledger">
                {findings.map((finding) => {
                  const words = requirementVocabulary(finding.assessment);
                  return (
                    <RequirementLedgerRow
                      key={finding.analysis_id || finding.requirement_id}
                      name={finding.requirement_text || "Requirement"}
                      why={finding.explanation.trim() || undefined}
                      state={words.label}
                      tone={words.tone}
                    />
                  );
                })}
              </ul>
            </section>
          ) : null}
          <section aria-labelledby="xb-hist-evidence">
            <h2 className="xb-ws-section-title" id="xb-hist-evidence">
              Evidence
            </h2>
            {record.supplied_evidence_ids.length === 0 ? (
              <p className="xb-ws-muted">No documents recorded for this shipment.</p>
            ) : (
              <ul className="xb-ws-missing">
                {record.supplied_evidence_ids.map((id, index) => {
                  const detail = evidence[id];
                  const name = detail?.document_title || `Document ${index + 1}`;
                  const kind = detail?.document_type ? ` · ${detail.document_type}` : "";
                  return (
                    <li key={id}>
                      {name}
                      {kind}{" "}
                      <button
                        type="button"
                        className="xb-ws-link"
                        onClick={() => void openDocument(id)}
                      >
                        Open document
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
          {sources.length > 0 ? (
            <section aria-labelledby="xb-hist-sources">
              <h2 className="xb-ws-section-title" id="xb-hist-sources">
                Regulatory sources
              </h2>
              <ul className="xb-ws-missing">
                {sources.map((source) => (
                  <li key={source.key}>
                    {source.title}
                    {source.detail ? (
                      <span className="xb-ws-muted"> · {source.detail}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <section aria-labelledby="xb-hist-completion">
            <h2 className="xb-ws-section-title" id="xb-hist-completion">
              Completion record
            </h2>
            <p className="xb-ws-muted">
              {record.rounds.length} analysis round{record.rounds.length === 1 ? "" : "s"} recorded.
              Assessment finalized — read-only.
            </p>
            <p>
              <Link className="secondary-button" to="/start">
                New shipment
              </Link>
            </p>
          </section>
        </div>
        <aside className="xb-ws-aside" aria-label="Shipment summary">
          <section aria-labelledby="xb-hist-summary">
            <h2 className="xb-ws-section-title" id="xb-hist-summary">
              Shipment summary
            </h2>
            {detailRows.length > 0 ? (
              <dl className="xb-summary">
                {detailRows.map((row) => (
                  <div key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="xb-ws-muted">No profile remembered for this shipment on this device.</p>
            )}
          </section>
        </aside>
      </div>
    </AuthenticatedShell>
  );
}
