import { RegulationAdminPage } from "../regulatory/RegulationAdminPage";

/**
 * Staff regulatory ingestion dashboard — the navigation-facing entry
 * point for the "Regulatory Ingestion" destination
 * (`/regulatory-ingestion`).
 *
 * The privilege-sensitive ingestion workflow — regulatory source
 * inspection (title, status, version, supersession, provenance),
 * ingestion job monitoring (status, attempts, timestamps, failure
 * details), extracted requirement candidates (text, citations,
 * extraction outcome, review state), Stage A verification decisions
 * (`POST /regulatory/candidates/{id}/stage-a`), and Stage B
 * pilot-applicability decisions (`POST
 * /regulatory/candidates/{id}/stage-b`) — is implemented once in
 * `RegulationAdminPage` (features/regulatory), where it is covered by
 * focused tests and protected server-side by global staff grants
 * (`GRANT_MANAGE`, `STAGE_A_VERIFY`, `STAGE_B_APPROVE`).
 *
 * This component deliberately composes that tested surface instead of
 * duplicating authorization-sensitive workflow logic into a second
 * implementation. The backend remains the sole authority: no retry
 * endpoint, manual candidate entry, or publication action is offered
 * here, and every decision requires an authenticated actor whose
 * server-side grant and reviewer identity the API establishes.
 *
 * Rendering through this route does not change exporter-facing
 * behavior: the exporter catalog is a separate surface, and no
 * requirement appears public, verified, or applicable merely because
 * it is listed on this staff view.
 */
export function IngestionDashboard() {
  return <RegulationAdminPage />;
}
