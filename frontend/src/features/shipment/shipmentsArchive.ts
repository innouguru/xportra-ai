import { describeShipment, type DashboardShipment } from "../dashboard/dashboard";
import type { ShipmentEntry } from "../../lib/shipments";

/**
 * Archive presentation mapping (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * Local search/filter/sort over the existing
 * device-local registry (the only shipment
 * source the architecture provides). Search
 * covers stored profile text and display
 * identity only — no semantic claims. Filters
 * are the four reference states (All / Active /
 * Incomplete / Completed): incomplete means the
 * shipment is still in intake (`created`,
 * `information_provided`); active means
 * anything else still in progress. Ordering is
 * stable: active, then incomplete, then
 * completed.
 */

export type ArchiveStatus = "all" | "active" | "incomplete" | "completed";

export interface ArchiveFilter {
  query: string;
  status: ArchiveStatus;
  product: string;
  destination: string;
  date: string;
}

export const EMPTY_FILTER: ArchiveFilter = {
  query: "",
  status: "all",
  product: "",
  destination: "",
  date: "",
};

function haystack(entry: ShipmentEntry, title: string): string {
  return [
    title,
    entry.profile.product,
    entry.profile.origin,
    entry.profile.destination,
    entry.caseId,
    entry.shipmentId ?? "",
  ]
    .join(" ")
    .toLowerCase();
}

function statusGroup(item: DashboardShipment): "active" | "incomplete" | "completed" {
  if (item.complete) {
    return "completed";
  }
  const state = item.entry.record?.state;
  if (state === undefined || state === "created" || state === "information_provided") {
    return "incomplete";
  }
  return "active";
}

/** Describe, filter, and stably order registry entries. */
export function queryArchive(entries: ShipmentEntry[], filter: ArchiveFilter): DashboardShipment[] {
  const query = filter.query.trim().toLowerCase();
  const described = entries.map(describeShipment);
  const rank = { active: 0, incomplete: 1, completed: 2 } as const;
  return described
    .filter((item) => {
      if (query && !haystack(item.entry, item.title).includes(query)) {
        return false;
      }
      if (filter.status !== "all" && statusGroup(item) !== filter.status) {
        return false;
      }
      if (filter.product && item.entry.profile.product.trim() !== filter.product) {
        return false;
      }
      if (filter.destination && item.entry.profile.destination.trim() !== filter.destination) {
        return false;
      }
      if (filter.date && item.entry.profile.shipmentDate.trim() !== filter.date) {
        return false;
      }
      return true;
    })
    .sort((a, b) => rank[statusGroup(a)] - rank[statusGroup(b)]);
}

/** Distinct non-empty values for one profile field. */
export function distinctProfileValues(
  entries: ShipmentEntry[],
  pick: (entry: ShipmentEntry) => string,
): string[] {
  const seen = new Set<string>();
  for (const entry of entries) {
    const value = pick(entry).trim();
    if (value) {
      seen.add(value);
    }
  }
  return [...seen].sort((a, b) => a.localeCompare(b));
}

/** Whether any entry carries a shipment date (gates the date filter/column). */
export function hasShipmentDates(entries: ShipmentEntry[]): boolean {
  return entries.some((entry) => entry.profile.shipmentDate.trim().length > 0);
}
