import { describe, expect, it } from "vitest";
import {
  findFindingForRequirement,
  missingLines,
  previewKind,
  unverifiedVerdict,
  verdictForAssessment,
} from "./verification";
import type { AnalysisFinding, AnalysisReport } from "../../types/api";

function finding(assessment: string, requirementId = "r1"): AnalysisFinding {
  return {
    analysis_id: "a1",
    requirement_id: requirementId,
    requirement_text: "Phytosanitary certificate",
    applicability: "applicable",
    assessment,
    explanation: "The certificate was reviewed.",
    uncertainty: "determined",
    uncertainty_explanation: "",
    evidence_sufficiency: "insufficient",
    sufficiency_explanation: "",
    contradiction_state: "none",
    missing_information: ["  ", "Upload the certificate."],
    supporting_evidence: [],
    conflicting_evidence: [],
    knowledge_references: [],
    sources: [],
    missing_items: [],
  };
}

function report(findings: AnalysisFinding[]): AnalysisReport {
  return {
    report_id: "rep-1",
    case_id: "case-1",
    counts: {},
    requirements_with_missing_information: [],
    uncertain_requirement_ids: [],
    requirements_with_conflicting_evidence: [],
    conflicting_evidence_count: 0,
    findings,
  };
}

describe("verification verdicts", () => {
  it("maps recorded assessments to user-facing verdicts", () => {
    expect(verdictForAssessment("satisfied").label).toBe("Satisfied");
    expect(verdictForAssessment("not_satisfied").label).toBe("Not satisfied");
    expect(verdictForAssessment("unknown").label).toBe("Unknown");
    expect(verdictForAssessment("something_new").label).toBe("Unknown");
  });

  it("never presents unknown as failure", () => {
    const verdict = verdictForAssessment("unknown");
    expect(verdict.explanation).toMatch(/could not determine/i);
    expect(verdict.explanation).not.toMatch(/fail|non-compliant|invalid/i);
  });

  it("treats missing findings as unverified, never satisfied", () => {
    expect(findFindingForRequirement(null, "r1")).toBeNull();
    expect(findFindingForRequirement(report([finding("satisfied", "r9")]), "r1")).toBeNull();
    const verdict = unverifiedVerdict();
    expect(verdict.state).toBe("unknown");
    expect(verdict.explanation).toMatch(/not been analyzed/i);
  });

  it("selects the latest finding per requirement", () => {
    const found = findFindingForRequirement(
      report([finding("unknown", "r1"), finding("satisfied", "r1")]),
      "r1",
    );
    expect(found?.assessment).toBe("satisfied");
  });

  it("keeps only real missing-information lines", () => {
    expect(missingLines(finding("unknown"))).toEqual(["Upload the certificate."]);
  });

  it("supports inline preview for PDF and images only", () => {
    expect(previewKind("application/pdf")).toBe("pdf");
    expect(previewKind("image/jpeg")).toBe("image");
    expect(previewKind("image/png")).toBe("image");
    expect(previewKind("application/vnd.openxmlformats-officedocument.wordprocessingml.document")).toBe(
      "unsupported",
    );
    expect(previewKind(null)).toBe("unsupported");
  });

  it("exposes no scores, reasons, or chain-of-thought", () => {
    const text = JSON.stringify([
      verdictForAssessment("satisfied"),
      verdictForAssessment("not_satisfied"),
      unverifiedVerdict(),
    ]);
    expect(text).not.toMatch(/score|percent|confidence|chain-of-thought|Run Compliance/i);
  });
});
