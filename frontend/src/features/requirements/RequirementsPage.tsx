import { useState } from "react";
import { Link } from "react-router-dom";
import { determineApplicability, recordApplicability } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import type { ApplicabilityResponse } from "../../types/api";
import {
  EmptyState,
  ErrorNotice,
  LoadingState,
  StatusBadge,
} from "../../components/StatusBits";
import { applicabilityLabel, applicabilityTone } from "../../lib/workflow";

/**
 * Screen 3 — Requirements / applicability.
 *
 * Records the applicability outcome on the workflow, and
 * offers the deterministic per-requirement breakdown over
 * caller-supplied records. Outcomes render verbatim;
 * `unknown` means undecided, never failed.
 */

interface DraftRequirement {
  id: string;
  requirement_text: string;
  requirement_type: string;
  actor: string;
}

function newDraft(): DraftRequirement {
  return { id: "", requirement_text: "", requirement_type: "", actor: "" };
}

export function RequirementsPage() {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const [drafts, setDrafts] = useState<DraftRequirement[]>([newDraft()]);
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [commodity, setCommodity] = useState("");
  const [report, setReport] = useState<ApplicabilityResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<string | null>(null);

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

  const updateDraft = (index: number, patch: Partial<DraftRequirement>) => {
    setDrafts((current) => current.map((draft, i) => (i === index ? { ...draft, ...patch } : draft)));
  };

  const runBreakdown = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setPending("breakdown");
    try {
      const requirements = drafts
        .filter((draft) => draft.id.trim() && draft.requirement_text.trim())
        .map((draft) => ({
          id: draft.id.trim(),
          requirement_text: draft.requirement_text.trim(),
          ...(draft.requirement_type.trim() ? { requirement_type: draft.requirement_type.trim() } : {}),
          ...(draft.actor.trim() ? { actor: draft.actor.trim() } : {}),
        }));
      const result = await determineApplicability(auth, {
        requirements,
        exporter: origin.trim() ? { country_of_registration: origin.trim() } : null,
        product: commodity.trim() ? { commodity_code: commodity.trim() } : null,
        destination: destination.trim() ? { country_code: destination.trim() } : null,
      });
      setReport(result);
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const recordOutcome = async () => {
    setError(null);
    setPending("record");
    try {
      const response = await recordApplicability(auth, record);
      setRecord(response.workflow);
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Regulatory intelligence</p>
        <p className="lede">
          Establish which requirements apply to this shipment before evidence
          is weighed. Applicability is determined from the facts below —
          nothing here judges the shipment.
        </p>
      </header>
      <section aria-label="Record applicability outcome">
        <h2>Applicability outcome</h2>
        <p className="muted">
          Mark the deterministic applicability outcome on the workflow once the
          requirement set below is understood.
        </p>
        {error ? <ErrorNotice error={error} /> : null}
        <div className="action-row">
          <button
            type="button"
            className="primary-button"
            disabled={pending !== null}
            onClick={recordOutcome}
          >
            {pending === "record" ? "Recording…" : "Record applicability outcome"}
          </button>
        </div>
        {pending ? <LoadingState text="Updating workflow…" /> : null}
      </section>
      <section aria-label="Applicability breakdown">
        <h2>Requirement breakdown</h2>
        <p className="muted">
          Evaluated deterministically against the facts you supply. Outcomes
          are shown exactly as determined: <strong>unknown</strong> means not
          yet determined — never failed.
        </p>
        <form className="form" onSubmit={runBreakdown}>
          <fieldset>
            <legend>Case facts</legend>
            <div className="form-grid">
              <div className="form-row">
                <label htmlFor="origin-country">Origin country</label>
                <input
                  id="origin-country"
                  type="text"
                  value={origin}
                  onChange={(event) => setOrigin(event.target.value)}
                  placeholder="e.g. NG"
                />
              </div>
              <div className="form-row">
                <label htmlFor="destination-country">Destination country</label>
                <input
                  id="destination-country"
                  type="text"
                  value={destination}
                  onChange={(event) => setDestination(event.target.value)}
                  placeholder="e.g. NL"
                />
              </div>
              <div className="form-row">
                <label htmlFor="commodity-code">Commodity code</label>
                <input
                  id="commodity-code"
                  type="text"
                  value={commodity}
                  onChange={(event) => setCommodity(event.target.value)}
                  placeholder="e.g. 0901"
                />
              </div>
            </div>
          </fieldset>
          <fieldset>
            <legend>Requirement records</legend>
            {drafts.map((draft, index) => (
              <div className="form-grid" key={`requirement-draft-${index}`}>
                <div className="form-row">
                  <label htmlFor={`req-id-${index}`}>Requirement ID</label>
                  <input
                    id={`req-id-${index}`}
                    type="text"
                    value={draft.id}
                    onChange={(event) => updateDraft(index, { id: event.target.value })}
                    placeholder="Requirement identifier"
                  />
                </div>
                <div className="form-row">
                  <label htmlFor={`req-text-${index}`}>Requirement text</label>
                  <input
                    id={`req-text-${index}`}
                    type="text"
                    value={draft.requirement_text}
                    onChange={(event) => updateDraft(index, { requirement_text: event.target.value })}
                    placeholder="What the regulation requires"
                  />
                </div>
                <div className="form-row">
                  <label htmlFor={`req-type-${index}`}>Type (optional)</label>
                  <input
                    id={`req-type-${index}`}
                    type="text"
                    value={draft.requirement_type}
                    onChange={(event) => updateDraft(index, { requirement_type: event.target.value })}
                    placeholder="e.g. documentation"
                  />
                </div>
                <div className="form-row">
                  <label htmlFor={`req-actor-${index}`}>Actor (optional)</label>
                  <input
                    id={`req-actor-${index}`}
                    type="text"
                    value={draft.actor}
                    onChange={(event) => updateDraft(index, { actor: event.target.value })}
                    placeholder="e.g. exporter"
                  />
                </div>
              </div>
            ))}
            <div className="action-row">
              <button type="button" className="ghost-button" onClick={() => setDrafts((d) => [...d, newDraft()])}>
                Add requirement
              </button>
            </div>
          </fieldset>
          <button type="submit" className="primary-button" disabled={pending !== null}>
            {pending === "breakdown" ? "Evaluating…" : "Determine applicability"}
          </button>
        </form>
        {report ? (
          <div className="results-block">
            <h3>Determination</h3>
            <dl className="field-grid">
              {Object.entries(report.counts).map(([name, count]) => (
                <div className="field" key={name}>
                  <dt>{name.replace(/_/g, " ")}</dt>
                  <dd>{count}</dd>
                </div>
              ))}
            </dl>
            {report.results.length === 0 ? (
              <p className="muted">No requirement results returned.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Requirement</th>
                    <th scope="col">Outcome</th>
                    <th scope="col">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {report.results.map((result) => (
                    <tr key={result.requirement_id}>
                      <td>
                        <code className="identifier" title={result.requirement_id}>
                          {result.requirement_id.slice(0, 8)}…
                        </code>
                      </td>
                      <td>
                        <StatusBadge value={applicabilityLabel(result.outcome)} tone={applicabilityTone(result.outcome)} />
                      </td>
                      <td>{result.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );
}
