import { useState } from "react";

/**
 * Structured assembly of compliance case views for
 * caller-supplied endpoints (`case-readiness`, `analyze`).
 *
 * Cases are built ONLY from records the UI already holds
 * or the user types: requirement identity/text, recorded
 * applicability and assessment outcomes with reasons, and
 * evidence references (typed or picked from supplied IDs).
 * Nothing is inferred — the backend validates and rejects
 * malformed cases with its own errors, which callers
 * surface unchanged.
 */

export interface EvidenceRefDraft {
  evidence_id: string;
  evidence_type: string;
  reference: string;
  status: string;
}

export interface CaseDraft {
  requirement_id: string;
  requirement_text: string;
  applicability: string;
  applicability_reason: string;
  assessment: string;
  assessment_reason: string;
  evidence: EvidenceRefDraft[];
}

export function newCaseDraft(): CaseDraft {
  return {
    requirement_id: "",
    requirement_text: "",
    applicability: "applicable",
    applicability_reason: "",
    assessment: "unknown",
    assessment_reason: "",
    evidence: [],
  };
}

export function newEvidenceRefDraft(): EvidenceRefDraft {
  return { evidence_id: "", evidence_type: "", reference: "", status: "" };
}

/** Assemble wire-ready case views, dropping rows without identity/text. */
export function buildCases(
  tenantId: string,
  caseId: string,
  drafts: CaseDraft[],
): Array<Record<string, unknown>> {
  return drafts
    .filter((draft) => draft.requirement_id.trim() && draft.requirement_text.trim())
    .map((draft) => ({
      id: `case-${draft.requirement_id.trim()}`,
      tenant_id: tenantId,
      requirement: {
        id: draft.requirement_id.trim(),
        requirement_text: draft.requirement_text.trim(),
      },
      applicability: {
        outcome: draft.applicability,
        reason: draft.applicability_reason.trim(),
      },
      assessment: {
        outcome: draft.assessment,
        reason: draft.assessment_reason.trim(),
      },
      evidence: draft.evidence
        .filter((item) => item.evidence_id.trim())
        .map((item) => ({
          evidence_id: item.evidence_id.trim(),
          evidence_type: item.evidence_type.trim(),
          reference: item.reference.trim(),
          status: item.status.trim(),
        })),
      case_reference: caseId,
    }));
}

const APPLICABILITY_OPTIONS = ["applicable", "not_applicable", "unknown"];
const ASSESSMENT_OPTIONS = ["satisfied", "not_satisfied", "unknown"];

