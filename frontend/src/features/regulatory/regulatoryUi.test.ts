import { describe, expect, it } from "vitest";
import type {
  RegulatoryArtifact,
  RegulatoryCandidate,
  RegulatoryIngestionJob,
  RegulatorySource,
} from "../../api/regulatory";
import {
  candidatePath,
  deriveSourceProgress,
  documentJobs,
  sourcePath,
} from "./regulatoryUi";

const SOURCE = { id: "s1", status: "draft" } as RegulatorySource;
const ARTIFACT = { id: "a1" } as RegulatoryArtifact;
const CANDIDATE = { id: "c1" } as RegulatoryCandidate;

function job(overrides: Partial<RegulatoryIngestionJob>): RegulatoryIngestionJob {
  return {
    id: "j",
    artifact_id: "a1",
    source_id: "s1",
    status: "completed",
    attempt_number: 1,
    ...overrides,
  } as RegulatoryIngestionJob;
}

function progress(parts: {
  source?: RegulatorySource;
  artifacts?: RegulatoryArtifact[];
  jobs?: RegulatoryIngestionJob[];
  candidates?: RegulatoryCandidate[];
}) {
  return deriveSourceProgress({
    source: parts.source ?? SOURCE,
    artifacts: parts.artifacts ?? [],
    jobs: parts.jobs ?? [],
    candidates: parts.candidates ?? [],
  });
}

const stepState = (p: ReturnType<typeof progress>, key: string) =>
  p.steps.find((step) => step.key === key)?.state;

describe("deriveSourceProgress", () => {
  it("asks for the first document right after registration", () => {
    const p = progress({});
    expect(stepState(p, "registered")).toBe("done");
    expect(stepState(p, "document")).toBe("current");
    expect(stepState(p, "extraction")).toBe("upcoming");
    expect(p.next.tab).toBe("documents");
    expect(p.inFlight).toBe(false);
  });

  it("ignores the registration placeholder job (no artifact)", () => {
    const placeholder = job({ id: "p", artifact_id: null, status: "pending" });
    expect(documentJobs([placeholder])).toEqual([]);
    const p = progress({ jobs: [placeholder] });
    expect(p.inFlight).toBe(false);
    expect(p.next.tab).toBe("documents");
  });

  it("reports a running job and polls while it is in flight", () => {
    for (const status of ["pending", "claimed", "processing", "retryable"]) {
      const p = progress({ artifacts: [ARTIFACT], jobs: [job({ status })] });
      expect(stepState(p, "extraction")).toBe("current");
      expect(p.inFlight).toBe(true);
      expect(p.next.kind).toBe("waiting");
    }
  });

  it("flags a failed latest attempt and points at ingestion", () => {
    const p = progress({ artifacts: [ARTIFACT], jobs: [job({ status: "failed" })] });
    expect(stepState(p, "extraction")).toBe("attention");
    expect(p.next.kind).toBe("attention");
    expect(p.next.tab).toBe("ingestion");
    expect(p.inFlight).toBe(false);
  });

  it("judges each document by its most recent attempt, so a good retry clears a failure", () => {
    const p = progress({
      artifacts: [ARTIFACT],
      jobs: [
        job({ id: "1", attempt_number: 1, status: "failed" }),
        job({ id: "2", attempt_number: 2, status: "completed" }),
      ],
    });
    expect(stepState(p, "extraction")).toBe("done");
  });

  it("moves to review once candidates exist, without claiming review is finished", () => {
    const p = progress({
      artifacts: [ARTIFACT],
      jobs: [job({ status: "completed" })],
      candidates: [CANDIDATE, { ...CANDIDATE, id: "c2" }],
    });
    expect(stepState(p, "review")).toBe("current");
    expect(p.steps.find((s) => s.key === "review")?.detail).toBe("2 candidates to review");
    expect(p.next.tab).toBe("candidates");
    expect(p.next.title).toBe("Next: review 2 candidates");
  });

  it("says plainly when extraction produced no candidates", () => {
    const p = progress({ artifacts: [ARTIFACT], jobs: [job({ status: "completed" })] });
    expect(stepState(p, "review")).toBe("upcoming");
    expect(p.next.title).toBe("No candidates were extracted");
  });

  it("offers no further actions for a withdrawn or archived source", () => {
    for (const status of ["withdrawn", "archived"]) {
      const p = progress({
        source: { ...SOURCE, status } as RegulatorySource,
        artifacts: [ARTIFACT],
        jobs: [job({ status: "completed" })],
        candidates: [CANDIDATE],
      });
      expect(p.next.title).toBe(`This source is ${status}`);
      expect(p.next.tab).toBe("details");
    }
  });

  it("never presents publication or exporter applicability", () => {
    const cases = [
      progress({}),
      progress({ artifacts: [ARTIFACT], jobs: [job({ status: "failed" })] }),
      progress({ artifacts: [ARTIFACT], jobs: [job({ status: "pending" })] }),
      progress({ artifacts: [ARTIFACT], jobs: [job({})], candidates: [CANDIDATE] }),
    ];
    for (const p of cases) {
      const text = JSON.stringify([p.steps, p.next]);
      expect(text).not.toMatch(/publi/i);
      expect(text).not.toMatch(/applicab/i);
    }
  });
});

describe("route builders", () => {
  it("encodes identifiers and targets the canonical staff routes", () => {
    expect(sourcePath("a b")).toBe("/regulatory/a%20b/documents");
    expect(sourcePath("s1", "ingestion")).toBe("/regulatory/s1/ingestion");
    expect(candidatePath("s1", "c1")).toBe("/regulatory/s1/candidates/c1");
  });
});
