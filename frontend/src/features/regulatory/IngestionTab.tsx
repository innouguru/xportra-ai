import { useCallback, useRef, useState, useEffect } from "react";
import { userFacingErrorMessage } from "../../api/client";
import { retryRegulatoryIngestionJob } from "../../api/regulatory";
import { StatusBadge } from "../../components/StatusBits";
import { useSourceContext } from "./SourceContext";
import { createdAt, tone } from "./regulatoryUi";
import { listSourceJobs } from "../../api/regulatory";

/** Every recorded ingestion attempt, with the bounded retry for failures. */
export function IngestionTab() {
  const { auth, jobs, reload, source } = useSourceContext();
  const [retryPendingJobId, setRetryPendingJobId] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrySuccess, setRetrySuccess] = useState<string | null>(null);

  const [isPolling, setIsPolling] = useState(false);
  const [lastPollError, setLastPollError] = useState<string | null>(null);
  const pollAbortCtrl = useRef<AbortController | null>(null);
  const pollTimeoutRef = useRef<number | null>(null);

  // -------------------------------------------------------------------------
  // Start / stop polling based on job states
  // -------------------------------------------------------------------------

  useEffect(() => {
    pollAbortCtrl.current = new AbortController();

    const nonTerminalJobs = jobs.filter(
      (job) =>
        job.artifact_id !== null && !["completed", "failed"].includes(job.status),
    );

    if (nonTerminalJobs.length > 0) {
      setIsPolling(true);
      startPolling();
    } else {
      setIsPolling(false);
      stopPolling();
    }

    return () => {
      stopPolling();
      pollAbortCtrl.current?.abort();
    };
  }, [jobs, source]);

  const startPolling = () => {
    if (pollTimeoutRef.current !== null) return; // prevent overlapping
    poll();

    pollTimeoutRef.current = window.setInterval(() => {
      poll();
    }, 3000);
  };

  const stopPolling = () => {
    if (pollTimeoutRef.current !== null) {
      clearInterval(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      stopPolling();
      pollAbortCtrl.current?.abort();
    };
  }, []);

  // -------------------------------------------------------------------------
  // Polling implementation
  // -------------------------------------------------------------------------

  const poll = useCallback(async () => {
    if (pollAbortCtrl.current && pollAbortCtrl.current.signal?.aborted) {
      return;
    }
    try {
      const result = await listSourceJobs(auth, source.id);
      // Refresh the job list via the context reload mechanism.
      if (typeof reload === "function") {
        reload();
      }
      setLastPollError(null);
    } catch (err) {
      // Display the last known status when polling temporarily fails;
      // do not automatically mark a job failed based solely on frontend time.
      setLastPollError(userFacingErrorMessage(err));
    }
  }, [auth, source, reload]);

  // -------------------------------------------------------------------------
  // Resume polling when a new job is submitted (jobs list changes)
  // -------------------------------------------------------------------------

  useEffect(() => {
    setLastPollError(null);

    const nonTerminalJobs = jobs.filter(
      (job) =>
        job.artifact_id !== null && !["completed", "failed"].includes(job.status),
    );

    if (nonTerminalJobs.length > 0) {
      setIsPolling(true);
      startPolling();
    } else {
      setIsPolling(false);
      stopPolling();
    }
  }, [jobs, source, reload]);

  // -------------------------------------------------------------------------
  // Retry handling (unchanged from original)
  // -------------------------------------------------------------------------

  const handleRetryJob = useCallback(
    async (jobId: string) => {
      setRetryPendingJobId(jobId);
      setRetryError(null);
      setRetrySuccess(null);
      try {
        const retried = await retryRegulatoryIngestionJob(auth, jobId);
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
                {job.artifact_id !== null && (
                  <div>
                    <dt>Processing stage</dt>
                    <dd>
                      {job.current_stage
                        ? `${job.current_stage}${
                              job.stage_updated_at
                                ? ` (last updated ${createdAt(job.stage_updated_at)})`
                                : ""
                          }`
                            : "—"}
                      </dd>
                    </div>
                  )}
                  {job.artifact_id !== null && (
                    <div>
                      <dt>Attempt</dt>
                      <dd>{job.attempt_number}</dd>
                    </div>
                  )}
                  {job.artifact_id !== null && (
                    <div>
                      <dt>Started</dt>
                      <dd>{createdAt(job.started_at)}</dd>
                    </div>
                  )}
                  {job.artifact_id !== null && (
                    <div>
                      <dt>Duration</dt>
                      <dd>
                        {job.started_at
                          ? `${new Date().getTime() - new Date(job.started_at).getTime()} ms elapsed`
                          : "—"}
                      </dd>
                    </div>
                  )}
                  {job.artifact_id !== null && (
                    <div>
                      <dt>Last updated</dt>
                      <dd>{createdAt(job.stage_updated_at)}</dd>
                    </div>
                  )}
                  {job.artifact_id !== null && (
                    <div>
                      <dt>Completed</dt>
                      <dd>{createdAt(job.completed_at)}</dd>
                    </div>
                  )}
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
                </dl>
              </li>
            ))}
        </ol>
      )}
      {lastPollError ? (
        <p role="alert" className="ledger-reason">
          Last update: {lastPollError}
        </p>
      ) : null}
      {retryError ? <p role="alert" className="ledger-reason">{retryError}</p> : null}
      {retrySuccess ? <p className="success-message" role="status">{retrySuccess}</p> : null}
    </div>
  );
}