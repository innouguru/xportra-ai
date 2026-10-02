import type { AnalysisReport, WorkflowRecord } from "../../types/api";
import { isTerminalState } from "../../lib/workflow";
import { shipmentDisplayName, type ShipmentEntry } from "../../lib/shipments";
import type { StatusTone } from "../../primitives/status";

/**
 * Phase 10.8E workspace presentation mapping.
 *
 * Translates the client-held workflow record, the
 * device-local shipment profile, and the in-memory
 * analysis report (when its case matches) into
 * plain-English workspace content. No compliance
 * logic, no new domain behavior, no invented
 * facts: every label derives from stored fields.
 * Technical workflow states never reach the UI
 * (pinned by test). Fields the boundary does not
 * expose (timestamps, scores, ports, activity)
 * are omitted, never fabricated.
 */

export interface WorkspaceAction {
  label: string;
  destination: string;
}

export interface WorkspaceRequirement {
  id: string;
  requirementId: string;
  title: string;
  statusLabel: string;
  tone: StatusTone;
  explanation: string | null;
  missing: string[];
}

export type WorkspaceRequirements =
  | { kind: "findings"; items: WorkspaceRequirement[] }
  | { kind: "open-count"; count: number }
  | { kind: "none" };

export interface WorkspaceModel {
  title: string;
  statusLabel: string;
  statusTone: StatusTone;
  briefing: string;
  briefingDetail: string | null;
  primaryAction: WorkspaceAction | null;
  readOnly: boolean;
  ready: boolean;
  details: { label: string; value: string | null }[];
  requirements: WorkspaceRequirements;
  progress: { addressed: number; total: number } | null;
  suppliedCount: number;
}

const TECHNICAL_STATES = [
  "created",
  "information_provided",
  "evidence_pending",
  "applicability_determined",
  "analysis_available",
  "review_required",
  "additional_evidence_requested",
  "reanalysis_required",
  "assessment_package_ready",
];

/** Guard for tests: no raw workflow state may leak into user text. */
export function containsTechnicalState(text: string): boolean {
  return TECHNICAL_STATES.some((state) => text.includes(state));
}

/** Approved user-facing words for one recorded assessment. */
export function requirementVocabulary(assessment: string): { label: string; tone: StatusTone } {
  switch (assessment) {
    case "satisfied":
      return { label: "Addressed", tone: "success" };
    case "not_satisfied":
      return { label: "Needs attention", tone: "warning" };
    case "unknown":
      return { label: "Still checking", tone: "info" };
    default:
      return { label: "Waiting for you", tone: "neutral" };
  }
}

function vocabulary(assessment: string): { label: string; tone: StatusTone } {
  return requirementVocabulary(assessment);
}

function lastReportId(record: WorkflowRecord): string | null {
  if (record.rounds.length === 0) {
    return null;
  }
  const last = record.rounds[record.rounds.length - 1];
  return last.report_id ? last.report_id : null;
}

/** Findings count as needing attention unless satisfied. */
function findingsNeedingAttention(report: AnalysisReport): number {
  return report.findings.filter((finding) => finding.assessment !== "satisfied").length;
}

function primaryActionFor(record: WorkflowRecord, caseId: string): WorkspaceAction | null {
  if (isTerminalState(record.state)) {
    const reportId = lastReportId(record);
    return reportId ? { label: "View report", destination: `/shipments/${caseId}/report` } : null;
  }
  switch (record.state) {
    case "created":
    case "information_provided":
      return { label: "Continue shipment", destination: "/workspace/info" };
    case "evidence_pending":
    case "additional_evidence_requested":
      return { label: "Upload document", destination: "/workspace/evidence" };
    case "applicability_determined":
      return { label: "Review requirements", destination: "/workspace/requirements" };
    case "analysis_available":
    case "review_required":
      return { label: "Review findings", destination: "/workspace/review" };
    case "reanalysis_required":
      return { label: "Open analysis", destination: "/workspace/analysis" };
    default:
      return { label: "Continue shipment", destination: "/workspace" };
  }
}

