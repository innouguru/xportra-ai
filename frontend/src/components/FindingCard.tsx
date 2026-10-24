import { Link } from "react-router-dom";
import type { AnalysisFinding } from "../types/api";
import {
  applicabilityLabel,
  assessmentLabel,
  assessmentTone,
  contradictionLabel,
  stateQualifier,
  sufficiencyLabel,
  uncertaintyLabel,
} from "../lib/findings";
import { Field, Identifier, StatusBadge } from "./StatusBits";

/**
 * One recorded finding. The primary view emphasizes its
 * meaning and next useful information; backend detail and
 * identifiers remain available on disclosure. Contradictions
 * are displayed, never resolved.
 */
export function FindingCard({
  finding,
  index,
  total,
  askAction,
  presentation = "workflow",
}: {
  finding: AnalysisFinding;
  /** Zero-based position in the report; renders "Finding N of M" when both are given. */
  index?: number;
  total?: number;
  /** Optional contextual entry point (e.g. Ask Xportra); rendered verbatim. */
  askAction?: React.ReactNode;
  /** Historical reports keep the same finding detail without exposing record identifiers. */
  presentation?: "workflow" | "historical";
}) {
  const assessmentNote = stateQualifier("assessment", finding.assessment);
  const sufficiencyNote = stateQualifier("sufficiency", finding.evidence_sufficiency);
  const showIdentifiers = presentation === "workflow";

  return (
    <article className="finding-card" aria-label={`Finding: ${finding.requirement_text}`}>
      {index !== undefined && total !== undefined ? (
        <p className="finding-count">
          Finding {index + 1} of {total}
        </p>
      ) : null}
      <p className="finding-kicker">Shipment finding</p>
      <h3 className="finding-requirement">{finding.requirement_text}</h3>
      <p className="finding-assessment">
        <StatusBadge value={assessmentLabel(finding.assessment)} tone={assessmentTone(finding.assessment)} />
        {assessmentNote ? <span className="muted"> {assessmentNote}</span> : null}
      </p>
      <p className="muted finding-limit">
        This is a recorded Xportra analysis result, not government approval or shipment clearance.
      </p>
      <section className="finding-section" aria-label="Explanation">
        <h4>What the analysis recorded</h4>
        <p>{finding.explanation}</p>
        {finding.uncertainty_explanation ? <p className="muted">{finding.uncertainty_explanation}</p> : null}
        {finding.sufficiency_explanation ? <p className="muted">{finding.sufficiency_explanation}</p> : null}
      </section>
      <section className="finding-section" aria-label="Evidence">
        <h4>Evidence references</h4>
        {finding.supporting_evidence.length === 0 && finding.conflicting_evidence.length === 0 ? (
          <p className="muted">
            No evidence references recorded for this finding.{" "}
            <Link to="../evidence">Open the evidence workspace</Link>.
          </p>
        ) : (
          <>
            {finding.supporting_evidence.length > 0 ? (
              <>
                <h5>Supporting</h5>
                <ul className="reference-list">
                  {finding.supporting_evidence.map((item, index) => (
                    <li key={`supporting-${index}`}>
                      <EvidenceReferenceView reference={item} showIdentifiers={showIdentifiers} />
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {finding.conflicting_evidence.length > 0 ? (
              <>
            <h5>Conflicting evidence — shown as recorded, not resolved</h5>
                <ul className="reference-list">
                  {finding.conflicting_evidence.map((item, index) => (
                    <li key={`conflicting-${index}`}>
                      <EvidenceReferenceView reference={item} showIdentifiers={showIdentifiers} />
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </>
        )}
      </section>
      {finding.missing_information.length > 0 ? (
        <section className="finding-section" aria-label="Missing information">
          <h4>Missing information</h4>
          <ul>
            {finding.missing_information.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <details className="finding-details" open={presentation === "historical"}>
        <summary>Analysis details and source records</summary>
        <dl className="field-grid finding-meta">
          {showIdentifiers ? (
            <Field label="Requirement ID">
              <Identifier value={finding.requirement_id} short={36} />
            </Field>
          ) : null}
          <Field label="Applicability">{applicabilityLabel(finding.applicability)}</Field>
          <Field label="Evidence support">{sufficiencyLabel(finding.evidence_sufficiency)}</Field>
          <Field label="Conflicting evidence">{contradictionLabel(finding.contradiction_state)}</Field>
          <Field label="Certainty">{uncertaintyLabel(finding.uncertainty)}</Field>
          <Field label="Recorded assessment">
            <StatusBadge value={assessmentLabel(finding.assessment)} tone={assessmentTone(finding.assessment)} />
            {sufficiencyNote ? <span className="muted"> — {sufficiencyNote}</span> : null}
          </Field>
        </dl>
        <h4>Sources and provenance</h4>
        {finding.sources.length === 0 && finding.knowledge_references.length === 0 ? (
          <p className="muted">No source references were recorded.</p>
        ) : (
          <ul className="reference-list">
            {[...finding.sources, ...finding.knowledge_references].map((source, index) => (
              <li key={`source-${index}`}>
                <SourceReference source={source} showIdentifiers={showIdentifiers} />
              </li>
            ))}
          </ul>
        )}
      </details>
      {askAction ? <p className="ledger-actions">{askAction}</p> : null}
    </article>
  );
}

function SourceReference({
  source,
  showIdentifiers,
}: {
  source: Record<string, unknown>;
  showIdentifiers: boolean;
}) {
  const label = [
    source["title"],
    source["label"],
    source["kind"],
    source["source_type"],
  ]
    .filter((item): item is string => typeof item === "string" && item.length > 0)
    .join(" · ")
    .replace(/_/g, " ");
  const location = [source["source_location"], source["location"], source["url"], source["source_url"]]
    .find((item): item is string => typeof item === "string" && item.length > 0);
  const identifier = showIdentifiers
    ? [source["identifier"], source["source_id"]].find(
        (item): item is string => typeof item === "string" && item.length > 0,
      )
    : undefined;
  const description = label || (identifier ? "Recorded source" : "Source reference recorded");
  return (
    <span>
      {description}
      {location ? <> — {location}</> : null}
      {identifier ? <> — <Identifier value={identifier} /></> : null}
    </span>
  );
}

function EvidenceReferenceView({
  reference,
  showIdentifiers,
}: {
  reference: Record<string, unknown>;
  showIdentifiers: boolean;
}) {
  const entries: Array<{ label: string; value: string; identifier?: boolean }> = [];
  for (const [key, label] of [
    ["evidence_type", "Document type"],
    ["reference", "Document reference"],
    ["status", "Recorded evidence status"],
  ]) {
    const value = reference[key];
    if (typeof value === "string" && value.length > 0) {
      entries.push({ label, value });
    }
  }
  const evidenceId =
    showIdentifiers && typeof reference["evidence_id"] === "string"
      ? reference["evidence_id"]
      : null;
  if (evidenceId) {
    entries.push({ label: "Evidence record", value: evidenceId, identifier: true });
  }
  if (entries.length === 0) {
    return <span className="muted">Evidence reference recorded without display details.</span>;
  }
  return (
    <dl className="field-grid">
      {entries.map((entry) => (
        <div className="field" key={entry.label}>
          <dt>{entry.label}</dt>
          <dd>
            {entry.identifier ? <Identifier value={entry.value} /> : entry.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
