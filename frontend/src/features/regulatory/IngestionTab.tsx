import { useCallback, useState } from "react";
import { userFacingErrorMessage } from "../../api/client";
import { retryRegulatoryIngestionJob } from "../../api/regulatory";
import { StatusBadge } from "../../components/StatusBits";
import { useSourceContext } from "./SourceContext";
import { createdAt, tone } from "./regulatoryUi";

/** Every recorded ingestion attempt, with the bounded retry for failures. */
export function IngestionTab() {
  const { auth, jobs, reload } = useSourceContext();
  const [retryPendingJobId, setRetryPendingJobId] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrySuccess, setRetrySuccess] = useState<string | null>(null);

  const handleRetryJob = useCallback(
    async (jobId: string) => {
      setRetryPendingJobId(jobId);
      setRetryError(null);
      setRetrySuccess(null);
      try {
        const retried = await retryRegulatoryIngestionJob(auth, jobId);
        // The retry is a new attempt row; the ledger reflects it only
        // after the server-confirmed refresh converges.
        setRetrySuccess(
          `Retry recorded: a new ingestion attempt (${retried.attempt_number}) was created for the failed job. The job remains pending until the worker processes it.`,
        );
        await reload();
      } catch (caught) {
        setRetryError(userFacingErrorMessage(caught));
      } finally {
        setRetryPendingJobId(null);
      }
    },
    [auth, reload],
  );

  return (
    <div>
      <h2>Ingestion jobs</h2>
      {jobs.length === 0 ? (
        <p className="muted">No ingestion jobs for this source.</p>
      ) : (
        <ol className="ledger">
          {jobs.map((job) => (
            <li key={job.id} className="ledger-row">
              {job.artifact_id === null ? (
                <p className="ledger-title">
                  Registration record — no document attached yet, so there is
                  nothing to ingest.
                </p>
              ) : null}
              <dl className="ledger-status">
                <div>
                  <dt>Status</dt>
                  <dd>
                    <StatusBadge value={job.status} tone={tone(job.status)} />
                  </dd>
                </div>
                <div>
                  <dt>Attempt</dt>
                  <dd>{job.attempt_number}</dd>
                </div>
                <div>
                  <dt>Started</dt>
                  <dd>{createdAt(job.started_at)}</dd>
                </div>
                <div>
                  <dt>Completed</dt>
                  <dd>{createdAt(job.completed_at)}</dd>
                </div>
              </dl>
              {job.error_details ? (
                <p className="ledger-reason">Failure details: {job.error_details}</p>
              ) : null}
              {job.status === "failed" ? (
                <p className="ledger-actions">
                  <button
                    type="button"
                    className="link-button"
                    disabled={retryPendingJobId !== null}
                    onClick={() => void handleRetryJob(job.id)}
                  >
                    {retryPendingJobId === job.id ? "Recording retry…" : "Retry failed job"}
                  </button>
                </p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
      {retryError ? <p role="alert" className="ledger-reason">{retryError}</p> : null}
      {retrySuccess ? <p className="success-message" role="status">{retrySuccess}</p> : null}
    </div>
  );
}
