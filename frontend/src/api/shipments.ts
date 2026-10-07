import { ApiError, apiFetch, type AuthCredentials } from "./client";
import type { WorkflowRecord } from "../types/api";
import {
  isHiddenShipment,
  rememberShipment,
  type ShipmentEntry,
  type ShipmentProfile,
} from "../lib/shipments";

/**
 * Typed shipment-discovery endpoints.
 *
 * Read-only views over server-owned rows: shipment
 * facts plus the latest workflow progress per
 * shipment. No compliance logic lives here:
 * functions transport the composed items and
 * surface backend errors unchanged.
 *
 * Covered routes (both GET):
 * - /compliance/shipments (paginated, newest first)
 * - /compliance/shipments/{shipment_id}
 */

export interface ServerShipmentWorkflow {
  workflow_id: string;
  state: string;
  is_closed: boolean;
  supplied_evidence_count: number;
  open_requirements_count: number;
  round_count: number;
  latest_report_id: string | null;
}

export interface ServerShipmentItem {
  shipment_id: string;
  case_id: string;
  product: string;
  origin_country: string;
  destination_country: string;
  quantity: string | null;
  unit: string | null;
  shipment_date: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  workflow: ServerShipmentWorkflow | null;
  workflow_count: number;
  workflow_record: WorkflowRecord | null;
}

export interface ServerShipmentList {
  shipments: ServerShipmentItem[];
  limit: number;
  offset: number;
  total: number;
}

export interface FetchShipmentListInput {
  limit?: number;
  offset?: number;
  status?: "all" | "active" | "completed";
}

/**
 * Discovery window for history surfaces.
 *
 * Dashboard, archive, workspace, and report reads
 * resolve entries by identity from the fetched page,
 * so they read a bounded full window (not the
 * default first page) until paged archive UI exists.
 */
export const DISCOVERY_PAGE_SIZE = 100;

/**
 * Adapt one server item into the existing UI model.
 *
 * Profiles map onto the intake field names the UI
 * already renders; the workflow snapshot passes
 * through untouched (null for drafts). No fact is
 * invented: a missing workflow stays missing.
 */
export function toShipmentEntry(item: ServerShipmentItem): ShipmentEntry {
  const profile: ShipmentProfile = {
    product: item.product,
    origin: item.origin_country,
    destination: item.destination_country,
    quantity: item.quantity ?? "",
    unit: item.unit ?? "",
    shipmentDate: item.shipment_date ?? "",
  };
  return {
    caseId: item.case_id,
    shipmentId: item.shipment_id,
    profile,
    record: item.workflow_record,
  };
}

function listQuery(input: FetchShipmentListInput): string {
  const params = new URLSearchParams();
  if (input.limit !== undefined) {
    params.set("limit", String(input.limit));
  }
  if (input.offset !== undefined) {
    params.set("offset", String(input.offset));
  }
  if (input.status !== undefined) {
    params.set("status", input.status);
  }
  const query = params.toString();
  return query ? `/compliance/shipments?${query}` : "/compliance/shipments";
}

/**
 * Fetch durable shipments and refresh the device cache.
 *
 * The server list is authoritative: cached entries
 * are overwritten by case identity (server wins on
 * conflict) and device-hidden rows stay hidden. The
 * registry remains as UI cache, mutation continuity,
 * and suggestion source — never as history truth.
 */
export async function fetchShipmentList(
  credentials: AuthCredentials,
  input: FetchShipmentListInput = {},
): Promise<ShipmentEntry[]> {
  const page = await apiFetch<ServerShipmentList>(listQuery(input), credentials);
  const entries = page.shipments.map(toShipmentEntry);
  for (const entry of entries) {
    rememberShipment(entry);
  }
  return entries.filter((entry) => !isHiddenShipment(entry));
}

/**
 * Fetch one durable shipment by server identity.
 *
 * Returns null when the backend reports not-found
 * (unknown or cross-tenant identity); other failures
 * propagate to the caller's error state.
 */
export async function fetchShipmentDetail(
  credentials: AuthCredentials,
  shipmentId: string,
): Promise<ShipmentEntry | null> {
  try {
    const item = await apiFetch<ServerShipmentItem>(
      `/compliance/shipments/${encodeURIComponent(shipmentId)}`,
      credentials,
    );
    const entry = toShipmentEntry(item);
    rememberShipment(entry);
    return isHiddenShipment(entry) ? null : entry;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}
