import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";
import { readOnboardingState } from "./onboarding";
import { readPendingRegistration } from "./pendingRegistration";

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
  // Enforce onboarding only when there's evidence it's needed:
  // either a pending organization profile exists, or the onboarding
  // state explicitly records an incomplete new-registration flow.
  const pendingProfile = readPendingRegistration();
  const onboardingState = readOnboardingState();
  const onboardingNeeded = pendingProfile !== null || (onboardingState !== null && !onboardingState.completed);
  if (onboardingNeeded) {
    return <Navigate to="/setup-password" replace />;
  }
  return <>{children}</>;
}
