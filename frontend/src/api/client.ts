/**
 * Centralized HTTP client for the Xportra AI backend.
 *
 * All API traffic goes through `apiFetch`. Components and
 * features MUST NOT issue raw `fetch()` calls: base URL,
 * authentication headers, tenant behavior, and error
 * mapping live here and nowhere else.
 *
 * Authentication contract (mirrors `xportra/api/dependencies.py`):
 * - Production: `Authorization: Bearer <Supabase JWT>`.
 * - Local development only: `X-Development-Tenant-ID: <uuid>`.
 *   This header is a dev/test pathway and must never be
 *   presented as a production mechanism in the UI.
 * - Tenant identity always comes from server-resolved
 *   membership; the client never invents tenant IDs.
 */

export interface AuthCredentials {
  /** Supabase JWT for production use. */
  token: string | null;
  /** Development tenant ID. Local development ONLY. */
  devTenantId: string | null;
}

export const DEV_TENANT_HEADER = "X-Development-Tenant-ID";

export function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as
    | string
    | undefined;
  const base = (configured ?? "http://localhost:8000").replace(/\/+$/, "");
  return base;
}

export function buildAuthHeaders(credentials: AuthCredentials): HeadersInit {
  if (credentials.token) {
    return { Authorization: `Bearer ${credentials.token}` };
  }
  if (credentials.devTenantId) {
    return { [DEV_TENANT_HEADER]: credentials.devTenantId };
  }
  return {};
}

/** Categorized backend failure. `code` is the backend `error.code`. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/**
 * User-facing message for an API failure that preserves backend
 * semantics without inventing compliance meaning.
 */
export function userFacingErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "authentication_required":
      case "invalid_token":
        return "Your session is missing or expired. Sign in again.";
      case "permission_denied":
        return "Your role does not allow this action. Contact a workspace owner.";
      case "tenant_mismatch":
        return "This shipment belongs to a different workspace.";
      case "not_found":
        return "The requested record was not found in this workspace.";
      case "invalid_transition":
        return "This action is not available in the shipment's current step.";
      case "terminal_workflow":
        return "This assessment package is final and cannot be changed.";
      case "not_ready":
        return "The workflow is not ready for this action yet.";
      case "stale_analysis":
        return "A newer analysis exists. Review the latest results first.";
      case "validation_error":
      case "invalid_input":
        return error.message || "Some input was invalid. Check the form.";
      case "infrastructure_failure":
        return "A backend service is temporarily unavailable. Try again shortly.";
      default:
        return error.message || "Something went wrong. Try again.";
    }
  }
  if (error instanceof Error) {
    return "The service could not be reached. Check your connection.";
  }
  return "Something went wrong. Try again.";
}

export async function apiFetch<T>(
  path: string,
  credentials: AuthCredentials,
  options: {
    method?: string;
    body?: unknown;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...buildAuthHeaders(credentials),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(0, "network_unreachable", "The service could not be reached.");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const body = (payload ?? {}) as {
      error?: { code?: string; message?: string; details?: unknown };
    };
    throw new ApiError(
      response.status,
      body.error?.code ?? "unexpected_error",
      body.error?.message ?? `Request failed (${response.status}).`,
      body.error?.details,
    );
  }
  return payload as T;
}