function briefingFor(
  record: WorkflowRecord,
  report: AnalysisReport | null,
): { message: string; detail: string | null; attention: boolean } {
  if (isTerminalState(record.state)) {
    return {
      message: "Everything Xportra could check is complete.",
      detail: "This shipment is a historical record and stays read-only.",
      attention: false,
    };
  }
  if (report && findingsNeedingAttention(report) > 0 && (record.state === "review_required" || record.state === "analysis_available")) {
    const count = findingsNeedingAttention(report);
    return {
      message:
        count === 1 ? "One requirement needs your attention." : `${count} requirements need your attention.`,
      detail: null,
      attention: true,
    };
  }
  if (
    record.state === "additional_evidence_requested" ||
    (record.state === "evidence_pending" && record.supplied_evidence_ids.length === 0)
  ) {
    return { message: "Xportra needs a document from you.", detail: null, attention: true };
  }
  if (record.state === "reanalysis_required") {
    return {
      message: "Analysis needs a re-run.",
      detail: "Re-running analysis is your decision — it never happens automatically.",
      attention: true,
    };
  }
  if (record.state === "created" || record.state === "information_provided") {
    return {
      message: "This shipment is just getting started.",
      detail: "Continue where you left off to establish what it needs.",
      attention: true,
    };
  }
  return { message: "We’re still checking this shipment.", detail: null, attention: false };
}

/**
 * Describe the workspace for one workflow record.
 * The report is honored only when its case matches
 * the record — never cross-shipment leakage.
 */
export function describeWorkspace(
  record: WorkflowRecord,
  entry: ShipmentEntry | null,
  report: AnalysisReport | null,
): WorkspaceModel {
  const matchedReport = report && report.case_id === record.case_id ? report : null;
  const title = entry ? shipmentDisplayName(entry) : "Shipment workspace";
  const closed = isTerminalState(record.state);
  const briefing = briefingFor(record, matchedReport);

  const details = entry
    ? [
        { label: "Product", value: entry.profile.product.trim() || null },
        { label: "Origin", value: entry.profile.origin.trim() || null },
        { label: "Destination", value: entry.profile.destination.trim() || null },
        { label: "Quantity", value: entry.profile.quantity.trim() || null },
        { label: "Unit", value: entry.profile.unit.trim() || null },
        { label: "Shipment date", value: entry.profile.shipmentDate.trim() || null },
      ]
    : [];

  let requirements: WorkspaceRequirements;
  let progress: WorkspaceModel["progress"];
  if (matchedReport && matchedReport.findings.length > 0) {
    const items = matchedReport.findings.map((finding) => {
      const words = vocabulary(finding.assessment);
      return {
        id: finding.analysis_id || finding.requirement_id,
        requirementId: finding.requirement_id,
        title: finding.requirement_text || "Requirement",
        statusLabel: words.label,
        tone: words.tone,
        explanation: finding.explanation.trim() || null,
        missing: finding.missing_information.filter((item) => item.trim().length > 0),
      };
    });
    requirements = { kind: "findings", items };
    const addressed = items.filter((item) => item.statusLabel === "Addressed").length;
    progress = { addressed, total: items.length };
  } else if (record.open_requirements.length > 0) {
    requirements = { kind: "open-count", count: record.open_requirements.length };
    progress = null;
  } else {
    requirements = { kind: "none" };
    progress = null;
  }

  return {
    title,
    statusLabel: closed ? "Ready" : briefing.attention ? "Needs attention" : "In progress",
    statusTone: closed ? "success" : briefing.attention ? "warning" : "info",
    briefing: briefing.message,
    briefingDetail: briefing.detail,
    primaryAction: primaryActionFor(record, record.case_id),
    readOnly: closed,
    ready: closed,
    details,
    requirements,
    progress,
    suppliedCount: record.supplied_evidence_ids.length,
  };
}
