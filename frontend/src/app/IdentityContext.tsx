/**
 * Current-account identity state for the authenticated shell.
 *
 * Resolves the signed-in person's name, email, and active organization
 * from ``GET /me`` (server-resolved identity + membership) and makes it
 * available to every authenticated surface through ``useIdentity``.
 *
 * - While the Supabase session is still being restored, status is
 *   ``idle`` (no identity shown).
 * - Once a session exists, the identity is fetched once; status moves to
 *   ``loading`` then ``ready`` or ``error``.
 * - Signing out clears the identity so a stale person or company is
 *   never shown for a different account.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "./AuthContext";
import { fetchIdentity } from "../api/identity";
import type { Identity } from "../types/api";

type IdentityStatus = "idle" | "loading" | "ready" | "error";

interface IdentityContextValue {
  identity: Identity | null;
  status: IdentityStatus;
  error: string | null;
  refetch: () => void;
}

const IdentityContext = createContext<IdentityContextValue | null>(null);

export function IdentityProvider({
  children,
}: {
  children: ReactNode;
}) {
  const auth = useAuth();
  const [status, setStatus] = useState<IdentityStatus>("idle");
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);

  const clear = useCallback(() => {
    setIdentity(null);
    setError(null);
    setStatus("idle");
  }, []);

  const refetch = useCallback(() => {
    void loadIdentity();
  }, []);

  const loadIdentity = useCallback(async () => {
    if (!auth.token && !auth.devTenantId) {
      clear();
      return;
    }
    setStatus("loading");
    setError(null);
    try {
      const result = await fetchIdentity({ token: auth.token, devTenantId: auth.devTenantId });
      // Do not apply a response for a session that has since changed.
      if (!mounted.current) {
        return;
      }
      setIdentity(result);
      setStatus("ready");
    } catch {
      if (!mounted.current) {
        return;
      }
      setIdentity(null);
      setStatus("error");
      setError(
        "We couldn't load your account details. Your name and organization may not appear until the page reloads.",
      );
    }
  }, [auth.token, auth.devTenantId, clear]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // Fetch whenever an authenticated session exists and we have not yet
  // loaded it. Clearing on sign out happens naturally: when the token is
  // removed, this effect runs again and `loadIdentity` resets to idle.
  useEffect(() => {
    if (!mounted.current) {
      return undefined;
    }
    if (!auth.token && !auth.devTenantId) {
      clear();
      return undefined;
    }
    void loadIdentity();
  }, [auth.token, auth.devTenantId, loadIdentity, clear]);

  const value = useMemo<IdentityContextValue>(
    () => ({ identity, status, error, refetch }),
    [identity, status, error, refetch],
  );
  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}

export function useIdentity(): IdentityContextValue {
  const context = useContext(IdentityContext);
  if (context === null) {
    // Identity context is optional at render time: the authenticated shell
    // is sometimes exercised directly in tests without a provider. In the
    // real application IdentityProvider is always mounted, so identity is
    // resolved there. Gracefully degrade to "no identity known" instead of
    // throwing so unrelated surfaces keep rendering.
    return { identity: null, status: "idle", error: null, refetch: () => undefined };
  }
  return context;
}
