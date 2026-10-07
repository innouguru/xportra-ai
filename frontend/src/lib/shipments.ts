import type { WorkflowRecord } from "../types/api";

/**
 * Device-local shipment registry.
 *
 * The backend keeps no shipment object and no session:
 * the client-held workflow record is the authoritative
 * process state. This registry only remembers which
 * shipments were started on this device, with the
 * human profile entered at creation, so the workspace
 * can show a Shipments list and human shipment identity.
 *
 * Everything here is presentation metadata. It is never
 * sent to the backend, never presented as a compliance
 * fact, and never mixed into applicability, assessment,
 * or reasoning inputs.
 */

export interface ShipmentProfile {
  product: string;
  origin: string;
  destination: string;
  quantity: string;
  unit: string;
  shipmentDate: string;
}

export interface ShipmentEntry {
  caseId: string;
  shipmentId: string | null;
  profile: ShipmentProfile;
  /**
   * Client-held workflow snapshot. Null for a
   * server-owned shipment with no workflow yet
   * (draft): the server is then the only source,
   * and resume binds through the existing start
   * endpoint rather than a snapshot.
   */
  record: WorkflowRecord | null;
}

const STORAGE_KEY = "xportra.shipments.v1";
const FORGOTTEN_KEY = "xportra.shipments.forgotten.v1";

export function emptyProfile(): ShipmentProfile {
  return {
    product: "",
    origin: "",
    destination: "",
    quantity: "",
    unit: "",
    shipmentDate: "",
  };
}

/** Human one-line identity; falls back to the short reference. */
export function shipmentDisplayName(
  entry: Pick<ShipmentEntry, "profile" | "shipmentId">,
): string {
  const { product, origin, destination } = entry.profile;
  if (product.trim() && origin.trim() && destination.trim()) {
    return `${product.trim()} · ${origin.trim()} → ${destination.trim()}`;
  }
  if (entry.shipmentId) {
    return `Shipment ${entry.shipmentId.slice(0, 8)}…`;
  }
  return "Unbound shipment";
}

function readEntries(): ShipmentEntry[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is ShipmentEntry =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as ShipmentEntry).caseId === "string" &&
        typeof (item as ShipmentEntry).record === "object" &&
        (item as ShipmentEntry).record !== null &&
        typeof (item as ShipmentEntry).profile === "object" &&
        (item as ShipmentEntry).profile !== null,
    );
  } catch {
    return [];
  }
}

function writeEntries(entries: ShipmentEntry[]): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Storage is a convenience; the in-memory workflow record
    // stays authoritative if persistence fails.
  }
}

/** All remembered shipments, most recently started first. */
export function listShipments(): ShipmentEntry[] {
  return readEntries();
}

/** Remember (or refresh) a shipment by case identity. */
export function rememberShipment(entry: ShipmentEntry): void {
  const rest = readEntries().filter((item) => item.caseId !== entry.caseId);
  writeEntries([entry, ...rest]);
}

/** Forget one shipment; the active workflow record is untouched. */
export function forgetShipment(caseId: string, shipmentId?: string | null): void {
  writeEntries(readEntries().filter((item) => item.caseId !== caseId));
  rememberForgotten(caseId);
  if (shipmentId) {
    rememberForgotten(shipmentId);
  }
}

function readForgotten(): string[] {
  try {
    const raw = sessionStorage.getItem(FORGOTTEN_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === "string");
  } catch {
    return [];
  }
}

function rememberForgotten(caseId: string): void {
  try {
    const known = readForgotten();
    if (!known.includes(caseId)) {
      sessionStorage.setItem(FORGOTTEN_KEY, JSON.stringify([...known, caseId]));
    }
  } catch {
    // Hiding is a convenience; a failed write only re-shows the row.
  }
}

/**
 * Device-hidden shipment identities.
 *
 * Forgetting is device-local hiding only — it never
 * deletes server data. The server list stays
 * authoritative; hidden rows are filtered client-side
 * after every server fetch.
 */
export function forgottenShipmentIds(): string[] {
  return readForgotten();
}

/** Whether an entry is hidden on this device (by case or shipment identity). */
export function isHiddenShipment(entry: Pick<ShipmentEntry, "caseId" | "shipmentId">): boolean {
  const hidden = readForgotten();
  if (hidden.includes(entry.caseId)) {
    return true;
  }
  return entry.shipmentId !== null && hidden.includes(entry.shipmentId);
}
