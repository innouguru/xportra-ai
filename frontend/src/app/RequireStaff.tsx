import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { useIdentity } from "./IdentityContext";
import { GRANT_MANAGE } from "../types/api";

/**
 * Gate for staff workspace routes.
 *
 * Mirrors `RequireAuth` but checks staff authorization: only a
 * server-resolved identity that carries an active global staff
 * ``grant_manage`` grant may proceed. While the identity is still
 * being established, a quiet checking state is shown instead of the
 * page content; when authorization is unknown, unavailable, or
 * absent, the guard fails closed with an in-place access panel and
 * a link back to the exporter dashboard. It never redirects the
 * person into a loop and never verifies permission itself — every
 * privileged operation remains authorized server-side by the global
 * staff grant dependencies.
 */
export function RequireStaff({ children }: { children: ReactNode }) {
  const { identity, status } = useIdentity();
  if (status !== "ready") {
    return (
      <main>
        <p role="status">Checking your access…</p>
      </main>
    );
  }
  if (!identity?.staff_permissions?.includes(GRANT_MANAGE)) {
    return (
      <main>
        <h1>This area is restricted</h1>
        <p>
          Regulatory ingestion administration is limited to authorized staff.
          Your account does not currently have the required permission.
        </p>
        <p>
          <Link to="/dashboard">Return to your dashboard</Link>
        </p>
      </main>
    );
  }
  return <>{children}</>;
}
