import { useCallback, useEffect, useRef, useState } from "react";
import { userFacingErrorMessage } from "../../api/client";
import type { AuthCredentials } from "../../api/client";
import {
  listRegulatoryAuthorities,
  registerRegulatorySource,
  type RegulatoryAuthority,
  type RegulatorySourceCreateRequest,
  REGULATORY_SOURCE_STATUSES,
  getRegulatoryCandidate,
  getCandidateStageA,
  getCandidateStageB,
  getRegulatorySource,
  listRequirementGovernanceFlags,
  listSourceArtifacts,
  listSourceCandidates,
  listSourceGovernanceFlags as listFlagsForSource,
  listSourceJobs,
  listRegulatorySources,
  listStageAHistory,
  listStageBHistory,
  listWordingCorrections,
  retryRegulatoryIngestionJob,
  submitStageADecision,
  submitStageBDecision,
  uploadRegulatoryArtifact,
  withdrawRegulatorySource,
  type RegulatoryArtifact,
  type RegulatoryCandidate,
  type RegulatoryGovernanceFlag,
  type RegulatoryIngestionJob,
  type RegulatorySource,
  type RegulatoryStageAHistoryEntry,
  type RegulatoryStageAState,
  type RegulatoryStageBHistoryEntry,
  type RegulatoryStageBState,
  type RegulatoryWordingCorrection,
} from "../../api/regulatory";
import { useAuth } from "../../app/AuthContext";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
} from "../../components/StatusBits";
import {
  REGULATORY_ARTIFACT_ACCEPT,
  SUPPORTED_ARTIFACT_TEXT,
  describeUnsupportedArtifactFile,
  resolveArtifactContentType,
} from "../../lib/regulatoryUpload";

/**
 * Regulatory administration surface (authorized staff only).
 *
 * The server is the authority for every privileged action: each
 * mutation requires an active global staff grant (``GRANT_MANAGE``,
 * ``STAGE_A_VERIFY`` or ``STAGE_B_APPROVE``) enforced server-side;
 * this page only reflects the backend's decisions and failures.
 * Authorization denials are surfaced as errors — never mocked as
 * success. All states, supersession links, extraction outcomes, and
 * governance flags are displayed verbatim; nothing is inferred.
 * No operation here publishes a requirement or marks it
 * exporter-applicable.
 */

function createdAt(value: string | null | undefined): string {
  return value ?? "—";
}

function tone(value: string): "info" | "muted" | "attention" | "neutral" {
  if (value === "completed" || value === "verified" || value === "approved") {
    return "info";
  }
  if (
    value === "failed" ||
    value === "rejected" ||
    value === "pending_review" ||
    value === "clarification_required"
  ) {
    return "attention";
  }
  return "muted";
}

