import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";

/**
 * Gate for authenticated workspace routes.
 *
 * While the session is restoring, renders a loading state instead
 * of redirecting (no premature navigation, no flicker). Signed-out
 * visitors are sent to `/session` with a safe internal return path;
 * only allow-listed destinations survive (see `safeReturnPath`).
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.initializing) {
    return (
      <main>
        <p role="status">Checking your session…</p>
      </main>
    );
  }
  if (!auth.isConfigured) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/session?next=${next}`} replace />;
  }
  return <>{children}</>;
}
