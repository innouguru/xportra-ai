import type {
  RegulatoryArtifact,
  RegulatoryCandidate,
  RegulatoryIngestionJob,
  RegulatorySource,
} from "../../api/regulatory";

/** Canonical mount point of the staff regulatory surface. */
export const REGULATORY_BASE = "/regulatory";

export type SourceTab =
  | "documents"
  | "ingestion"
  | "candidates"
  | "governance"
  | "details";

export function sourcePath(sourceId: string, tab: SourceTab = "documents"): string {
  return `${REGULATORY_BASE}/${encodeURIComponent(sourceId)}/${tab}`;
}

export function candidatePath(sourceId: string, candidateId: string): string {
  return `${REGULATORY_BASE}/${encodeURIComponent(sourceId)}/candidates/${encodeURIComponent(candidateId)}`;
}

export function createdAt(value: string | null | undefined): string {
  return value ?? "—";
}

export function tone(value: string): "info" | "muted" | "attention" | "neutral" {
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

// ---------------------------------------------------------------------------
// Progress derivation
//
// Everything below is computed ONLY from rows the backend has already
// recorded (artifacts, ingestion jobs, candidates). Nothing is inferred:
// per-candidate Stage A / Stage B outcomes are not part of the candidate
// list response, so the "Review" step reports a count and never claims
// completion. No step represents publication or exporter applicability.
// ---------------------------------------------------------------------------

/** Job statuses that mean the worker has not finished with the job yet. */
const IN_FLIGHT_JOB_STATUSES = new Set(["pending", "claimed", "processing", "retryable"]);

export type StepState = "done" | "current" | "upcoming" | "attention";

export interface ProgressStep {
  key: "registered" | "document" | "extraction" | "review";
  label: string;
  state: StepState;
  detail: string;
}

export interface NextAction {
  kind: "action" | "waiting" | "attention" | "info";
  title: string;
  body: string;
  tab: SourceTab;
  cta: string;
}

export interface SourceProgressData {
  source: RegulatorySource;
  artifacts: RegulatoryArtifact[];
  jobs: RegulatoryIngestionJob[];
  candidates: RegulatoryCandidate[];
}

export interface SourceProgress {
  steps: ProgressStep[];
  next: NextAction;
  /** True while any document ingestion job is still pending or running. */
  inFlight: boolean;
}

/**
 * Jobs that belong to an uploaded document. Registration records a job
 * with no artifact; it is not an ingestion attempt and is excluded here.
 */
export function documentJobs(jobs: RegulatoryIngestionJob[]): RegulatoryIngestionJob[] {
  return jobs.filter((job) => job.artifact_id !== null);
}

/** The most recent attempt per artifact (highest attempt number). */
function latestAttempts(jobs: RegulatoryIngestionJob[]): RegulatoryIngestionJob[] {
  const latest = new Map<string, RegulatoryIngestionJob>();
  for (const job of documentJobs(jobs)) {
    const key = job.artifact_id as string;
    const current = latest.get(key);
    if (!current || job.attempt_number > current.attempt_number) {
      latest.set(key, job);
    }
  }
  return [...latest.values()];
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function deriveSourceProgress(data: SourceProgressData): SourceProgress {
  const { source, artifacts, jobs, candidates } = data;
  const attempts = latestAttempts(jobs);
  const failed = attempts.filter((job) => job.status === "failed");
  const running = attempts.filter((job) => IN_FLIGHT_JOB_STATUSES.has(job.status));
  const completed = attempts.filter((job) => job.status === "completed");
  const hasDocument = artifacts.length > 0;
  const closed = source.status === "withdrawn" || source.status === "archived";

  let extraction: ProgressStep;
  if (!hasDocument) {
    extraction = {
      key: "extraction",
      label: "Extraction",
      state: "upcoming",
      detail: "Starts after a document is uploaded",
    };
  } else if (failed.length > 0) {
    extraction = {
      key: "extraction",
      label: "Extraction",
      state: "attention",
      detail: `${plural(failed.length, "job", "jobs")} failed`,
    };
  } else if (running.length > 0) {
    extraction = {
      key: "extraction",
      label: "Extraction",
      state: "current",
      detail: "In progress",
    };
  } else if (attempts.length > 0 && completed.length === attempts.length) {
    extraction = {
      key: "extraction",
      label: "Extraction",
      state: "done",
      detail: "Completed",
    };
  } else {
    extraction = {
      key: "extraction",
      label: "Extraction",
      state: "current",
      detail: "No ingestion job recorded yet",
    };
  }

  const steps: ProgressStep[] = [
    {
      key: "registered",
      label: "Registered",
      state: "done",
      detail: `Status: ${source.status}`,
    },
    {
      key: "document",
      label: "Document",
      state: hasDocument ? "done" : "current",
      detail: hasDocument ? `${plural(artifacts.length, "file", "files")} uploaded` : "Not uploaded yet",
    },
    extraction,
    {
      key: "review",
      label: "Review",
      state: candidates.length > 0 ? "current" : "upcoming",
      detail:
        candidates.length > 0
          ? `${plural(candidates.length, "candidate", "candidates")} to review`
          : "No candidates yet",
    },
  ];

  let next: NextAction;
  if (closed) {
    next = {
      kind: "info",
      title: `This source is ${source.status}`,
      body: "No further ingestion or review actions are offered for it. Recorded history stays visible.",
      tab: "details",
      cta: "View details",
    };
  } else if (!hasDocument) {
    next = {
      kind: "action",
      title: "Next: upload the original document",
      body: "Ingestion starts once a document is attached to this source.",
      tab: "documents",
      cta: "Upload document",
    };
  } else if (failed.length > 0) {
    next = {
      kind: "attention",
      title: "Ingestion failed",
      body: "Review the recorded failure details, then retry the failed job.",
      tab: "ingestion",
      cta: "Open ingestion",
    };
  } else if (running.length > 0) {
    next = {
      kind: "waiting",
      title: "Ingestion is running",
      body: "This page refreshes by itself while a job is pending or running.",
      tab: "ingestion",
      cta: "Watch ingestion",
    };
  } else if (candidates.length > 0) {
    next = {
      kind: "action",
      title: `Next: review ${plural(candidates.length, "candidate", "candidates")}`,
      body: "Open each candidate to record its Stage A verification and Stage B decision.",
      tab: "candidates",
      cta: "Review candidates",
    };
  } else {
    next = {
      kind: "info",
      title: "No candidates were extracted",
      body: "Check the ingestion record for this document to see how extraction ended.",
      tab: "ingestion",
      cta: "Open ingestion",
    };
  }

  return { steps, next, inFlight: running.length > 0 };
}
