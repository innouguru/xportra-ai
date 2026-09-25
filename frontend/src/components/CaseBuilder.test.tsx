import { describe, expect, it } from "vitest";
import { buildCases, newCaseDraft, newEvidenceRefDraft } from "./CaseBuilder";

describe("buildCases", () => {
  it("assembles wire-ready cases only from identified rows", () => {
    const drafts = [
      {
        ...newCaseDraft(),
        requirement_id: "req-1",
        requirement_text: "File form X.",
        applicability: "applicable",
        applicability_reason: "Matches.",
        assessment: "unknown",
        assessment_reason: "No evidence yet.",
        evidence: [
          {
            ...newEvidenceRefDraft(),
            evidence_id: "ev-1",
            evidence_type: "certificate",
            reference: "registry://x",
            status: "accepted",
          },
          { ...newEvidenceRefDraft() },
        ],
      },
      newCaseDraft(),
    ];
    const cases = buildCases("tenant-1", "case-1", drafts);
    expect(cases).toHaveLength(1);
    expect(cases[0]).toMatchObject({
      tenant_id: "tenant-1",
      requirement: { id: "req-1", requirement_text: "File form X." },
      applicability: { outcome: "applicable", reason: "Matches." },
      assessment: { outcome: "unknown", reason: "No evidence yet." },
      case_reference: "case-1",
    });
    const evidence = cases[0]["evidence"] as Array<Record<string, string>>;
    expect(evidence).toHaveLength(1);
    expect(evidence[0]["evidence_id"]).toBe("ev-1");
  });

  it("invents no identities, outcomes, or facts", () => {
    expect(buildCases("t", "c", [newCaseDraft()])).toEqual([]);
    expect(buildCases("t", "c", [])).toEqual([]);
  });
});
