import { useCallback, useEffect, useState } from "react";
import { userFacingErrorMessage } from "../../api/client";
import type { AuthCredentials } from "../../api/client";
import {
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
  submitStageADecision,
  submitStageBDecision,
  type RegulatoryArtifact,
  type RegulatoryCandidate,
  type RegulatoryGovernanceFlag,
  type RegulatoryIngestionJob,
  type RegulatorySource,
  type RegulatoryStageAHistoryEntry,
  type RegulatoryStageAState,
  type RegulatoryStageBHistoryEntry,
  type RegulatoryStageBState,
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
      </header>

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

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const detail = await getRegulatorySource(auth, sourceId);
      setSource(detail);
      const [artifactRows, jobRows, candidateRows, flagRows] = await Promise.all([
        listSourceArtifacts(auth, sourceId),
        listSourceJobs(auth, sourceId),
        listSourceCandidates(auth, sourceId),
        listFlagsForSource(auth, sourceId),
      ]);
      setArtifacts(artifactRows.items);
      setJobs(jobRows.items);
      setCandidates(candidateRows.items);
      setFlags(flagRows.items);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, [auth, sourceId]);

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
                </li>
              ))}
            </ol>
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

          <h3>Candidate requirements</h3>
          {candidates !== null && candidates.length === 0 ? (
            <p className="muted">No candidates extracted or entered for this source.</p>
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
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  // Form state — separate for each stage so the decisions remain distinct.
  const [stageARationale, setStageARationale] = useState("");
  const [stageADecision, setStageADecision] =
    useState<"verified" | "rejected" | "clarification_required">("verified");
  const [stageAPending, setStageAPending] = useState(false);
  const [stageAError, setStageAError] = useState<string | null>(null);

  const [stageBRationale, setStageBRationale] = useState("");
  const [stageBDecision, setStageBDecision] =
    useState<"approved" | "rejected" | "clarification_required">("approved");
  const [stageBPilotScope, setStageBPilotScope] = useState("");
  const [stageBEvidenceRefs, setStageBEvidenceRefs] = useState("");
  const [stageBPending, setStageBPending] = useState(false);
  const [stageBError, setStageBError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const detail = await getRegulatoryCandidate(auth, candidateId);
      setCandidate(detail);
      const [
        stageAResponse,
        stageAHistoryResponse,
        stageBResponse,
        stageBHistoryResponse,
        flagRows,
      ] = await Promise.all([
        getCandidateStageA(auth, candidateId),
        listStageAHistory(auth, candidateId),
        getCandidateStageB(auth, candidateId),
        listStageBHistory(auth, candidateId),
        listRequirementGovernanceFlags(auth, detail.id),
      ]);
      setStageA(stageAResponse);
      setStageAHistory(stageAHistoryResponse.items);
      setStageB(stageBResponse);
      setStageBHistory(stageBHistoryResponse.items);
      setFlags(flagRows.items);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
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
    setStageAPending(true);
    setStageAError(null);
    try {
      await submitStageADecision(auth, candidateId, {
        stage_a_status: stageADecision,
        rationale: stageARationale.trim(),
      });
      setStageARationale("");
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
    setStageBPending(true);
    setStageBError(null);
    try {
      await submitStageBDecision(auth, candidateId, {
        stage_b_status: stageBDecision,
        rationale: stageBRationale.trim(),
        pilot_scope: stageBPilotScope.trim() || null,
        evidence_references: stageBEvidenceRefs.trim()
          ? stageBEvidenceRefs.split(",").map((value) => value.trim()).filter(Boolean)
          : null,
      });
      setStageBRationale("");
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
                  ? ` — evidence: ${entry.evidence_references.join(", ")}`
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
                <label htmlFor="stage-b-pilot-scope">Pilot scope (optional)</label>
                <input
                  id="stage-b-pilot-scope"
                  type="text"
                  value={stageBPilotScope}
                  onChange={(event) => setStageBPilotScope(event.target.value)}
                  placeholder="e.g. cocoa pilot"
                />
              </div>
              <div className="form-row">
                <label htmlFor="stage-b-evidence-refs">
                  Evidence references (comma-separated, optional)
                </label>
                <input
                  id="stage-b-evidence-refs"
                  type="text"
                  value={stageBEvidenceRefs}
                  onChange={(event) => setStageBEvidenceRefs(event.target.value)}
                  placeholder="evidence-id-1, evidence-id-2"
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
