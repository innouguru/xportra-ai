import type { WorkflowRecord } from "../../types/api";
import { isTerminalState } from "../../lib/workflow";
import {
  listShipments,
  shipmentDisplayName,
  type ShipmentEntry,
} from "../../lib/shipments";

/**
 * Phase 10.8C dashboard presentation mapping.
 *
 * Translates the existing device-local shipment
 * registry (`lib/shipments`, most-recent-first)
 * and the existing backend process states
 * (`lib/workflow`) into plain-English dashboard
 * presentation. No compliance logic, no new
 * domain behavior, no invented backend facts:
 * every label derives from the entry's stored
 * profile, workflow state, supplied-evidence
 * count, and analysis-round count. Fields the
 * backend does not expose (timestamps, missing-
 * detail counts, scores) are omitted, never
 * fabricated.
 */

export type DashboardTone = "success" | "warning" | "danger" | "info" | "neutral";

export interface DashboardAction {
  label: string;
  destination: string;
}

export interface DashboardShipment {
  entry: ShipmentEntry;
  title: string;
  meta: string | null;
  tone: DashboardTone;
  statusLabel: string;
  /** Present when the shipment needs user action. */
  attention: string | null;
  action: DashboardAction;
  complete: boolean;
}

/** Time-appropriate greeting from the local hour. */
export function greetingForHour(hour: number): string {
  if (hour < 12) {
    return "Good morning";
  }
  if (hour < 18) {
    return "Good afternoon";
  }
  return "Good evening";
}

function profileMeta(entry: ShipmentEntry): string | null {
  const parts = [
    [entry.profile.quantity.trim(), entry.profile.unit.trim()].filter(Boolean).join(" ") || null,
    entry.profile.shipmentDate.trim() || null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

/**
 * Present one registry entry as dashboard content.
 * Attention membership follows existing process
 * semantics: early/incomplete states, explicit
 * evidence or review requests, and available
 * findings awaiting review. Terminal records are
 * complete history, never attention.
 */
export function describeShipment(entry: ShipmentEntry): DashboardShipment {
  const { record } = entry;
  // Entry-level opens land on the Phase 10.8E shipment workspace;
  // deep-link actions below keep their existing workflow routes.
  const workspace = `/shipments/${entry.caseId}`;
  const title = shipmentDisplayName(entry);
  const meta = profileMeta(entry);
  const base = { entry, title, meta };

  if (isTerminalState(record.state)) {
    return {
      ...base,
      tone: "success",
      statusLabel: "Completed",
      attention: null,
      // Completed shipments always open the read-only historical
      // report — even without recorded rounds, the profile and
      // evidence sections still render honestly.
      action: { label: "View report", destination: `/shipments/${entry.caseId}/report` },
      complete: true,
    };
  }

  switch (record.state) {
    case "created":
    case "information_provided":
      return {
        ...base,
        tone: "warning",
        statusLabel: "Incomplete",
        attention: "Incomplete — continue where you left off",
        action: { label: "Continue", destination: workspace },
        complete: false,
      };
    case "evidence_pending":
      if (record.supplied_evidence_ids.length === 0) {
        return {
          ...base,
          tone: "warning",
          statusLabel: "Waiting for you",
          attention: "Document needed — upload your first document",
          action: { label: "Upload document", destination: "/workspace/evidence" },
          complete: false,
        };
      }
      return {
        ...base,
        tone: "info",
        statusLabel: "Still checking",
        attention: null,
        action: { label: "Continue", destination: workspace },
        complete: false,
      };
    case "additional_evidence_requested":
      return {
        ...base,
        tone: "warning",
        statusLabel: "Needs attention",
        attention: "Document needed — more evidence was requested",
        action: { label: "Upload document", destination: "/workspace/evidence" },
        complete: false,
      };
    case "analysis_available":
    case "review_required":
      return {
        ...base,
        tone: "warning",
        statusLabel: "Needs attention",
        attention: "Review needed — findings are ready",
        action: { label: "Review", destination: "/workspace/review" },
        complete: false,
      };
    case "reanalysis_required":
      return {
        ...base,
        tone: "warning",
        statusLabel: "Needs attention",
        attention: "Analysis needs a re-run",
        action: { label: "Open analysis", destination: "/workspace/analysis" },
        complete: false,
      };
    default:
      // Includes `applicability_determined` and any
      // future state: mid-process position rendered
      // honestly without inventing urgency.
      return {
        ...base,
        tone: "info",
        statusLabel: "Still checking",
        attention: null,
        action: { label: "Continue", destination: workspace },
        complete: false,
      };
  }
}

export interface DashboardModel {
  entries: DashboardShipment[];
  attention: DashboardShipment[];
  recent: DashboardShipment[];
  activeCount: number;
  attentionCount: number;
}

export const RECENT_LIMIT = 5;

/**
 * Partition described entries: actionable work
 * first, then up to three recent non-attention
 * shipments (no duplicates across sections).
 */
export function partitionDashboard(described: DashboardShipment[]): DashboardModel {
  const attention = described.filter((item) => item.attention !== null);
  const recent = described.filter((item) => item.attention === null).slice(0, RECENT_LIMIT);
  return {
    entries: described,
    attention,
    recent,
    activeCount: described.filter((item) => !item.complete).length,
    attentionCount: attention.length,
  };
}

export type DashboardLoad = { status: "ready"; model: DashboardModel } | { status: "error" };

/** Read the registry through the existing boundary. */
export function loadDashboard(): DashboardLoad {
  try {
    return { status: "ready", model: partitionDashboard(listShipments().map(describeShipment)) };
  } catch {
    return { status: "error" };
  }
}

/**
 * Open a shipment in the workspace: load its
 * record into the existing workflow context,
 * then navigate (mirrors the Shipments list
 * behavior; no new mechanism).
 */
export function openShipment(
  entry: ShipmentEntry,
  setRecord: (record: WorkflowRecord) => void,
  navigate: (path: string) => void,
  destination: string,
): void {
  setRecord(entry.record);
  navigate(destination);
}
