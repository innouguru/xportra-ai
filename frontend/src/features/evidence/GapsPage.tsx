import { useState } from "react";
import { Link } from "react-router-dom";
import { assessCaseReadiness } from "../../api/assessments";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import type { CaseReadiness } from "../../types/api";
import { CaseBuilder, buildCases, newCaseDraft, type CaseDraft } from "../../components/CaseBuilder";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
} from "../../components/StatusBits";
import { gapKindLabel, readinessTone } from "../../lib/evidence";

/**
 * Screen 5 — Evidence gaps and case readiness.
 *
 * Renders the backend readiness report verbatim:
 * readiness_state plus typed gaps. Missing, insufficient,
 * unknown, and contradictory states are shown as
 * information needs — never converted to non-compliant,
 * failed, scores, or percentages.
 */
export function GapsPage() {
  const auth = useAuth();
  const { record } = useWorkflow();
  const [drafts, setDrafts] = useState<CaseDraft[]>([newCaseDraft()]);
  const [report, setReport] = useState<CaseReadiness | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

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

  const assess = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const cases = buildCases(record.tenant_id, record.case_id, drafts);
      const result = await assessCaseReadiness(auth, cases);
      setReport(result);
    } catch (err) {
      setError(err);
    } finally {
      setPending(false);
    }
  };

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Evidence still needed</p>
      </header>
      <section aria-label="Evidence coverage">
        <h2>Evidence coverage</h2>
        <p className="muted">
          Assemble the case views from records you already hold, then ask
          the backend what information is still missing. Coverage here
          describes information — not compliance.
        </p>
        <form className="form" onSubmit={assess}>
          <CaseBuilder
            drafts={drafts}
            onChange={setDrafts}
            suppliedEvidenceIds={record.supplied_evidence_ids}
            idPrefix="gaps"
          />
          {error ? <ErrorNotice error={error} /> : null}
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? "Assessing…" : "Assess evidence coverage"}
          </button>
        </form>
        {pending ? <LoadingState text="Assessing evidence coverage…" /> : null}
      </section>
      {report ? (
        <section aria-label="Readiness outcome">
          <h2>
            Readiness: <StatusBadge value={report.readiness_state} tone={readinessTone(report.readiness_state)} />
          </h2>
          <dl className="field-grid">
            <Field label="Required information">{report.required_information}</Field>
            <Field label="Known information">{report.known_information}</Field>
            <Field label="Missing information items">{report.missing_information_count}</Field>
          </dl>
          {report.gaps.length === 0 ? (
            <p>No gaps reported — every required information item is known.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Requirement</th>
                  <th scope="col">Gap</th>
                  <th scope="col">Why it matters</th>
                </tr>
              </thead>
              <tbody>
                {report.gaps.map((gap, index) => (
                  <tr key={`${gap.requirement_id}-${index}`}>
                    <td>
                      <Identifier value={gap.requirement_id} />
                    </td>
                    <td>
                      <StatusBadge value={gapKindLabel(gap.kind)} tone="attention" />
                    </td>
                    <td>{gap.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="action-row">
            <Link className="secondary-button" to="../evidence">
              Supply evidence
            </Link>
            <Link className="secondary-button" to="../analysis">
              Run analysis
            </Link>
          </div>
        </section>
      ) : null}
    </div>
  );
}
