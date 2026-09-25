import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchStoredReport } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { FindingCard } from "../../components/FindingCard";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
} from "../../components/StatusBits";
import type { AnalysisReport } from "../../types/api";

/**
 * Screen 10 — Stored compliance report.
 *
 * Reads one report by identity and presents it in priority order:
 * assessment context → findings → evidence/support → missing
 * information → uncertainty and contradictions → authoritative
 * summary reference. Everything renders from the stored DTO: no count
 * is recomputed, no state is reinterpreted, `unknown` is never shown as
 * failure, and missing evidence is never shown as non-compliance.
 */
export function ReportPage() {
  const auth = useAuth();
  const { record } = useWorkflow();
  const { reportId } = useParams<{ reportId: string }>();
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!reportId) {
      return;
    }
    let cancelled = false;
    setPending(true);
    setError(null);
    fetchStoredReport(auth, reportId)
      .then((loaded) => {
        if (!cancelled) {
          setReport(loaded);
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
  }, [reportId]);

  if (!reportId) {
    return (
      <EmptyState
        title="No report selected"
        body="Open a stored report through a package or history reference that carries its identity."
        action={
          record ? (
            <Link className="primary-button" to="../package">
              Go to the assessment package
            </Link>
          ) : (
            <Link className="primary-button" to="/">
              Start a new shipment
            </Link>
          )
        }
      />
    );
  }

  if (pending) {
    return <LoadingState text="Reading the stored report…" />;
  }

  if (error) {
    return <ErrorNotice error={error} />;
  }

  if (!report) {
    return (
      <EmptyState
        title="Report unavailable"
        body="The stored report could not be loaded for this workspace."
      />
    );
  }

  const round = record
    ? record.rounds.find((item) => item.report_id === report.report_id)
    : undefined;
  const countEntries = Object.entries(report.counts ?? {});
  const findingsWithEvidence = report.findings.filter(
    (finding) =>
      finding.supporting_evidence.length > 0 || finding.conflicting_evidence.length > 0,
  );

  return (
    <div>
      <header className="doc-head">
        <p className="page-kicker">Xportra AI · Stored compliance report</p>
      </header>
      <section aria-label="Assessment context">
        <p className="eyebrow">Stored compliance report</p>
        <h2>Assessment context</h2>
        <dl className="field-grid">
          <Field label="Report">
            <Identifier value={report.report_id} short={36} />
          </Field>
          <Field label="Case">
            <Identifier value={report.case_id} short={36} />
          </Field>
          <Field label="Analysis round">
            {round ? (
              <>
                Round {round.round_index} of {record?.rounds.length} recorded
              </>
            ) : (
              <span className="muted">Not recorded on the client-held workflow record.</span>
            )}
          </Field>
          <Field label="Findings">{report.findings.length}</Field>
          {countEntries.map(([key, value]) => (
            <Field key={key} label={key.replace(/_/g, " ")}>
              {String(value)}
            </Field>
          ))}
          <Field label="Requirements with missing information">
            {report.requirements_with_missing_information.length}
          </Field>
          <Field label="Uncertain requirements">{report.uncertain_requirement_ids.length}</Field>
          <Field label="Conflicting evidence items">
            {report.conflicting_evidence_count}
          </Field>
        </dl>
        <p className="form-hint">
          Counters describe the stored report as received. They are not a compliance score, and
          this screen renders no verdict.
        </p>
      </section>

      <section aria-label="Report findings">
        <h2>Findings</h2>
        {report.findings.map((finding, position) => (
          <FindingCard
            key={finding.analysis_id}
            finding={finding}
            index={position}
            total={report.findings.length}
          />
        ))}
      </section>

      <section aria-label="Evidence and support">
        <h2>Evidence and support</h2>
        {findingsWithEvidence.length === 0 ? (
          <p className="muted">
            No evidence references were recorded on this report. That is a statement about
            recorded support, not a finding of non-compliance.
          </p>
        ) : (
          <ul className="reference-list">
            {findingsWithEvidence.map((finding) => (
              <li key={`evidence-${finding.analysis_id}`}>
                <p className="eyebrow">References for requirement</p>
                <p className="reference-id">
                  <Identifier value={finding.requirement_id} short={36} />
                </p>
                {finding.supporting_evidence.length > 0 ? (
                  <>
                    <h3>Supporting ({finding.supporting_evidence.length})</h3>
                    <ul className="reference-list reference-list--plain">
                      {finding.supporting_evidence.map((item, index) => (
                        <li key={`supporting-${finding.analysis_id}-${index}`}>
                          <ReferenceEntries reference={item} />
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {finding.conflicting_evidence.length > 0 ? (
                  <>
                    <h3>Conflicting — recorded, not resolved</h3>
                    <ul className="reference-list reference-list--plain">
                      {finding.conflicting_evidence.map((item, index) => (
                        <li key={`conflicting-${finding.analysis_id}-${index}`}>
                          <ReferenceEntries reference={item} />
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <p className="form-hint">
          Provenance and source records travel inside each finding above, in its sources
          disclosure.
        </p>
      </section>

      <section aria-label="Missing information">
        <h2>Missing information</h2>
        {report.requirements_with_missing_information.length === 0 ? (
          <p className="muted">No requirement carries missing information on this report.</p>
        ) : (
          <ul className="reference-list">
            {report.requirements_with_missing_information.map((requirementId) => {
              const finding = report.findings.find(
                (item) => item.requirement_id === requirementId,
              );
              return (
                <li key={requirementId}>
                  <p className="reference-id">
                    <Identifier value={requirementId} short={36} />
                  </p>
                  {finding && finding.missing_information.length > 0 ? (
                    <ul>
                      {finding.missing_information.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">
                      The report lists this requirement as carrying missing information without
                      further recorded detail.
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <p className="form-hint">
          Missing information is a request for information. It is never presented as
          non-compliance.
        </p>
      </section>

      <section aria-label="Uncertainty and contradictions">
        <h2>Uncertainty and contradictions</h2>
        <dl className="field-grid">
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
          <Field label="Conflicting evidence items">
            {report.conflicting_evidence_count}
          </Field>
        </dl>
        <p className="form-hint">
          Undecided states render verbatim as <code>unknown</code>: undecided, not failed.
        </p>
      </section>

      <section aria-label="Authoritative summary reference">
        <h2>Authoritative summary reference</h2>
        <p className="muted">
          A stored report carries findings and counters. The authoritative decision summary is
          carried by the workflow&apos;s final assessment package, where it is shown verbatim; it
          is not reconstructed from this report.
        </p>
        <div className="action-row">
          <Link className="secondary-button" to="../package">
            Assessment package
          </Link>
          <Link className="secondary-button" to="../history">
            Workflow history
          </Link>
        </div>
      </section>
    </div>
  );
}

/** Key/value evidence reference rendered verbatim from the DTO. */
function ReferenceEntries({ reference }: { reference: Record<string, unknown> }) {
  const entries = Object.entries(reference);
  if (entries.length === 0) {
    return <span className="muted">Empty reference</span>;
  }
  return (
    <dl className="field-grid">
      {entries.map(([key, value]) => (
        <Field key={key} label={key.replace(/_/g, " ")}>
          {typeof value === "string" && value.length > 40 ? (
            <Identifier value={value} short={36} />
          ) : (
            <span className="reference-value">{String(value ?? "")}</span>
          )}
        </Field>
      ))}
    </dl>
  );
}

