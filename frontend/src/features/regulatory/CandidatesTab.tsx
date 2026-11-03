import { Link } from "react-router-dom";
import { StatusBadge } from "../../components/StatusBits";
import { useSourceContext } from "./SourceContext";
import { candidatePath, tone } from "./regulatoryUi";

/** Extracted candidates; each opens its own review page. */
export function CandidatesTab() {
  const { sourceId, candidates } = useSourceContext();

  return (
    <div>
      <h2>Candidate requirements</h2>
      {candidates.length === 0 ? (
        <p className="muted">
          No candidates extracted or entered for this source. Manual candidate
          entry is not offered here because no authorized backend operation
          creates candidates by hand in this view — it would be a separate,
          backend-backed capability.
        </p>
      ) : (
        <ol className="ledger">
          {candidates.map((candidate) => (
            <li key={candidate.id} className="ledger-row">
              <p className="ledger-title">{candidate.requirement_text}</p>
              <dl className="ledger-status">
                <div>
                  <dt>Status</dt>
                  <dd>
                    <StatusBadge value={candidate.status} tone={tone(candidate.status)} />
                  </dd>
                </div>
                <div>
                  <dt>Extraction outcome</dt>
                  <dd>
                    <StatusBadge
                      value={candidate.extraction_outcome}
                      tone={tone(candidate.extraction_outcome)}
                    />
                  </dd>
                </div>
                <div>
                  <dt>Entry</dt>
                  <dd>{candidate.manual_entry ? "Manual" : "Extracted"}</dd>
                </div>
              </dl>
              <p className="ledger-actions">
                <Link to={candidatePath(sourceId, candidate.id)} className="link-button">
                  Review candidate
                </Link>
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
