import { useCallback, useEffect, useState } from "react";
import { userFacingErrorMessage } from "../../api/client";
import type { AuthCredentials } from "../../api/client";
import {
  listRegulatoryAuthorities,
  REGULATORY_SOURCE_STATUSES,
  type RegulatoryAuthority,
  type RegulatorySourceCreateRequest,
} from "../../api/regulatory";
import { LoadingState } from "../../components/StatusBits";

export function RegisterSourceForm({
  auth,
  onRegister,
}: {
  auth: AuthCredentials;
  onRegister: (payload: RegulatorySourceCreateRequest) => Promise<boolean>;
}) {
  type SourceStatus = (typeof REGULATORY_SOURCE_STATUSES)[number];

  const [authorityId, setAuthorityId] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [title, setTitle] = useState("");
  const [version, setVersion] = useState("");
  const [status, setStatus] = useState<SourceStatus>("draft");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [publicationDate, setPublicationDate] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [authorities, setAuthorities] = useState<RegulatoryAuthority[] | null>(
    null,
  );
  const [authorityLoading, setAuthorityLoading] = useState(false);
  const [authorityError, setAuthorityError] = useState<unknown>(null);
  const [authorityFilter, setAuthorityFilter] = useState("");

  const loadAuthorities = useCallback(async () => {
    setAuthorityLoading(true);
    setAuthorityError(null);
    try {
      const authorities = await listRegulatoryAuthorities(
        auth as AuthCredentials,
      );
      setAuthorities(authorities);
    } catch (caught) {
      setAuthorityError(caught);
    } finally {
      setAuthorityLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void loadAuthorities();
  }, [loadAuthorities]);

  const filteredAuthorities = authorities?.filter((a) =>
    a.name.toLowerCase().includes(authorityFilter.toLowerCase()),
  ) ?? [];

  const selectedAuthority = authorities?.find((a) => a.id === authorityId);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    if (!jurisdiction.trim()) {
      setError("Jurisdiction is required.");
      return;
    }
    if (!authorityId.trim()) {
      setError("An authority must be selected.");
      return;
    }
    if (!authorities || authorities.length === 0) {
      setError("Authority list is unavailable. Please refresh and try again.");
      return;
    }
    const matchedAuthority = authorities.find((a) => a.id === authorityId.trim());
    if (!matchedAuthority) {
      setError("Selected authority is invalid or stale. Please select from the current list.");
      return;
    }

    setPending(true);
    try {
      const ok = await onRegister({
        authority_id: authorityId.trim(),
        jurisdiction: jurisdiction.trim(),
        title: title.trim(),
        version: version.trim() || undefined,
        status,
        effective_date: effectiveDate || undefined,
        publication_date: publicationDate || undefined,
        source_url: sourceUrl.trim() || undefined,
      });
      if (!ok) {
        return;
      }
      setAuthorityId("");
      setJurisdiction("");
      setTitle("");
      setVersion("");
      setStatus("draft");
      setEffectiveDate("");
      setPublicationDate("");
      setSourceUrl("");
      setAuthorityFilter("");
    } catch (caught) {
      setError(userFacingErrorMessage(caught));
    } finally {
      setPending(false);
    }
  };

  return (
    <section aria-label="Register regulatory source">
      <h2>Register regulatory source</h2>
      <form className="form" onSubmit={submit}>
        <fieldset>
          <div className="form-row">
            <label htmlFor="register-source-authority-id">
              Regulatory authority (required)
            </label>
            {authorityLoading ? (
              <LoadingState text="Loading authorities…" />
            ) : authorityError ? (
              <p role="alert" className="ledger-reason">
                {userFacingErrorMessage(authorityError)}
              </p>
            ) : authorities === null ? (
              <p className="muted">Loading authorities…</p>
            ) : authorities.length === 0 ? (
              <p className="muted">
                No regulatory authorities are registered. An authority must be
                created through the administrative process before a source can
                be registered.
              </p>
            ) : (
              <>
                <div className="form-row">
                  <label htmlFor="register-authority-filter">
                    Search authority
                  </label>
                  <input
                    id="register-authority-filter"
                    type="text"
                    value={authorityFilter}
                    onChange={(event) =>
                      setAuthorityFilter(event.target.value)
                    }
                    placeholder="Search by authority name"
                  />
                </div>
                <div className="form-row">
                  <label htmlFor="register-source-authority-id">
                    Selected authority
                  </label>
                  <select
                    id="register-source-authority-id"
                    value={authorityId}
                    onChange={(event) => setAuthorityId(event.target.value)}
                    disabled={filteredAuthorities.length === 0}
                  >
                    <option value="">Select an authority…</option>
                    {filteredAuthorities.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                        {a.jurisdiction ? ` (${a.jurisdiction})` : ""}
                      </option>
                    ))}
                  </select>
                  {selectedAuthority && (
                    <p className="hint">
                      Selected: {selectedAuthority.name}{" "}
                      {selectedAuthority.jurisdiction ? `(${selectedAuthority.jurisdiction})` : ""}
                    </p>
                  )}
                </div>
              </>
            )}
            </div>
            <div className="form-row">
              <label htmlFor="register-source-jurisdiction">
                Jurisdiction (required)
              </label>
              <input
                id="register-source-jurisdiction"
                type="text"
                value={jurisdiction}
                onChange={(event) => setJurisdiction(event.target.value)}
                placeholder="e.g. NG"
              />
            </div>
            <div className="form-row">
              <label htmlFor="register-source-title">Title (required)</label>
              <input
                id="register-source-title"
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Regulation (EU) 2019/1793"
              />
            </div>
            <div className="form-row">
              <label htmlFor="register-source-version">Version</label>
              <input
                id="register-source-version"
                type="text"
                value={version}
                maxLength={100}
                onChange={(event) => setVersion(event.target.value)}
                placeholder="e.g. 1.0"
              />
              <p className="hint">Maximum 100 characters.</p>
            </div>
            <div className="form-row">
              <label htmlFor="register-source-status">Status</label>
              <select
                id="register-source-status"
                value={status}
                onChange={(event) =>
                  setStatus(event.target.value as SourceStatus)
                }
              >
                {REGULATORY_SOURCE_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <label htmlFor="register-source-effective-date">Effective date</label>
              <input
                id="register-source-effective-date"
                type="date"
                value={effectiveDate}
                onChange={(event) => setEffectiveDate(event.target.value)}
              />
            </div>

            <div className="form-row">
              <label htmlFor="register-source-publication-date">
                Publication date
              </label>
              <input
                id="register-source-publication-date"
disabled={pending || !authorityId}
                type="date"
                value={publicationDate}
                onChange={(event) => setPublicationDate(event.target.value)}
              />
            </div>
            <div className="form-row">
              <label htmlFor="register-source-source-url">Source URL</label>
              <input
                id="register-source-source-url"
                type="url"
                value={sourceUrl}
                maxLength={2048}
                onChange={(event) => setSourceUrl(event.target.value)}
                placeholder="e.g. https://eur-lex.example/regulation"
              />
              <p className="hint">
                Stored as metadata only; never fetched by the server.
              </p>
            </div>
          </fieldset>
          {error ? <p role="alert" className="ledger-reason">{error}</p> : null}
          <button type="submit" className="primary-button" disabled={pending || !authorityId}>
            {pending ? "Registering…" : "Register source"}
          </button>
        </form>
      </section>
    );
}