export function RegulationAdminPage() {
  const auth = useAuth();
  const [sources, setSources] = useState<RegulatorySource[] | null>(null);
  const [listError, setListError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [registerPending, setRegisterPending] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [registerSuccess, setRegisterSuccess] = useState<string | null>(null);

  const loadSources = useCallback(async () => {
    setLoading(true);
    setListError(null);
    try {
      const response = await listRegulatorySources(auth as AuthCredentials);
      setSources(response.items);
    } catch (error) {
      setListError(error);
    } finally {
      setLoading(false);
    }
  }, [auth]);

  const registerSource = useCallback(
    async (payload: RegulatorySourceCreateRequest) => {
      setRegisterError(null);
      setRegisterSuccess(null);
      setRegisterPending(true);
      try {
        const source = await registerRegulatorySource(
          auth as AuthCredentials,
          payload,
        );
        setRegisterSuccess(`Source “${source.title}” registered.`);
        // Optimistically add the new source so it appears immediately.
        setSources((prev) =>
          prev === null ? [source] : [...prev, source],
        );
        // Refresh to converge with the server. If the refresh fails, the
        // registration success message is retained — we do not falsely
        // report registration failure.
        try {
          await loadSources();
        } catch {
          // Refresh failure is not registration failure.
        }
      } catch (caught) {
        setRegisterError(userFacingErrorMessage(caught));
      } finally {
        setRegisterPending(false);
      }
    },
    [auth, loadSources],
  );

  useEffect(() => {
    void loadSources();
  }, [loadSources]);

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
        <button
          type="button"
          className="primary-button"
          onClick={() => setRegisterOpen((open) => !open)}
          disabled={registerPending}
        >
          {registerOpen ? "Hide registration form" : "Register source"}
        </button>
      </header>

      {registerSuccess ? (
        <p className="success-message" role="status">
          {registerSuccess}
        </p>
      ) : null}
      {registerError ? (
        <p role="alert" className="ledger-reason">{registerError}</p>
      ) : null}
      {registerOpen ? (
        <RegisterSourceForm auth={auth as AuthCredentials} onRegister={registerSource} />
      ) : null}

      {loading ? <LoadingState text="Loading regulatory sources…" /> : null}
      {listError ? (
        <ErrorNotice error={listError} onRetry={() => void loadSources()} />
      ) : null}
      {!loading && !listError && sources !== null && sources.length === 0 ? (
        <EmptyState
          title="No regulatory sources registered"
          body="Sources are registered through the regulatory intake API. This view lists what exists — it does not fabricate records."
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
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setSelectedSourceId(source.id)}
                  >
                    Inspect source
                  </button>
                </p>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {selectedSourceId ? (
        <SourceDetail
          auth={auth as AuthCredentials}
          sourceId={selectedSourceId}
          onClose={() => setSelectedSourceId(null)}
        />
      ) : null}
    </div>
  );
}

function SourceDetail({
  auth,
  sourceId,
  onClose,
}: {
  auth: AuthCredentials;
  sourceId: string;
  onClose: () => void;
}) {
  const [source, setSource] = useState<RegulatorySource | null>(null);
  const [artifacts, setArtifacts] = useState<RegulatoryArtifact[] | null>(null);
  const [jobs, setJobs] = useState<RegulatoryIngestionJob[] | null>(null);
  const [candidates, setCandidates] = useState<RegulatoryCandidate[] | null>(null);
  const [flags, setFlags] = useState<RegulatoryGovernanceFlag[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // M4 — bounded retry for a terminally failed ingestion job.
  const [retryPendingJobId, setRetryPendingJobId] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrySuccess, setRetrySuccess] = useState<string | null>(null);

  // M7 — authorized source withdrawal.
  const [withdrawRationale, setWithdrawRationale] = useState("");
  const [withdrawPending, setWithdrawPending] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [withdrawSuccess, setWithdrawSuccess] = useState<string | null>(null);

  // Sequence guard: when the inspected source changes while a load is in
  // flight, only the most recent request may mutate this section's state.
  // Older responses arrive stale and are discarded instead of overlapping.
  const loadTokenRef = useRef(0);

  const load = useCallback(async () => {
    const token = ++loadTokenRef.current;
    setLoading(true);
    setError(null);
    try {
      const detail = await getRegulatorySource(auth, sourceId);
      if (token !== loadTokenRef.current) return;
      setSource(detail);
      const [artifactRows, jobRows, candidateRows, flagRows] = await Promise.all([
        listSourceArtifacts(auth, sourceId),
        listSourceJobs(auth, sourceId),
        listSourceCandidates(auth, sourceId),
        listFlagsForSource(auth, sourceId),
      ]);
      if (token !== loadTokenRef.current) return;
      setArtifacts(artifactRows.items);
      setJobs(jobRows.items);
      setCandidates(candidateRows.items);
      setFlags(flagRows.items);
    } catch (caught) {
      if (token !== loadTokenRef.current) return;
      setError(caught);
    } finally {
      if (token === loadTokenRef.current) {
        setLoading(false);
      }
    }
  }, [auth, sourceId]);

  const handleUpload = useCallback(
    async (file: File) => {
      const fileRejection = describeUnsupportedArtifactFile(file);
      if (fileRejection) {
        setUploadError(fileRejection);
        return;
      }
      setUploadPending(true);
      setUploadError(null);
      setUploadSuccess(null);
      try {
        const content_base64 = await file.arrayBuffer().then((buf) => {
          const bytes = new Uint8Array(buf);
          const chunkSize = 0x8000;
          let binary = "";
          for (let offset = 0; offset < bytes.length; offset += chunkSize) {
            const chunk = bytes.subarray(offset, offset + chunkSize);
            binary += String.fromCharCode(...chunk);
          }
          return btoa(binary);
        });
        const result = await uploadRegulatoryArtifact(auth as AuthCredentials, sourceId, {
          content_base64,
          content_type: resolveArtifactContentType(file),
          source_version: source?.version ?? null,
        });
        setUploadSuccess(`Artifact “${file.name}” uploaded (${result.content_length} bytes, ${result.content_type}).`);
        setUploadFile(null);
        await load();
      } catch (caught) {
        setUploadError(userFacingErrorMessage(caught));
      } finally {
        setUploadPending(false);
      }
    },
    [auth, sourceId, source?.version, load],
  );

  const handleRetryJob = useCallback(
    async (jobId: string) => {
      setRetryPendingJobId(jobId);
      setRetryError(null);
      setRetrySuccess(null);
      try {
        const retried = await retryRegulatoryIngestionJob(
          auth as AuthCredentials,
          jobId,
        );
        // The retry is a new attempt row; the ledger reflects it only
        // after the server-confirmed refresh converges.
        setRetrySuccess(
          `Retry recorded: a new ingestion attempt (${retried.attempt_number}) was created for the failed job. The job remains pending until the worker processes it.`,
        );
        await load();
      } catch (caught) {
        setRetryError(userFacingErrorMessage(caught));
      } finally {
        setRetryPendingJobId(null);
      }
    },
    [auth, load],
  );

  const handleWithdrawSource = useCallback(async () => {
    if (!withdrawRationale.trim()) {
      setWithdrawError("A rationale is required to withdraw the source.");
      return;
    }
    setWithdrawPending(true);
    setWithdrawError(null);
    setWithdrawSuccess(null);
    try {
      const result = await withdrawRegulatorySource(auth as AuthCredentials, sourceId, {
        rationale: withdrawRationale.trim(),
      });
      setWithdrawSuccess(
        `Source withdrawn as recorded. Status: ${result.status}; ${result.governance_flags_raised} pending withdrawal governance flag(s) raised.`,
      );
      setWithdrawRationale("");
      await load();
    } catch (caught) {
      setWithdrawError(userFacingErrorMessage(caught));
    } finally {
      setWithdrawPending(false);
    }
  }, [auth, sourceId, withdrawRationale, load]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section aria-label="Source detail">
      <p className="action-row">
        <button type="button" className="ghost-button" onClick={onClose}>
          Close source detail
        </button>
      </p>
      {loading ? <LoadingState text="Loading source…" /> : null}
      {error ? <ErrorNotice error={error} onRetry={() => void load()} /> : null}
      {source ? (
        <>
          <h2>{source.title}</h2>
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
            <Field label="Retrieval timestamp">{source.retrieval_timestamp ?? "Unknown — not recorded"}</Field>
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

          <h3>Governance flags</h3>
          {flags !== null && flags.length === 0 ? (
            <p className="muted">No governance flags recorded for this source.</p>
          ) : null}
          {flags !== null && flags.length > 0 ? (
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
          ) : null}

          <section aria-label="Withdraw source">
            <h3>Withdraw source</h3>
            {source.status === "withdrawn" || source.status === "archived" ? (
              <p className="muted">
                This source is already {source.status}. The backend refuses a
                further withdrawal; nothing is offered here.
              </p>
            ) : (
              <>
                <p className="muted">
                  Withdrawing the source sets its status to
                  {" "}<code>withdrawn</code> and raises a pending withdrawal
                  governance flag for every linked requirement; nothing linked
                  to the source can be published or re-verified while the flags
                  remain pending. The rationale is mandatory and recorded.
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

          <h3>Ingestion jobs</h3>
          {jobs !== null && jobs.length === 0 ? (
            <p className="muted">No ingestion jobs for this source.</p>
          ) : null}
          {jobs !== null && jobs.length > 0 ? (
            <ol className="ledger">
              {jobs.map((job) => (
                <li key={job.id} className="ledger-row">
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
                        {retryPendingJobId === job.id
                          ? "Recording retry…"
                          : "Retry failed job"}
                      </button>
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : null}
          {retryError ? (
            <p role="alert" className="ledger-reason">{retryError}</p>
          ) : null}
          {retrySuccess ? (
            <p className="success-message" role="status">{retrySuccess}</p>
          ) : null}

          <h3>Artifacts</h3>
          {artifacts !== null && artifacts.length === 0 ? (
            <p className="muted">No artifacts uploaded for this source.</p>
          ) : null}
          {artifacts !== null && artifacts.length > 0 ? (
            <ol className="ledger">
              {artifacts.map((artifact) => (
                <li key={artifact.id} className="ledger-row">
                  <dl className="ledger-status">
                    <div>
                      <dt>Content type</dt>
                      <dd>{artifact.content_type}</dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd>
                        <StatusBadge value={artifact.status} tone={tone(artifact.status)} />
                      </dd>
                    </div>
                    <div>
                      <dt>Acquired at</dt>
                      <dd>{createdAt(artifact.acquired_at)}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ol>
          ) : null}

          <section aria-label="Upload artifact">
            <h3>Upload original regulatory document</h3>
            <p className="muted">
              Supported: {SUPPORTED_ARTIFACT_TEXT} (max 10 MB). The backend
              validates every file; unsupported or oversized files are
              rejected.
            </p>
            <form
              className="form"
              onSubmit={(event) => {
                event.preventDefault();
                if (uploadFile) {
                  void handleUpload(uploadFile);
                }
              }}
            >
              <fieldset>
                <div className="form-row">
                  <label htmlFor="artifact-file">Choose file</label>
                  <input
                    id="artifact-file"
                    type="file"
                    accept={REGULATORY_ARTIFACT_ACCEPT}
                    disabled={uploadPending || loading}
                    onChange={(event) => {
                      const file = event.target.files?.[0] ?? null;
                      if (!file) {
                        setUploadFile(null);
                        return;
                      }
                      const fileRejection = describeUnsupportedArtifactFile(file);
                      if (fileRejection) {
                        // Unsupported files are never stored as the
                        // selection, so the submit path cannot send them.
                        setUploadFile(null);
                        setUploadError(fileRejection);
                        setUploadSuccess(null);
                        event.target.value = "";
                        return;
                      }
                      setUploadError(null);
                      setUploadFile(file);
                    }}
                  />
                </div>
                {uploadFile ? (
                  <div className="form-row">
                    <p className="hint">
                      Selected: {uploadFile.name} ({Math.round(uploadFile.size / 1024)} KB, {uploadFile.type || "unknown type"})
                    </p>
                  </div>
                ) : null}
              </fieldset>
              <div className="form-row">
                <button
                  type="submit"
                  className="primary-button"
                  disabled={uploadPending || loading || !uploadFile}
                >
                  {uploadPending ? "Uploading…" : "Upload document"}
                </button>
              </div>
            </form>
            {uploadError ? (
              <p role="alert" className="ledger-reason">{uploadError}</p>
            ) : null}
            {uploadSuccess ? (
              <p className="success-message" role="status">{uploadSuccess}</p>
            ) : null}
          </section>

          <h3>Candidate requirements</h3>
          {candidates !== null && candidates.length === 0 ? (
            <p className="muted">
              No candidates extracted or entered for this source. Manual
              candidate entry is not offered here because no authorized
              backend operation creates candidates by hand in this view — it
              would be a separate, backend-backed capability.
            </p>
          ) : null}
          {candidates !== null && candidates.length > 0 ? (
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
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setSelectedCandidateId(candidate.id)}
                    >
                      Review candidate
                    </button>
                  </p>
                </li>
              ))}
            </ol>
          ) : null}

          {selectedCandidateId ? (
            <CandidateReview
              auth={auth}
              candidateId={selectedCandidateId}
              onClose={() => setSelectedCandidateId(null)}
              onRefresh={load}
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}

export function CandidateReview({
  auth,
  candidateId,
  onClose,
  onRefresh,
}: {
  auth: AuthCredentials;
  candidateId: string;
  onClose: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [candidate, setCandidate] = useState<RegulatoryCandidate | null>(null);
  const [stageA, setStageA] = useState<RegulatoryStageAState | null>(null);
  const [stageAHistory, setStageAHistory] = useState<RegulatoryStageAHistoryEntry[]>([]);
  const [stageB, setStageB] = useState<RegulatoryStageBState | null>(null);
  const [stageBHistory, setStageBHistory] = useState<RegulatoryStageBHistoryEntry[]>([]);
  const [flags, setFlags] = useState<RegulatoryGovernanceFlag[]>([]);
  const [wordingCorrections, setWordingCorrections] = useState<
    RegulatoryWordingCorrection[]
  >([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  // Form state — separate for each stage so the decisions remain distinct.
  const [stageARationale, setStageARationale] = useState("");
  const [stageADecision, setStageADecision] =
    useState<"verified" | "rejected" | "clarification_required">("verified");
  const [stageACorrectedText, setStageACorrectedText] = useState("");
  const [stageAPending, setStageAPending] = useState(false);
  const [stageAError, setStageAError] = useState<string | null>(null);

  const [stageBRationale, setStageBRationale] = useState("");
  const [stageBDecision, setStageBDecision] =
    useState<"approved" | "rejected" | "clarification_required">("approved");
  const [stageBPilotScope, setStageBPilotScope] = useState("");
  const [stageBPending, setStageBPending] = useState(false);
  const [stageBError, setStageBError] = useState<string | null>(null);

  // Sequence guard: only the most recent candidate load may mutate state.
  const loadTokenRef = useRef(0);

  const load = useCallback(async () => {
    const token = ++loadTokenRef.current;
    setLoading(true);
    setError(null);
    try {
      const detail = await getRegulatoryCandidate(auth, candidateId);
      if (token !== loadTokenRef.current) return;
      const [
        stageAResponse,
        stageAHistoryResponse,
        stageBResponse,
        stageBHistoryResponse,
        flagRows,
        wordingResponse,
      ] = await Promise.all([
        getCandidateStageA(auth, candidateId),
        listStageAHistory(auth, candidateId),
        getCandidateStageB(auth, candidateId),
        listStageBHistory(auth, candidateId),
        listRequirementGovernanceFlags(auth, detail.id),
        listWordingCorrections(auth, candidateId),
      ]);
      if (token !== loadTokenRef.current) return;
      setCandidate(detail);
      setStageA(stageAResponse);
      setStageAHistory(stageAHistoryResponse.items);
      setStageB(stageBResponse);
      setStageBHistory(stageBHistoryResponse.items);
      setFlags(flagRows.items);
      setWordingCorrections(wordingResponse.items);
    } catch (caught) {
      if (token !== loadTokenRef.current) return;
      setError(caught);
    } finally {
      if (token === loadTokenRef.current) {
        setLoading(false);
      }
    }
  }, [auth, candidateId]);

  useEffect(() => {
    void load();
  }, [load]);

  const recordStageA = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!stageARationale.trim()) {
      setStageAError("A rationale is required for the Stage A decision.");
      return;
    }
    const correctedText = stageACorrectedText.trim();
    if (correctedText && stageADecision !== "verified") {
      setStageAError(
        "Corrected wording can only be recorded with a verified decision; the recording rules mirror the backend.",
      );
      return;
    }
    if (correctedText && candidate && correctedText === candidate.requirement_text) {
      setStageAError(
        "A wording correction must differ from the currently recorded wording.",
      );
      return;
    }
    setStageAPending(true);
    setStageAError(null);
    try {
      await submitStageADecision(auth, candidateId, {
        stage_a_status: stageADecision,
        rationale: stageARationale.trim(),
        ...(correctedText
          ? { corrected_requirement_text: correctedText }
          : {}),
      });
      setStageARationale("");
      setStageACorrectedText("");
      await load();
      await onRefresh();
    } catch (caught) {
      setStageAError(userFacingErrorMessage(caught));
    } finally {
      setStageAPending(false);
    }
  };

  const recordStageB = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!stageBRationale.trim()) {
      setStageBError("A rationale is required for the Stage B decision.");
      return;
    }
    if (!stageBPilotScope.trim()) {
      setStageBError("Pilot scope is required for the Stage B decision.");
      return;
    }
    setStageBPending(true);
    setStageBError(null);
    try {
      await submitStageBDecision(auth, candidateId, {
        stage_b_status: stageBDecision,
        rationale: stageBRationale.trim(),
        pilot_scope: stageBPilotScope.trim(),
      });
      setStageBRationale("");
      setStageBPilotScope("");
      await load();
      await onRefresh();
    } catch (caught) {
      setStageBError(userFacingErrorMessage(caught));
    } finally {
      setStageBPending(false);
    }
  };

  return (
    <section aria-label="Candidate review">
      <p className="action-row">
        <button type="button" className="ghost-button" onClick={onClose}>
          Close candidate review
        </button>
      </p>
      <p className="muted">
        Reviewer identity, decisions, and reasons are recorded by the backend
        with an append-only audit trail. Extraction and review decisions do
        <strong> not</strong> publish this requirement or make it
        exporter-applicable.
      </p>
      {loading ? <LoadingState text="Loading candidate…" /> : null}
      {error ? <ErrorNotice error={error} onRetry={() => void load()} /> : null}
      {candidate ? (
        <>
          <dl className="results-block">
            <Field label="Candidate ID">
              <Identifier value={candidate.id} short={36} />
            </Field>
            <Field label="Requirement text">{candidate.requirement_text}</Field>
            <Field label="Type">{candidate.requirement_type || "—"}</Field>
            <Field label="Source location">
              {Object.keys(candidate.source_location).length > 0
                ? JSON.stringify(candidate.source_location)
                : "—"}
            </Field>
            <Field label="Status">
              <StatusBadge value={candidate.status} tone={tone(candidate.status)} />
            </Field>
            <Field label="Extraction outcome">
              <StatusBadge
                value={candidate.extraction_outcome}
                tone={tone(candidate.extraction_outcome)}
              />
            </Field>
            <Field label="Entry">{candidate.manual_entry ? "Manual" : "Extracted"}</Field>
            <Field label="Artifact reference">
              {candidate.artifact_id ? <Identifier value={candidate.artifact_id} short={36} /> : "—"}
            </Field>
            <Field label="Extracted by">
              {candidate.reviewer_user_id ? (
                <Identifier value={candidate.reviewer_user_id} short={36} />
              ) : (
                "—"
              )}
            </Field>
            <Field label="Created">{candidate.created_at ?? "—"}</Field>
          </dl>

          <h4>Governance flags for this requirement</h4>
          {flags.length === 0 ? (
            <p className="muted">No governance flags recorded for this requirement.</p>
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
                </li>
              ))}
            </ol>
          )}
          {flags.some((flag) => flag.status === "pending_review") ? (
            <p role="alert" className="ledger-reason">
              A pending governance flag exists for this requirement. Pending
              flags cannot be cleared or bypassed from this view; review
              completion follows the governance rules only.
            </p>
          ) : null}

          <h4>Stage A — source traceability and wording verification</h4>
          <dl className="results-block">
            <Field label="Stage A status">
              <StatusBadge value={stageA?.stage_a_status ?? "unknown"} tone="muted" />
            </Field>
            <Field label="Stage A reviewer">
              {stageA?.stage_a_reviewer_user_id ? (
                <Identifier value={stageA.stage_a_reviewer_user_id} short={36} />
              ) : (
                "—"
              )}
            </Field>
            <Field label="Stage A rationale">{stageA?.stage_a_rationale ?? "—"}</Field>
          </dl>
          {stageAHistory.length > 0 ? (
            <CollapsibleList title="Stage A decision history" entries={stageAHistory.length} />
          ) : (
            <p className="muted">No Stage A decisions recorded yet.</p>
          )}
          {stageAHistory.map((entry) => (
            <p key={entry.id} className="muted">
              {entry.stage_a_status} — {createdAt(entry.reviewed_at)} — {entry.rationale}
            </p>
          ))}

          <h4>Recorded wording corrections</h4>
          {wordingCorrections.length === 0 ? (
            <p className="muted">No wording corrections recorded for this candidate.</p>
          ) : (
            <ol className="ledger">
              {wordingCorrections.map((correction) => (
                <li key={correction.id} className="ledger-row">
                  <p className="ledger-title">Original: {correction.original_text}</p>
                  <p className="ledger-title">Corrected: {correction.corrected_text}</p>
                  <p className="muted">
                    Recorded {createdAt(correction.created_at)} by{" "}
                    <Identifier value={correction.reviewer_user_id} short={36} />
                  </p>
                  <p className="ledger-reason">Rationale: {correction.rationale}</p>
                </li>
              ))}
            </ol>
          )}
          <form className="form" onSubmit={recordStageA}>
            <fieldset>
              <legend>Record Stage A verification</legend>
              <div className="form-row">
                <label htmlFor="stage-a-decision">Decision</label>
                <select
                  id="stage-a-decision"
                  value={stageADecision}
                  onChange={(event) =>
                    setStageADecision(
                      event.target.value as
                        | "verified"
                        | "rejected"
                        | "clarification_required",
                    )
                  }
                >
                  <option value="verified">verified</option>
                  <option value="rejected">rejected</option>
                  <option value="clarification_required">clarification_required</option>
                </select>
              </div>
              <div className="form-row">
                <label htmlFor="stage-a-rationale">Rationale (required)</label>
                <textarea
                  id="stage-a-rationale"
                  rows={3}
                  value={stageARationale}
                  onChange={(event) => setStageARationale(event.target.value)}
                  placeholder="Why this source traceability and wording decision"
                />
              </div>
              <div className="form-row">
                <label htmlFor="stage-a-corrected-wording">
                  Corrected requirement wording (optional, verified decisions only)
                </label>
                <textarea
                  id="stage-a-corrected-wording"
                  rows={3}
                  value={stageACorrectedText}
                  onChange={(event) => setStageACorrectedText(event.target.value)}
                  placeholder="Leave empty to record no wording correction"
                />
                <p className="hint">
                  Recording a correction preserves the original wording
                  append-only; the corrected text becomes the operative
                  wording. Corrections are refused by the backend once
                  Stage B has approved the requirement, and they require a
                  rationale — leave empty to send none.
                </p>
              </div>
            </fieldset>
            {stageAError ? (
              <p role="alert" className="ledger-reason">{stageAError}</p>
            ) : null}
            <button type="submit" className="primary-button" disabled={stageAPending}>
              {stageAPending ? "Recording…" : "Record Stage A verification"}
            </button>
          </form>

          <h4>Stage B — pilot-scope applicability approval</h4>
          <dl className="results-block">
            <Field label="Stage B status">
              <StatusBadge value={stageB?.stage_b_status ?? "unknown"} tone="muted" />
            </Field>
            <Field label="Stage B reviewer">
              {stageB?.stage_b_reviewer_user_id ? (
                <Identifier value={stageB.stage_b_reviewer_user_id} short={36} />
              ) : (
                "—"
              )}
            </Field>
            <Field label="Stage B rationale">{stageB?.stage_b_rationale ?? "—"}</Field>
            <Field label="Stage B pilot scope">{stageB?.stage_b_pilot_scope ?? "—"}</Field>
          </dl>
          {stageBHistory.length === 0 ? (
            <p className="muted">No Stage B decisions recorded yet.</p>
          ) : (
            stageBHistory.map((entry) => (
              <p key={entry.id} className="muted">
                {entry.stage_b_status} — {createdAt(entry.reviewed_at)} — {entry.rationale}
                {entry.evidence_references.length > 0
                  ? ` — evidence: ${entry.evidence_references
                      .map((ref) => (typeof ref === "string" ? ref : JSON.stringify(ref)))
                      .join(", ")}`
                  : ""}
              </p>
            ))
          )}
          <form className="form" onSubmit={recordStageB}>
            <fieldset>
              <legend>Record Stage B approval</legend>
              <div className="form-row">
                <label htmlFor="stage-b-decision">Decision</label>
                <select
                  id="stage-b-decision"
                  value={stageBDecision}
                  onChange={(event) =>
                    setStageBDecision(
                      event.target.value as
                        | "approved"
                        | "rejected"
                        | "clarification_required",
                    )
                  }
                >
                  <option value="approved">approved</option>
                  <option value="rejected">rejected</option>
                  <option value="clarification_required">clarification_required</option>
                </select>
              </div>
              <div className="form-row">
                <label htmlFor="stage-b-pilot-scope">Pilot scope (required)</label>
                <input
                  id="stage-b-pilot-scope"
                  type="text"
                  value={stageBPilotScope}
                  onChange={(event) => setStageBPilotScope(event.target.value)}
                  placeholder="e.g. sesame EU pilot"
                />
              </div>
              <div className="form-row">
                <label htmlFor="stage-b-rationale">Rationale (required)</label>
                <textarea
                  id="stage-b-rationale"
                  rows={3}
                  value={stageBRationale}
                  onChange={(event) => setStageBRationale(event.target.value)}
                  placeholder="Why this pilot-applicability decision"
                />
              </div>
              <p className="muted">
                Evidence is recorded by the backend as structured reference
                objects; structured evidence attachment is not offered from
                this view and is not required for the decision to be
                recorded. Pilot scope and rationale are mandatory.
              </p>
            </fieldset>
            {stageBError ? (
              <p role="alert" className="ledger-reason">{stageBError}</p>
            ) : null}
            <button type="submit" className="primary-button" disabled={stageBPending}>
              {stageBPending ? "Recording…" : "Record Stage B approval"}
            </button>
          </form>
        </>
      ) : null}
    </section>
  );
}

/** Small marker used so tests can assert history sections exist. */
function CollapsibleList({ title, entries }: { title: string; entries: number }) {
  return <p className="eyebrow">{`${title} (${entries} recorded)`}</p>;
}

function RegisterSourceForm({
  auth,
  onRegister,
}: {
  auth: AuthCredentials;
  onRegister: (payload: RegulatorySourceCreateRequest) => void;
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
      await onRegister({
        authority_id: authorityId.trim(),
        jurisdiction: jurisdiction.trim(),
        title: title.trim(),
        version: version.trim() || undefined,
        status,
        effective_date: effectiveDate || undefined,
        publication_date: publicationDate || undefined,
        source_url: sourceUrl.trim() || undefined,
      });
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
