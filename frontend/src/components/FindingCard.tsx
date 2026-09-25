import type { AnalysisFinding } from "../types/api";
import { applicabilityTone } from "../lib/workflow";
import { contradictionTone } from "../lib/evidence";
import { assessmentTone, stateQualifier, uncertaintyTone } from "../lib/findings";
import { Collapsible, Field, Identifier, StatusBadge } from "./StatusBits";

/**
 * One analysis finding, structured exactly like the
 * backend DTO: requirement, applicability, assessment,
 * explanation, evidence, sufficiency, missing
 * information, sources, uncertainty. Contradictions are
 * displayed, never resolved. No scores, no verdicts,
 * no numeric confidence exists anywhere here.
 */
export function FindingCard({
  finding,
  index,
  total,
}: {
  finding: AnalysisFinding;
  /** Zero-based position in the report; renders "Finding N of M" when both are given. */
  index?: number;
  total?: number;
}) {
  const assessmentNote = stateQualifier("assessment", finding.assessment);
  const sufficiencyNote = stateQualifier("sufficiency", finding.evidence_sufficiency);

  return (
    <article className="finding-card" aria-label={`Finding for ${finding.requirement_id}`}>
      {index !== undefined && total !== undefined ? (
        <p className="finding-count">
          Finding {index + 1} of {total}
        </p>
      ) : null}
      <p className="finding-kicker">Requirement</p>
      <h3 className="finding-requirement">{finding.requirement_text}</h3>
      <dl className="field-grid finding-meta">
        <Field label="Requirement ID">
          <Identifier value={finding.requirement_id} short={36} />
        </Field>
        <Field label="Applicability">
          <StatusBadge value={finding.applicability} tone={applicabilityTone(finding.applicability)} />
        </Field>
        <Field label="Assessment">
          <StatusBadge value={finding.assessment} tone={assessmentTone(finding.assessment)} />
          {assessmentNote ? <span className="muted"> — {assessmentNote}</span> : null}
        </Field>
        <Field label="Evidence sufficiency">
          <StatusBadge value={finding.evidence_sufficiency} tone="neutral" />
          {sufficiencyNote ? <span className="muted"> — {sufficiencyNote}</span> : null}
        </Field>
        <Field label="Contradiction">
          <StatusBadge
            value={finding.contradiction_state}
            tone={contradictionTone(finding.contradiction_state)}
          />
        </Field>
        <Field label="Uncertainty">
          <StatusBadge value={finding.uncertainty} tone={uncertaintyTone(finding.uncertainty)} />
        </Field>
      </dl>
      <section className="finding-section" aria-label="Explanation">
        <h4>Explanation</h4>
        <p>{finding.explanation}</p>
        {finding.uncertainty_explanation ? <p className="muted">{finding.uncertainty_explanation}</p> : null}
        {finding.sufficiency_explanation ? <p className="muted">{finding.sufficiency_explanation}</p> : null}
      </section>
      <section className="finding-section" aria-label="Evidence">
        <h4>Evidence</h4>
        {finding.supporting_evidence.length === 0 && finding.conflicting_evidence.length === 0 ? (
          <p className="muted">No evidence references recorded for this finding.</p>
        ) : (
          <>
            {finding.supporting_evidence.length > 0 ? (
              <>
                <h5>Supporting</h5>
                <ul className="reference-list">
                  {finding.supporting_evidence.map((item, index) => (
                    <li key={`supporting-${index}`}>
                      <EvidenceReferenceView reference={item} />
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {finding.conflicting_evidence.length > 0 ? (
              <>
                <h5>Conflicting — shown as recorded, not resolved</h5>
                <ul className="reference-list">
                  {finding.conflicting_evidence.map((item, index) => (
                    <li key={`conflicting-${index}`}>
                      <EvidenceReferenceView reference={item} />
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
      <Collapsible title={`Sources and provenance (${finding.sources.length})`}>
        {finding.sources.length === 0 ? (
          <p className="muted">No sources recorded.</p>
        ) : (
          <ul className="reference-list">
              {finding.sources.map((source, index) => (
                <li key={`source-${index}`}>
                <code className="identifier">{JSON.stringify(source)}</code>
              </li>
            ))}
          </ul>
        )}
        {finding.knowledge_references.length > 0 ? (
          <>
            <h5>Knowledge references</h5>
            <ul className="reference-list">
              {finding.knowledge_references.map((reference, index) => (
                <li key={`knowledge-${index}`}>
                  <code className="identifier">{JSON.stringify(reference)}</code>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </Collapsible>
    </article>
  );
}

function EvidenceReferenceView({ reference }: { reference: Record<string, unknown> }) {
  const entries = Object.entries(reference);
  if (entries.length === 0) {
    return <span className="muted">Empty reference</span>;
  }
  return (
    <dl className="field-grid">
      {entries.map(([key, value]) => (
        <div className="field" key={key}>
          <dt>{key.replace(/_/g, " ")}</dt>
          <dd>
            {typeof value === "string" && value.length > 60 ? (
              <Identifier value={value} />
            ) : (
              <span>{String(value ?? "")}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
