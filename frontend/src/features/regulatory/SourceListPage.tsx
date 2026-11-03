import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { AuthCredentials } from "../../api/client";
import { listRegulatorySources, type RegulatorySource } from "../../api/regulatory";
import { useAuth } from "../../app/AuthContext";
import {
  EmptyState,
  ErrorNotice,
  LoadingState,
  StatusBadge,
} from "../../components/StatusBits";
import { REGULATORY_BASE, sourcePath, tone } from "./regulatoryUi";

/** Entry page: every registered source, newest first, and a way to add one. */
export function SourceListPage() {
  const auth = useAuth() as AuthCredentials;
  const [sources, setSources] = useState<RegulatorySource[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listRegulatorySources(auth);
      setSources(response.items);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  const registerLink = (
    <Link to={`${REGULATORY_BASE}/new`} className="primary-button">
      Register source
    </Link>
  );

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Regulatory administration</p>
        <p className="lede">
          Authorized staff view for regulatory sources, ingestion, candidate
          review, and governance flags. Authorization is enforced by the
          server for every action shown here; the server remains the
          authority. Nothing on this page publishes a requirement or marks it
          exporter-applicable.
        </p>
        {registerLink}
      </header>

      {loading ? <LoadingState text="Loading regulatory sources…" /> : null}
      {error ? <ErrorNotice error={error} onRetry={() => void load()} /> : null}
      {!loading && !error && sources !== null && sources.length === 0 ? (
        <EmptyState
          title="No regulatory sources registered"
          body="Use Register source above to add the first one and begin ingestion. This view lists what exists — it does not fabricate records."
        />
      ) : null}

      {sources !== null && sources.length > 0 ? (
        <section aria-label="Regulatory sources">
          <h2>Regulatory sources</h2>
          <ol className="ledger">
            {sources.map((source) => (
              <li key={source.id} className="ledger-row">
                <p className="ledger-title">{source.title}</p>
                <dl className="ledger-status">
                  <div>
                    <dt>Status</dt>
                    <dd>
                      <StatusBadge value={source.status} tone={tone(source.status)} />
                    </dd>
                  </div>
                  <div>
                    <dt>Jurisdiction</dt>
                    <dd>{source.jurisdiction}</dd>
                  </div>
                  <div>
                    <dt>Provenance</dt>
                    <dd>
                      {source.source_url ? (
                        <span className="muted">source URL recorded (metadata only)</span>
                      ) : (
                        <span className="muted">No source URL recorded</span>
                      )}
                    </dd>
                  </div>
                </dl>
                <p className="ledger-actions">
                  <Link to={sourcePath(source.id)} className="link-button">
                    Open source
                  </Link>
                </p>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}
