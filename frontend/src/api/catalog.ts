import { apiFetch, type AuthCredentials } from "./client";

/**
 * Typed regulatory catalog endpoints (exporter-facing).
 *
 * The catalog exposes only published requirements that have been
 * evaluated as applicable to the requesting organization's scope.
 * All governance filtering happens server-side.
 */

export interface CatalogSourceReference {
  source_id: string | null;
  source_title: string | null;
  source_jurisdiction: string | null;
  source_version: string | null;
  source_status: string | null;
}

export interface CatalogCitationReference {
  normalized_document_id: string | null;
  source_location: Record<string, unknown> | null;
  position: number | null;
  parser_version: string | null;
}

export interface CatalogApplicability {
  outcome: string;
  reason: string | null;
  context_fingerprint: string | null;
}

export interface CatalogRequirementItem {
  requirement_id: string;
  requirement_text: string;
  requirement_type: string;
  stage_a_status: string;
  stage_b_status: string;
  stage_b_pilot_scope: string | null;
  published_at: string | null;
  source: CatalogSourceReference;
  citation: CatalogCitationReference;
  applicability: CatalogApplicability;
}

export interface CatalogRequirementsResponse {
  items: CatalogRequirementItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface FetchCatalogRequirementsInput {
  product?: string;
  origin_country?: string;
  destination_country?: string;
  limit?: number;
  offset?: number;
}

/**
 * Fetch published regulatory requirements applicable to the
 * organization's scope from the backend catalog.
 *
 * Tenant identity is resolved server-side from membership.
 * The caller cannot supply a tenant ID.
 */
export async function fetchCatalogRequirements(
  credentials: AuthCredentials,
  input: FetchCatalogRequirementsInput = {},
): Promise<CatalogRequirementsResponse> {
  const params = new URLSearchParams();
  if (input.product) params.set("product", input.product);
  if (input.origin_country) params.set("origin_country", input.origin_country);
  if (input.destination_country) params.set("destination_country", input.destination_country);
  if (input.limit !== undefined) params.set("limit", String(input.limit));
  if (input.offset !== undefined) params.set("offset", String(input.offset));

  const query = params.toString();
  const path = query ? `/catalog/requirements?${query}` : "/catalog/requirements";

  return apiFetch<CatalogRequirementsResponse>(path, credentials);
}