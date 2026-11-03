import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { userFacingErrorMessage } from "../../api/client";
import type { AuthCredentials } from "../../api/client";
import {
  getCandidateStageA,
  getCandidateStageB,
  getRegulatoryCandidate,
  listRequirementGovernanceFlags,
  listStageAHistory,
  listStageBHistory,
  listWordingCorrections,
  submitStageADecision,
  submitStageBDecision,
  type RegulatoryCandidate,
  type RegulatoryGovernanceFlag,
  type RegulatoryStageAHistoryEntry,
  type RegulatoryStageAState,
  type RegulatoryStageBHistoryEntry,
  type RegulatoryStageBState,
  type RegulatoryWordingCorrection,
} from "../../api/regulatory";
import {
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
} from "../../components/StatusBits";
import { STAGE_A_VERIFY, STAGE_B_APPROVE } from "../../types/api";
import { createdAt, tone } from "./regulatoryUi";
import { useStaffPermissions } from "./useStaffPermissions";

/**
 * Candidate review: Stage A (source traceability and wording) and
 * Stage B (pilot-scope applicability) stay two distinct, separately
 * recorded decisions. Reviewer identity and rationale are recorded by
 * the backend in an append-only trail. Nothing here publishes a
 * requirement or marks it exporter-applicable.
 */

export function CandidateReview({
  auth,
  candidateId,
  backTo,
  onDecisionRecorded,
}: {
  auth: AuthCredentials;
  candidateId: string;
  /** Where the "Back to candidates" link points. */
  backTo: string;
  onDecisionRecorded?: () => Promise<void>;
}) {
  const permissions = useStaffPermissions();
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
      await onDecisionRecorded?.();
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
      await onDecisionRecorded?.();
    } catch (caught) {
      setStageBError(userFacingErrorMessage(caught));
    } finally {
      setStageBPending(false);
    }
  };

  return (
    <section aria-label="Candidate review">
      <p className="action-row">
        <Link to={backTo} className="ghost-button">
          Back to candidates
        </Link>
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
        <div className="reg-review-grid">
          <div className="reg-review-facts">
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

          </div>
          <div className="reg-review-decisions">
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
          {!permissions.mayAttempt(STAGE_A_VERIFY) ? (
            <p className="reg-notice" role="note">
              Your account does not hold the Stage A verification grant, so
              the decision form is not offered. Ask an administrator for
              access if you need to record Stage A decisions.
            </p>
          ) : (
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
          )}

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
          <p className="reg-notice" role="note">
            Stage B requires a verified Stage A decision, and the Stage B
            reviewer must be a different person from the Stage A reviewer.
            The server enforces both rules.
          </p>
          {!permissions.mayAttempt(STAGE_B_APPROVE) ? (
            <p className="reg-notice" role="note">
              Your account does not hold the Stage B approval grant, so the
              decision form is not offered.
            </p>
          ) : (
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
          )}
          </div>
        </div>
      ) : null}
    </section>
  );
}

/** Small marker used so tests can assert history sections exist. */
function CollapsibleList({ title, entries }: { title: string; entries: number }) {
  return <p className="eyebrow">{`${title} (${entries} recorded)`}</p>;
}
