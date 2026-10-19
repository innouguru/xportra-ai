import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "./AuthContext";

/**
 * Shared sign-out action for every authenticated surface.
 *
 * Terminates the Supabase session through `AuthContext.signOut` and
 * returns the user to the public sign-in route only after success. Session-scoped
 * workflow data is cleared by `WorkflowSessionSync`, which reacts to
 * the resulting unauthenticated state, so this hook does not touch
 * storage itself.
 */
export function useSignOut(): () => Promise<boolean> {
  const auth = useAuth();
  const navigate = useNavigate();
  return useCallback(async (): Promise<boolean> => {
    try {
      await auth.signOut();
      navigate("/session", { replace: true });
      return true;
    } catch {
      return false;
    }
  }, [auth, navigate]);
}
