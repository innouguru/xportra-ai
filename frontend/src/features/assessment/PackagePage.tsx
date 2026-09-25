import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStoredPackage } from "../../api/workflows";
import { useAssessment } from "../../app/AssessmentContext";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { FindingCard } from "../../components/FindingCard";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
  TerminalNotice,
} from "../../components/StatusBits";
import { workflowStateLabel } from "../../lib/workflow";
import type { FinalPackage } from "../../types/api";

/**
 * Screen 9 — Stored final assessment package (terminal artifact).
 *
 * Reads the package exactly as stored: identities, state, round
 * count, the finalized report with its findings and received
 * counters, the open-requirement snapshot and the carried decision
 * summary. Read-only by design — no mutating control exists on
 * this screen, no count is recomputed into a score, and no overall
 * verdict is invented. Terminal status is communicated through
 * text, structure and the absence of controls, never color alone.
 */
function renderScalar(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

export function PackagePage() {
  const auth = useAuth();
  const { record } = useWorkflow();
  const { package: heldPackage, setPackage } = useAssessment();
  const [pkg, setPkg] = useState<FinalPackage | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!record) {
      return;
    }
    // Prefer the in-memory package only when it belongs to
    // the current workflow; otherwise read the stored one
    // (which also restores the artifact after a refresh).
    if (heldPackage && heldPackage.workflow_id === record.id) {
      setPkg(heldPackage);
      return;
    }
    let cancelled = false;
    setPending(true);
    setError(null);
    fetchStoredPackage(auth, record)
      .then((loaded) => {
        if (!cancelled) {
          setPkg(loaded);
          setPackage(loaded);
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
    return <LoadingState text="Reading the stored assessment package…" />;
  }

  if (error) {
    return (
      <>
        <ErrorNotice error={error} />
        <div className="action-row">
          <Link className="secondary-button" to="../final-review">
            Back to final review
          </Link>
        </div>
      </>
    );
  }

  if (!pkg) {
    return (
      <EmptyState
        title="No final package yet"
        body="This workflow has no stored assessment package. Review the latest findings and finalize explicitly to produce one."
        action={
          <Link className="primary-button" to="../final-review">
            Go to final review
          </Link>
        }
      />
    );
  }

  const report = pkg.report;
  const countEntries = Object.entries(report.counts ?? {});
  const summaryEntries =
    pkg.decision_summary !== null && pkg.decision_summary !== undefined
      ? Object.entries(pkg.decision_summary)
      : [];

  return (
    <div>
      <header className="doc-head">
        <p className="page-kicker">Xportra AI · Final assessment package</p>
      </header>
      <TerminalNotice title="Assessment package finalized — this workflow is permanently closed">
        <p>
          This package is the terminal artifact of a closed workflow. Additional evidence cannot
          be supplied, analysis cannot be rerun, and the current workflow offers no reopen or
          versioning operation. Nothing on this screen changes the workflow.
        </p>
        <dl className="field-grid">
          <Field label="Package state">
            <StatusBadge value={pkg.state} tone="neutral" />{" "}
            <span className="muted">— {workflowStateLabel(pkg.state)}</span>
          </Field>
          <Field label="Rounds recorded">{pkg.round_count}</Field>
          <Field label="Final report">
            <Identifier value={report.report_id} short={36} />
          </Field>
        </dl>
      </TerminalNotice>

      <section aria-label="Assessment record">
        <h2>Assessment record</h2>
        <p className="muted">
          Shipment and workspace identity exactly as stored with the package.
        </p>
        <dl className="field-grid">
          <Field label="Workflow">
            <Identifier value={pkg.workflow_id} short={36} />
          </Field>
          <Field label="Tenant">
            <Identifier value={pkg.tenant_id} short={36} />
          </Field>
          <Field label="Case">
            <Identifier value={pkg.case_id} short={36} />
          </Field>
          <Field label="Shipment">
            {pkg.shipment_id ? (
              <Identifier value={pkg.shipment_id} short={36} />
            ) : (
              <span className="muted">Unbound at finalization</span>
            )}
          </Field>
        </dl>
      </section>

      <section aria-label="Report counters as received">
        <h2>Report counters as received</h2>
        <p className="muted">
          Counters are shown exactly as the backend reported them with the finalized report. They
          are informational receipt counts — not a compliance score, rating, or percentage.
        </p>
        <dl className="field-grid">
          {countEntries.map(([key, value]) => (
            <Field key={key} label={key.replace(/_/g, " ")}>
              {String(value)}
            </Field>
          ))}
          <Field label="Requirements with missing information">
            {report.requirements_with_missing_information.length}
          </Field>
          <Field label="Uncertain requirements">{report.uncertain_requirement_ids.length}</Field>
          <Field label="Requirements with conflicting evidence">
            {report.requirements_with_conflicting_evidence.length}
          </Field>
          <Field label="Conflicting evidence items">
            {report.conflicting_evidence_count}
          </Field>
        </dl>
      </section>

      <section aria-label="Findings as finalized">
        <h2>Findings as finalized</h2>
        <p className="muted">
          Every finding is reproduced as stored: requirement, applicability, assessment,
          explanation, evidence references, sufficiency, missing information, contradictions and
          uncertainty. <code>unknown</code> means undecided and is never shown as failure;
          missing evidence remains an information need.
        </p>
        {report.findings.map((finding, position) => (
          <FindingCard
            key={finding.analysis_id}
            finding={finding}
            index={position}
            total={report.findings.length}
          />
        ))}
      </section>

      <section aria-label="Open requirements at finalization">
        <h2>Open requirements at finalization</h2>
        {pkg.open_requirements.length === 0 ? (
          <p className="muted">
            None outstanding — recorded as an empty snapshot, not as compliance.
          </p>
        ) : (
          <ul className="reference-list reference-list--plain">
            {pkg.open_requirements.map((id) => (
              <li key={id}>
                <Identifier value={id} short={36} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Missing information and uncertainty">
        <h2>Missing information and uncertainty</h2>
        <dl className="field-grid">
          <Field label="Requirements with missing information">
            {report.requirements_with_missing_information.length === 0 ? (
              <span className="muted">None recorded on this report.</span>
            ) : (
              <ul className="reference-list reference-list--plain">
                {report.requirements_with_missing_information.map((id) => (
                  <li key={id}>
                    <Identifier value={id} short={36} />
                  </li>
                ))}
              </ul>
            )}
          </Field>
          <Field label="Uncertain requirements">
            {report.uncertain_requirement_ids.length === 0 ? (
              <span className="muted">None recorded on this report.</span>
            ) : (
              <ul className="reference-list reference-list--plain">
                {report.uncertain_requirement_ids.map((id) => (
                  <li key={id}>
                    <Identifier value={id} short={36} />
                  </li>
                ))}
              </ul>
            )}
          </Field>
          <Field label="Requirements with conflicting evidence">
            {report.requirements_with_conflicting_evidence.length === 0 ? (
              <span className="muted">None recorded on this report.</span>
            ) : (
              <ul className="reference-list reference-list--plain">
                {report.requirements_with_conflicting_evidence.map((id) => (
                  <li key={id}>
                    <Identifier value={id} short={36} />
                  </li>
                ))}
              </ul>
            )}
          </Field>
        </dl>
        <p className="form-hint">
          Contradictions are recorded as found — this screen neither resolves nor ranks them.
        </p>
      </section>

      <section aria-label="Carried decision summary">
        <h2>Carried decision summary (reference)</h2>
        {summaryEntries.length === 0 ? (
          <p className="muted">
            No decision summary was carried with this package. It is shown verbatim when one was
            recorded on the latest result — nothing is reconstructed here.
          </p>
        ) : (
          <dl className="field-grid">
            {summaryEntries.map(([key, value]) => (
              <Field key={key} label={key.replace(/_/g, " ")}>
                {typeof value === "string" && value.length > 60 ? (
                  <Identifier value={value} short={48} />
                ) : (
                  <span className="reference-value">{renderScalar(value)}</span>
                )}
              </Field>
            ))}
          </dl>
        )}
      </section>

      <section aria-label="Stored references">
        <h2>Stored references</h2>
        <p className="muted">
          The package, its report and its workflow history remain readable after closure. No
          control on this screen mutates any of them.
        </p>
        <div className="action-row">
          <Link
            className="secondary-button"
            to={`../report/${encodeURIComponent(report.report_id)}`}
          >
            Open stored report
          </Link>
          <Link className="secondary-button" to="../history">
            View workflow history
          </Link>
          <Link className="secondary-button" to="../final-review">
            Review record
          </Link>
        </div>
      </section>
    </div>
  );
}

