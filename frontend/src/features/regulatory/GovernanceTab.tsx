import { StatusBadge } from "../../components/StatusBits";
import { useSourceContext } from "./SourceContext";
import { tone } from "./regulatoryUi";

/** Governance flags recorded against the source, verbatim. */
export function GovernanceTab() {
  const { flags } = useSourceContext();

  return (
    <div>
      <h2>Governance flags</h2>
      {flags.length === 0 ? (
        <p className="muted">No governance flags recorded for this source.</p>
      ) : (
        <ol className="ledger">
          {flags.map((flag) => (
            <li key={flag.id} className="ledger-row">
              <dl className="ledger-status">
                <div>
                  <dt>Status</dt>
                  <dd>
                    <StatusBadge value={flag.status} tone={tone(flag.status)} />
                  </dd>
                </div>
                <div>
                  <dt>Trigger</dt>
                  <dd>{flag.trigger_type}</dd>
                </div>
              </dl>
              <p className="ledger-reason">{flag.rationale}</p>
              <p className="muted">
                Pending flags cannot be cleared from this view. Flag
                completion follows the governance rules only.
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
