/**
 * Onboarding state tracking (signup password-setup enforcement).
 *
 * Uses sessionStorage so the state survives page refreshes within
 * the same browser session but requires a valid session for protected
 * routes. This balances recoverability with security: clearing
 * browser data or opening a new tab forces re-authentication, which
 * is appropriate for a new-account onboarding gate.
 */

const STORAGE_KEY = "xportra.onboarding-state.v1";

export interface OnboardingState {
  completed: boolean;
  email: string | null;
  pendingRegistration: boolean;
}

function sessionStorageOrNull(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function saveOnboardingState(partial: Partial<OnboardingState>): void {
  const store = sessionStorageOrNull();
  if (store === null) return;
  const existing = readOnboardingState();
  const normalized: OnboardingState = {
    completed: partial.completed ?? existing?.completed ?? false,
    email: partial.email ?? existing?.email ?? null,
    pendingRegistration: partial.pendingRegistration ?? existing?.pendingRegistration ?? false,
  };
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Storage full or unavailable: best-effort only.
  }
}

export function readOnboardingState(): OnboardingState | null {
  const store = sessionStorageOrNull();
  if (store === null) return null;
  let raw: string | null;
  try {
    raw = store.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (raw === null) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    clearOnboardingState();
    return null;
  }
  if (typeof parsed !== "object" || parsed === null) {
    clearOnboardingState();
    return null;
  }
  const record = parsed as Record<string, unknown>;
  const completed = record.completed === true;
  const email = typeof record.email === "string" ? record.email : null;
  const pendingRegistration = record.pendingRegistration === true;
  return { completed, email, pendingRegistration };
}

export function clearOnboardingState(): void {
  const store = sessionStorageOrNull();
  if (store === null) return;
  try {
    store.removeItem(STORAGE_KEY);
  } catch {
    // Best-effort cleanup only.
  }
}

export function isOnboardingComplete(): boolean {
  const state = readOnboardingState();
  return state !== null && state.completed;
}
