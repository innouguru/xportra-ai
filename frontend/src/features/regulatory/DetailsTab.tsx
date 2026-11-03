import { useCallback, useState } from "react";
import { userFacingErrorMessage } from "../../api/client";
import { withdrawRegulatorySource } from "../../api/regulatory";
import { Field, Identifier, StatusBadge } from "../../components/StatusBits";
import { useSourceContext } from "./SourceContext";
import { tone } from "./regulatoryUi";

/** Recorded provenance, plus the (deliberately last) withdrawal action. */
export function DetailsTab() {
  const { auth, sourceId, source, loading, reload } = useSourceContext();
  const [withdrawRationale, setWithdrawRationale] = useState("");
  const [withdrawPending, setWithdrawPending] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [withdrawSuccess, setWithdrawSuccess] = useState<string | null>(null);

  const handleWithdrawSource = useCallback(async () => {
    if (!withdrawRationale.trim()) {
      setWithdrawError("A rationale is required to withdraw the source.");
      return;
    }
    setWithdrawPending(true);
    setWithdrawError(null);
    setWithdrawSuccess(null);
    try {
      const result = await withdrawRegulatorySource(auth, sourceId, {
        rationale: withdrawRationale.trim(),
      });
      setWithdrawSuccess(
        `Source withdrawn as recorded. Status: ${result.status}; ${result.governance_flags_raised} pending withdrawal governance flag(s) raised.`,
      );
      setWithdrawRationale("");
      await reload();
    } catch (caught) {
      setWithdrawError(userFacingErrorMessage(caught));
    } finally {
      setWithdrawPending(false);
    }
  }, [auth, sourceId, withdrawRationale, reload]);

  return (
    <div>
      <h2>Source details</h2>
      <dl className="results-block">
        <Field label="Source ID">
          <Identifier value={source.id} />
        </Field>
        <Field label="Status">
          <StatusBadge value={source.status} tone={tone(source.status)} />
        </Field>
        <Field label="Authority">
          <Identifier value={source.authority_id} />
        </Field>
        <Field label="Jurisdiction">{source.jurisdiction}</Field>
        <Field label="Version">{source.version ?? "—"}</Field>
        <Field label="Effective date">{source.effective_date ?? "—"}</Field>
        <Field label="Publication date">{source.publication_date ?? "—"}</Field>
        <Field label="Retrieval timestamp">
          {source.retrieval_timestamp ?? "Unknown — not recorded"}
        </Field>
        <Field label="Source URL (metadata only, never fetched)">
          {source.source_url ?? "—"}
        </Field>
        <Field label="Supersedes (as recorded)">
          {source.supersedes_source_id ? (
            <Identifier value={source.supersedes_source_id} short={36} />
          ) : (
            "—"
          )}
        </Field>
        <Field label="Superseded by (as recorded)">
          {source.superseded_by_source_id ? (
            <Identifier value={source.superseded_by_source_id} short={36} />
          ) : (
            "—"
          )}
        </Field>
      </dl>

      <section className="reg-danger" aria-label="Withdraw source">
        <h3>Withdraw source</h3>
        {source.status === "withdrawn" || source.status === "archived" ? (
          <p className="muted">
            This source is already {source.status}. The backend refuses a
            further withdrawal; nothing is offered here.
          </p>
        ) : (
          <>
            <p className="muted">
              Withdrawing the source sets its status to <code>withdrawn</code>{" "}
              and raises a pending withdrawal governance flag for every linked
              requirement; nothing linked to the source can be published or
              re-verified while the flags remain pending. The rationale is
              mandatory and recorded.
            </p>
            <form
              className="form"
              onSubmit={(event) => {
                event.preventDefault();
                void handleWithdrawSource();
              }}
            >
              <fieldset>
                <div className="form-row">
                  <label htmlFor="withdraw-source-rationale">
                    Withdrawal rationale (required)
                  </label>
                  <textarea
                    id="withdraw-source-rationale"
                    rows={3}
                    value={withdrawRationale}
                    onChange={(event) => setWithdrawRationale(event.target.value)}
                    placeholder="Why this source is being withdrawn"
                  />
                </div>
              </fieldset>
              {withdrawError ? (
                <p role="alert" className="ledger-reason">{withdrawError}</p>
              ) : null}
              <div className="form-row">
                <button
                  type="submit"
                  className="primary-button"
                  disabled={withdrawPending || loading || !withdrawRationale.trim()}
                >
                  {withdrawPending ? "Withdrawing…" : "Withdraw source"}
                </button>
              </div>
            </form>
            {withdrawSuccess ? (
              <p className="success-message" role="status">{withdrawSuccess}</p>
            ) : null}
          </>
        )}
      </section>
    </div>
  );
}
