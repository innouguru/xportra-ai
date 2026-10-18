import type {
  OrganizationRegistrationInput,
  OrganizationType,
} from "../types/api";

/**
 * Pending organization registration (Phase 10.11).
 *
 * When a visitor registers, the organization profile they typed is
 * held briefly in `sessionStorage` until the magic-link email is
 * opened and the PKCE callback establishes a session. The callback
 * then posts the profile to `POST /organizations` with the fresh
 * bearer token, so the backend always derives identity from the
 * verified session — never from this client-side cache.
 *
 * Scope and safety:
 * - Session-scoped and same-tab only; cleared once finalized or on
 *   any invalid/absent shape.
 * - Holds organization profile fields plus the sign-up email only —
 *   no tokens, no tenant id, no user id, no role, no secrets.
 * - Every read re-validates the stored shape and returns `null` on
 *   anything unexpected, so a corrupted or stale value can never
 *   drive a registration request.
 */

const STORAGE_KEY = "xportra.pending-registration.v1";

const ORGANIZATION_TYPES: readonly OrganizationType[] = [
  "farmer",
  "cooperative",
  "exporter",
  "service_provider",
  "other",
];

export interface PendingRegistration {
  email: string;
  organizationName: string;
  organizationType: OrganizationType;
  countryCode: string;
  region: string | null;
  contactName: string | null;
}

function sessionStorageOrNull(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function savePendingRegistration(pending: PendingRegistration): void {
  const store = sessionStorageOrNull();
  if (store === null) {
    return;
  }
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(pending));
  } catch {
    // Storage unavailable or full: the callback simply skips
    // auto-finalization. Nothing sensitive is left behind.
  }
}

export function readPendingRegistration(): PendingRegistration | null {
  const store = sessionStorageOrNull();
  if (store === null) {
    return null;
  }
  let raw: string | null;
  try {
    raw = store.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (raw === null) {
    return null;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  return normalize(parsed);
}

export function clearPendingRegistration(): void {
  const store = sessionStorageOrNull();
  if (store === null) {
    return;
  }
  try {
    store.removeItem(STORAGE_KEY);
  } catch {
    // Best-effort cleanup only.
  }
}

function normalize(value: unknown): PendingRegistration | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as Record<string, unknown>;
  const email = text(record.email);
  const organizationName = text(record.organizationName);
  const organizationType = record.organizationType;
  const countryCodeResult = text(record.countryCode);
  if (countryCodeResult === null) {
    return null;
  }
  const countryCode = countryCodeResult.toUpperCase();
  if (
    email === null ||
    organizationName === null ||
    typeof organizationType !== "string" ||
    !(ORGANIZATION_TYPES as readonly string[]).includes(organizationType) ||
    !/^[A-Z]{2}$/.test(countryCode)
  ) {
    return null;
  }
  return {
    email,
    organizationName,
    organizationType: organizationType as OrganizationType,
    countryCode,
    region: text(record.region),
    contactName: text(record.contactName),
  };
}

function text(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

/** Map the cached profile onto the backend request shape. */
export function toRegistrationInput(
  pending: PendingRegistration,
): OrganizationRegistrationInput {
  return {
    organization_name: pending.organizationName,
    organization_type: pending.organizationType,
    country_code: pending.countryCode,
    region: pending.region,
    contact_name: pending.contactName,
    contact_email: pending.email,
  };
}