export function CaseBuilder({
  drafts,
  onChange,
  suppliedEvidenceIds,
  idPrefix,
}: {
  drafts: CaseDraft[];
  onChange: (drafts: CaseDraft[]) => void;
  suppliedEvidenceIds: string[];
  idPrefix: string;
}) {
  const [expanded, setExpanded] = useState(0);

  const update = (index: number, patch: Partial<CaseDraft>) => {
    onChange(drafts.map((draft, i) => (i === index ? { ...draft, ...patch } : draft)));
  };

  const updateEvidence = (
    caseIndex: number,
    evidenceIndex: number,
    patch: Partial<EvidenceRefDraft>,
  ) => {
    const draft = drafts[caseIndex];
    update(caseIndex, {
      evidence: draft.evidence.map((item, i) =>
        i === evidenceIndex ? { ...item, ...patch } : item,
      ),
    });
  };

  return (
    <div className="case-builder">
      {drafts.map((draft, index) => {
        const open = expanded === index;
        const title = draft.requirement_text.trim() || `Case ${index + 1}`;
        return (
          <fieldset key={`${idPrefix}-case-${index}`}>
            <legend>
              <button
                type="button"
                className="ghost-button"
                aria-expanded={open}
                onClick={() => setExpanded(open ? -1 : index)}
              >
                {title}
              </button>
            </legend>
            {open ? (
              <>
                <div className="form-grid">
                  <div className="form-row">
                    <label htmlFor={`${idPrefix}-req-id-${index}`}>Requirement ID</label>
                    <input
                      id={`${idPrefix}-req-id-${index}`}
                      type="text"
                      value={draft.requirement_id}
                      onChange={(event) => update(index, { requirement_id: event.target.value })}
                      placeholder="Requirement identifier"
                    />
                  </div>
                  <div className="form-row">
                    <label htmlFor={`${idPrefix}-req-text-${index}`}>Requirement text</label>
                    <input
                      id={`${idPrefix}-req-text-${index}`}
                      type="text"
                      value={draft.requirement_text}
                      onChange={(event) => update(index, { requirement_text: event.target.value })}
                      placeholder="What the regulation requires"
                    />
                  </div>
                  <div className="form-row">
                    <label htmlFor={`${idPrefix}-applicability-${index}`}>Applicability</label>
                    <select
                      id={`${idPrefix}-applicability-${index}`}
                      value={draft.applicability}
                      onChange={(event) => update(index, { applicability: event.target.value })}
                    >
                      {APPLICABILITY_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-row">
                    <label htmlFor={`${idPrefix}-applicability-reason-${index}`}>
                      Applicability reason
                    </label>
                    <input
                      id={`${idPrefix}-applicability-reason-${index}`}
                      type="text"
                      value={draft.applicability_reason}
                      onChange={(event) =>
                        update(index, { applicability_reason: event.target.value })
                      }
                      placeholder="Why this outcome holds"
                    />
                  </div>
                  <div className="form-row">
                    <label htmlFor={`${idPrefix}-assessment-${index}`}>Assessment</label>
                    <select
                      id={`${idPrefix}-assessment-${index}`}
                      value={draft.assessment}
                      onChange={(event) => update(index, { assessment: event.target.value })}
                    >
                      {ASSESSMENT_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-row">
                    <label htmlFor={`${idPrefix}-assessment-reason-${index}`}>
                      Assessment reason
                    </label>
                    <input
                      id={`${idPrefix}-assessment-reason-${index}`}
                      type="text"
                      value={draft.assessment_reason}
                      onChange={(event) =>
                        update(index, { assessment_reason: event.target.value })
                      }
                      placeholder="Why this assessment holds"
                    />
                  </div>
                </div>
                <h4>Evidence references</h4>
                {draft.evidence.length === 0 ? (
                  <p className="muted">No evidence references attached to this case.</p>
                ) : null}
                {draft.evidence.map((item, evidenceIndex) => (
                  <div className="form-grid" key={`${idPrefix}-case-${index}-ev-${evidenceIndex}`}>
                    <div className="form-row">
                      <label htmlFor={`${idPrefix}-ev-id-${index}-${evidenceIndex}`}>
                        Evidence ID
                      </label>
                      <input
                        id={`${idPrefix}-ev-id-${index}-${evidenceIndex}`}
                        type="text"
                        value={item.evidence_id}
                        onChange={(event) =>
                          updateEvidence(index, evidenceIndex, {
                            evidence_id: event.target.value,
                          })
                        }
                        placeholder="Recorded evidence ID"
                      />
                    </div>
                    <div className="form-row">
                      <label htmlFor={`${idPrefix}-ev-type-${index}-${evidenceIndex}`}>
                        Evidence type
                      </label>
                      <input
                        id={`${idPrefix}-ev-type-${index}-${evidenceIndex}`}
                        type="text"
                        value={item.evidence_type}
                        onChange={(event) =>
                          updateEvidence(index, evidenceIndex, {
                            evidence_type: event.target.value,
                          })
                        }
                        placeholder="e.g. certificate"
                      />
                    </div>
                    <div className="form-row">
                      <label htmlFor={`${idPrefix}-ev-ref-${index}-${evidenceIndex}`}>
                        Reference
                      </label>
                      <input
                        id={`${idPrefix}-ev-ref-${index}-${evidenceIndex}`}
                        type="text"
                        value={item.reference}
                        onChange={(event) =>
                          updateEvidence(index, evidenceIndex, {
                            reference: event.target.value,
                          })
                        }
                        placeholder="URI or registry pointer"
                      />
                    </div>
                    <div className="form-row">
                      <label htmlFor={`${idPrefix}-ev-status-${index}-${evidenceIndex}`}>
                        Status
                      </label>
                      <input
                        id={`${idPrefix}-ev-status-${index}-${evidenceIndex}`}
                        type="text"
                        value={item.status}
                        onChange={(event) =>
                          updateEvidence(index, evidenceIndex, {
                            status: event.target.value,
                          })
                        }
                        placeholder="e.g. accepted"
                      />
                    </div>
                  </div>
                ))}
                <div className="action-row">
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() =>
                      update(index, {
                        evidence: [...draft.evidence, newEvidenceRefDraft()],
                      })
                    }
                  >
                    Add evidence reference
                  </button>
                  {suppliedEvidenceIds.length > 0 ? (
                    <span className="muted">
                      Supplied on this workflow: {suppliedEvidenceIds.join(", ")}
                    </span>
                  ) : null}
                </div>
              </>
            ) : null}
          </fieldset>
        );
      })}
    </div>
  );
}