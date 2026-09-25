import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { AuthCredentials } from "../api/client";

/**
 * Session authentication state.
 *
 * - Production: bearer token (Supabase JWT), kept in memory only.
 * - Local development only: development tenant ID header.
 *   The UI labels this input as dev-only; production builds
 *   must use bearer tokens.
 * Tenant identity always comes from server-resolved
 * membership — the client never invents tenant IDs.
 */
interface AuthState extends AuthCredentials {
  setToken: (token: string | null) => void;
  setDevTenantId: (tenantId: string | null) => void;
  clear: () => void;
  isConfigured: boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({
  children,
  initial,
}: {
  children: ReactNode;
  /** Optional starting credentials (e.g. restored session or tests). */
  initial?: Partial<AuthCredentials>;
}) {
  const [token, setToken] = useState<string | null>(initial?.token ?? null);
  const [devTenantId, setDevTenantId] = useState<string | null>(
    initial?.devTenantId ?? null,
  );

  const value = useMemo<AuthState>(
    () => ({
      token,
      devTenantId,
      setToken,
      setDevTenantId,
      clear: () => {
        setToken(null);
        setDevTenantId(null);
      },
      isConfigured: token !== null || devTenantId !== null,
    }),
    [token, devTenantId],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (state === null) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return state;
}
