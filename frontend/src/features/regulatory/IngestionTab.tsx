import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  userFacingErrorMessage,
} from "../../api/client";
import {
  getRegulatoryIngestionJobExtractionHistory,
  retryRegulatoryIngestionJob,
  type RegulatoryExtractionRunCandidate,
  type RegulatoryIngestionJob,
  type RegulatoryJobExtractionHistory,
  type RegulatoryJobExtractionRun,
} from "../../api/regulatory";
import { Identifier, StatusBadge } from "../../components/StatusBits";
import { useSourceContext } from "./SourceContext";
import { candidatePath, tone } from "./regulatoryUi";

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  retrieving_artifact: "Retrieving artifact",
  validating_document: "Validating document",
  extracting_text: "Extracting document text",
  normalizing_content: "Normalizing content",
  extracting_requirements: "Extracting requirements",
  saving_candidates: "Saving candidates",
  completed: "Completed",
  failed: "Failed",
};

function stageLabel(stage: string | null | undefined): string {
  return stage ? STAGE_LABELS[stage] ?? stage : "Not recorded";
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function textValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function referenceText(location: Record<string, unknown>, key: string): string {
  const referenceStatus = recordValue(location.reference_status);
  const status = textValue(referenceStatus?.[key]);
  const value = location[`${key}_reference`];
  if (value !== null && value !== undefined && String(value).trim()) {
    return String(value);
  }
  if (status === "not_returned_by_model") return "Not returned by model";
  if (status === "unavailable_in_supplied_context") {
    return "Unavailable in supplied source context";
  }
  if (status === "verified") return "Verified; no value recorded";
  return "Not recorded";
}

function jobStateDescription(job: RegulatoryIngestionJob): string {
  if (job.artifact_id === null) {
    return "Registration placeholder; waiting for an artifact upload.";
  }
  switch (job.status) {
    case "pending":
      return "Waiting for the ingestion worker.";
    case "claimed":
      return "Claimed by the worker; processing stage will update as work proceeds.";
    case "processing":
      return "The worker is processing this ingestion job.";
    case "retryable":
      return "A retryable failure is recorded; the worker can reclaim this job.";
    case "completed":
      return "Ingestion completed successfully.";
    case "failed":
      return "Ingestion failed. Review the recorded diagnostic.";
    default:
      return `Backend status: ${job.status}`;
  }
}

function shouldOfferRetry(
  job: RegulatoryIngestionJob,
  jobs: RegulatoryIngestionJob[],
  alreadySubmitted: boolean,
): boolean {
  if (
    job.status !== "failed" ||
    job.artifact_id === null ||
    alreadySubmitted
  ) {
    return false;
  }
  return !jobs.some(
    (other) =>
      other.artifact_id === job.artifact_id &&
      other.attempt_number > job.attempt_number,
  );
}

function EvidenceSnapshot({
  item,
  sourceId,
}: {
  item: RegulatoryExtractionRunCandidate;
  sourceId: string;
}) {
  const snapshot = item.evidence_snapshot;
  const location = recordValue(snapshot.source_location) ?? {};
  const requirementText =
    textValue(snapshot.requirement_text) ?? textValue(snapshot.title);
  const quote = textValue(location.supporting_quote);

  return (
    <article className="reg-ingestion-evidence">
      <h5>
        Candidate snapshot {item.candidate_index + 1}
        {item.is_origin ? " · origin" : ""}
      </h5>
      {requirementText ? <p>{requirementText}</p> : null}
      <dl className="reg-ingestion-meta">
        <div>
          <dt>Supporting quotation</dt>
          <dd>{quote ? <blockquote>{quote}</blockquote> : "Not recorded"}</dd>
        </div>
        <div>
          <dt>Page reference</dt>
          <dd>{referenceText(location, "page")}</dd>
        </div>
        <div>
          <dt>Section or article</dt>
          <dd>{referenceText(location, "section")}</dd>
        </div>
        <div>
          <dt>Candidate persistence</dt>
          <dd>{item.resolution_status}</dd>
        </div>
      </dl>
      {item.candidate_id ? (
        <Link
          to={candidatePath(sourceId, item.candidate_id)}
          className="link-button"
        >
          Inspect candidate and full provenance
        </Link>
      ) : (
        <p className="muted">
          No persisted candidate is linked to this snapshot.
        </p>
      )}
    </article>
  );
}

function ExtractionRun({ run, sourceId }: {
  run: RegulatoryJobExtractionRun;
  sourceId: string;
}) {
  return (
    <section className="reg-ingestion-run">
      <header className="reg-ingestion-run__header">
        <h4>Extraction run</h4>
        <StatusBadge value={run.outcome} tone={tone(run.outcome)} />
      </header>
      <p className="muted">
        {run.candidate_count} candidate snapshot
        {run.candidate_count === 1 ? "" : "s"} recorded;{" "}
        {run.persisted_candidate_count} linked to persisted candidates.
      </p>
      <dl className="reg-ingestion-meta">
        <div>
          <dt>Run ID</dt>
          <dd><Identifier value={run.extraction_run_id} short={36} /></dd>
        </div>
        <div>
          <dt>Artifact version</dt>
          <dd>{run.artifact_source_version ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt>Artifact hash</dt>
          <dd>{run.artifact_content_hash}</dd>
        </div>
        <div>
          <dt>Extraction method / version</dt>
          <dd>{run.extraction_method} / {run.extraction_version}</dd>
        </div>
        <div>
          <dt>Parser version</dt>
          <dd>{run.parser_version}</dd>
        </div>
        <div>
          <dt>Prompt version</dt>
          <dd>{run.prompt_version ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt>Configured model</dt>
          <dd>{run.configured_model_identifier ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt>Observed providers and models</dt>
          <dd>
            {[...run.provider_names, ...run.model_identifiers].join(", ") ||
              "Not recorded"}
          </dd>
        </div>
        <div>
          <dt>Started</dt>
          <dd>{formatTimestamp(run.started_at)}</dd>
        </div>
        <div>
          <dt>Completed</dt>
          <dd>{formatTimestamp(run.completed_at)}</dd>
        </div>
        <div>
          <dt>Rejected candidates</dt>
          <dd>{run.rejected_candidate_count}</dd>
        </div>
      </dl>
      {run.failed_chunks.length > 0 ? (
        <div className="ledger-reason">
          <h5>Recorded extraction warnings</h5>
          <ul>
            {run.failed_chunks.map((failure, index) => {
              const reason = textValue(failure.reason);
              const errorType = textValue(failure.error_type);
              return (
                <li key={`${reason ?? "warning"}-${index}`}>
                  {[reason, errorType].filter(Boolean).join(" · ") ||
                    "A failed extraction chunk was recorded."}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {run.candidates.length > 0 ? (
        <div>
          <h5>Candidate evidence snapshots</h5>
          <div className="reg-ingestion-evidence-list">
            {run.candidates.map((item) => (
              <EvidenceSnapshot
                key={`${run.extraction_run_id}-${item.candidate_index}`}
                item={item}
                sourceId={sourceId}
              />
            ))}
          </div>
        </div>
      ) : (
        <p className="muted">
          This persisted run contains no candidate snapshots.
        </p>
      )}
    </section>
  );
}

/** Every recorded ingestion attempt, with the bounded retry for failures. */
export function IngestionTab() {
  const {
    auth,
    artifacts,
    candidates,
    jobs,
    loading,
    refreshError,
    reload,
    source,
    sourceId,
  } = useSourceContext();
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [history, setHistory] = useState<RegulatoryJobExtractionHistory | null>(
    null,
  );
  const [historyForJobId, setHistoryForJobId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyReloadNonce, setHistoryReloadNonce] = useState(0);
  const [retryPendingJobId, setRetryPendingJobId] = useState<string | null>(null);
  const [retrySubmittedJobIds, setRetrySubmittedJobIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrySuccess, setRetrySuccess] = useState<string | null>(null);
  const historyRequestId = useRef(0);

  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null;

  useEffect(() => {
    if (!selectedJob) {
      setHistory(null);
      setHistoryForJobId(null);
      setHistoryError(null);
      setHistoryLoading(false);
      return;
    }

    const requestId = ++historyRequestId.current;
    let active = true;
    setHistory(null);
    setHistoryForJobId(null);
    setHistoryError(null);
    setHistoryLoading(true);
    void getRegulatoryIngestionJobExtractionHistory(
      auth,
      selectedJob.id,
    )
      .then((response) => {
        if (!active || requestId !== historyRequestId.current) return;
        setHistory(response);
        setHistoryForJobId(selectedJob.id);
      })
      .catch((caught: unknown) => {
        if (!active || requestId !== historyRequestId.current) return;
        setHistoryError(userFacingErrorMessage(caught));
      })
      .finally(() => {
        if (active && requestId === historyRequestId.current) {
          setHistoryLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [auth, selectedJob?.id, selectedJob?.updated_at, historyReloadNonce]);

  const handleRetryJob = useCallback(
    async (jobId: string) => {
      setRetryPendingJobId(jobId);
      setRetryError(null);
      setRetrySuccess(null);
      try {
        const retried = await retryRegulatoryIngestionJob(auth, jobId);
        setRetrySubmittedJobIds((current) => new Set(current).add(jobId));
        setRetrySuccess(
          `Retry recorded as attempt ${retried.attempt_number}; the new job is awaiting the worker.`,
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

  const selectedCandidates = selectedJob
    ? candidates.filter((candidate) => candidate.ingestion_job_id === selectedJob.id)
    : [];
  const selectedHistory =
    historyForJobId === selectedJob?.id ? history : null;

  return (
    <div>
      <div className="reg-ingestion-heading">
        <div>
          <h2>Ingestion jobs</h2>
          <p className="muted">
            Status and stage are shown as recorded by the ingestion service.
            Progress is stage-based; no completion percentage is inferred.
          </p>
        </div>
        <button
          type="button"
          className="secondary-button"
          disabled={loading}
          onClick={() => void reload()}
        >
          {loading ? "Refreshing…" : "Refresh jobs"}
        </button>
      </div>

      {refreshError ? (
        <p role="status" className="reg-notice">
          Refresh failed. The job data below is the last successfully loaded
          snapshot and may be stale. Use “Refresh jobs” or the page retry action
          to check again.
        </p>
      ) : null}

      {jobs.length === 0 ? (
        <p className="muted">No ingestion jobs for this source.</p>
      ) : (
        <ol className="ledger">
          {jobs.map((job) => {
            const artifact =
              job.artifact_id === null
                ? null
                : artifacts.find((item) => item.id === job.artifact_id) ?? null;
            const selected = selectedJobId === job.id;
            const retryAvailable = shouldOfferRetry(
              job,
              jobs,
              retrySubmittedJobIds.has(job.id),
            );
            return (
              <li key={job.id} className="ledger-row">
                <div className="reg-ingestion-job-head">
                  <div>
                    <h3 className="ledger-title">
                      {job.artifact_id === null
                        ? "Registration placeholder"
                        : `Artifact ingestion · attempt ${job.attempt_number}`}
                    </h3>
                    <p className="muted">{jobStateDescription(job)}</p>
                  </div>
                  <StatusBadge value={job.status} tone={tone(job.status)} />
                </div>

                <dl className="reg-ingestion-meta">
                  <div>
                    <dt>Source</dt>
                    <dd>{source.title} · <Identifier value={source.id} short={12} /></dd>
                  </div>
                  <div>
                    <dt>Artifact</dt>
                    <dd>
                      {job.artifact_id ? (
                        <>
                          <Identifier value={job.artifact_id} short={12} />
                          {artifact?.source_version
                            ? ` · version ${artifact.source_version}`
                            : ""}
                        </>
                      ) : (
                        "Not uploaded"
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Submitted</dt>
                    <dd>{formatTimestamp(job.created_at)}</dd>
                  </div>
                  <div>
                    <dt>Job last updated</dt>
                    <dd>{formatTimestamp(job.updated_at)}</dd>
                  </div>
                  {job.artifact_id !== null ? (
                    <>
                      <div>
                        <dt>Current processing stage</dt>
                        <dd>{stageLabel(job.current_stage)}</dd>
                      </div>
                      <div>
                        <dt>Stage last updated</dt>
                        <dd>{formatTimestamp(job.stage_updated_at)}</dd>
                      </div>
                      <div>
                        <dt>Worker started</dt>
                        <dd>{formatTimestamp(job.started_at)}</dd>
                      </div>
                      <div>
                        <dt>Completed</dt>
                        <dd>{formatTimestamp(job.completed_at)}</dd>
                      </div>
                    </>
                  ) : null}
                </dl>

                {job.error_details ? (
                  <div className="ledger-reason" role="note">
                    <strong>
                      Recorded failure diagnostic
                      {job.current_stage
                        ? ` · ${stageLabel(job.current_stage)}`
                        : ""}
                    </strong>
                    <p>{job.error_details}</p>
                  </div>
                ) : null}

                <div className="ledger-actions">
                  <button
                    type="button"
                    className="link-button"
                    aria-expanded={selected}
                    onClick={() =>
                      setSelectedJobId((current) =>
                        current === job.id ? null : job.id,
                      )
                    }
                  >
                    {selected ? "Hide job details" : "Inspect job"}
                  </button>
                  {retryAvailable ? (
                    <button
                      type="button"
                      className="link-button"
                      disabled={retryPendingJobId !== null}
                      onClick={() => void handleRetryJob(job.id)}
                    >
                      {retryPendingJobId === job.id
                        ? "Recording retry…"
                        : "Retry failed job"}
                    </button>
                  ) : null}
                  {retrySubmittedJobIds.has(job.id) ? (
                    <span className="muted">
                      A retry was recorded for this attempt.
                    </span>
                  ) : null}
                </div>

                {selected ? (
                  <section
                    id={`job-details-${job.id}`}
                    className="reg-ingestion-details"
                    aria-label={`Details for job ${job.id}`}
                  >
                    <h4>Job details</h4>
                    <dl className="reg-ingestion-meta">
                      <div>
                        <dt>Job ID</dt>
                        <dd><Identifier value={job.id} short={36} /></dd>
                      </div>
                      <div>
                        <dt>Artifact content hash</dt>
                        <dd>{artifact?.content_hash ?? "Not available"}</dd>
                      </div>
                      <div>
                        <dt>Artifact content type</dt>
                        <dd>{artifact?.content_type ?? "Not available"}</dd>
                      </div>
                      <div>
                        <dt>Parser version</dt>
                        <dd>{job.parser_version || "Not recorded"}</dd>
                      </div>
                    </dl>

                    <h4>Requirement extraction runs</h4>
                    {historyLoading ? (
                      <p role="status">Loading persisted extraction history…</p>
                    ) : null}
                    {historyError ? (
                      <div className="ledger-reason" role="alert">
                        <p>{historyError}</p>
                        <button
                          type="button"
                          className="link-button"
                          onClick={() =>
                            setHistoryReloadNonce((current) => current + 1)
                          }
                        >
                          Retry loading extraction history
                        </button>
                      </div>
                    ) : null}
                    {!historyLoading && !historyError && selectedHistory ? (
                      selectedHistory.items.length > 0 ? (
                        <div className="reg-ingestion-runs">
                          {selectedHistory.items.map((run) => (
                            <ExtractionRun
                              key={run.extraction_run_id}
                              run={run}
                              sourceId={sourceId}
                            />
                          ))}
                        </div>
                      ) : (
                        <p className="muted">
                          No requirement-extraction run is recorded for this
                          job. The ingestion status alone does not establish an
                          extraction outcome.
                        </p>
                      )
                    ) : null}

                    <h4>Persisted candidates linked to this job</h4>
                    {selectedCandidates.length > 0 ? (
                      <ul className="reg-ingestion-candidate-links">
                        {selectedCandidates.map((candidate) => (
                          <li key={candidate.id}>
                            <Link to={candidatePath(sourceId, candidate.id)}>
                              {candidate.requirement_text}
                            </Link>
                            {" · "}
                            <StatusBadge
                              value={candidate.extraction_outcome}
                              tone={tone(candidate.extraction_outcome)}
                            />
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">
                        No persisted candidates are currently linked to this
                        job.
                      </p>
                    )}
                  </section>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}

      {retryError ? (
        <p role="alert" className="ledger-reason">{retryError}</p>
      ) : null}
      {retrySuccess ? (
        <p className="success-message" role="status">{retrySuccess}</p>
      ) : null}
    </div>
  );
}
