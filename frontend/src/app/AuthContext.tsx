import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AuthCredentials } from "../api/client";
import { authCallbackUrl, getSupabaseClient, supabaseConfigError } from "./supabaseClient";

/**
 * Session authentication state.
 *
 * - Production: Supabase magic-link session. The bearer token comes
 *   from the authenticated session (`session.access_token`), is
 *   restored on startup, refreshed by the Supabase client, and kept
 *   in memory only — it is never written to storage by this module.
 * - Local development only: development tenant ID header.
 *   The UI labels this input as dev-only; production builds
 *   must use Supabase sign-in.
 * Tenant identity always comes from server-resolved
 * membership — the client never invents tenant IDs.
 */
interface AuthState extends AuthCredentials {
  setToken: (token: string | null) => void;
  setDevTenantId: (tenantId: string | null) => void;
  clear: () => void;
  isConfigured: boolean;
  /** True while the initial Supabase session is being restored. */
  initializing: boolean;
  /** Signed-in account email, when a Supabase session is active. */
  userEmail: string | null;
  /** Whether Supabase sign-in is configured for this build. */
  supabaseConfigured: boolean;
  /** Request a magic-link email. Resolves to a safe status payload. */
  signInWithEmail: (email: string) => Promise<{
    sent: boolean;
    errorMessage: string | null;
  }>;
  /**
   * Sign out: clears local session state synchronously, then closes
   * the Supabase session. Local state stays cleared even if the
   * remote call fails.
   */
  signOut: () => Promise<void>;
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
  const [userEmail, setUserEmail] = useState<string | null>(null);
  // The single shared client for this build (null when unconfigured).
  const [client] = useState(getSupabaseClient);
  // Explicit test/initial credentials skip session restoration.
  const [initializing, setInitializing] = useState(
    () =>
      client !== null &&
      initial?.token === undefined &&
      initial?.devTenantId === undefined,
  );

  // One subscription per provider mount: restore the session once,
  // then follow client auth events (sign-in, refresh, sign-out).
  // No-op when Supabase is unconfigured (tests, misconfigured builds).
  useEffect(() => {
    if (client === null) {
      return undefined;
    }
    let cancelled = false;
    client.auth
      .getSession()
      .then(({ data }) => {
        if (cancelled) {
          return;
        }
        setToken(data.session?.access_token ?? null);
        setUserEmail(data.session?.user?.email ?? null);
        setInitializing(false);
      })
      .catch(() => {
        if (!cancelled) {
          setInitializing(false);
        }
      });
    const { data: subscription } = client.auth.onAuthStateChange(
      (_event, session) => {
        setToken(session?.access_token ?? null);
        setUserEmail(session?.user?.email ?? null);
      },
    );
    return () => {
      cancelled = true;
      subscription.subscription.unsubscribe();
    };
  }, [client]);

  const clear = useCallback(() => {
    setToken(null);
    setDevTenantId(null);
    setUserEmail(null);
  }, []);

  const signInWithEmail = useCallback(
    async (email: string) => {
      if (client === null) {
        return { sent: false as const, errorMessage: supabaseConfigError() };
      }
      const { error } = await client.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: authCallbackUrl(),
          // Never create accounts from the sign-in surface; the
          // owner account already exists.
          shouldCreateUser: false,
        },
      });
      if (error) {
        // Deliberately generic: no account-existence oracle, no
        // provider details in the UI.
        return {
          sent: false as const,
          errorMessage:
            "We could not send a sign-in link. Check the email address and try again.",
        };
      }
      return { sent: true as const, errorMessage: null };
    },
    [client],
  );

  const signOut = useCallback(async () => {
    // Local state clears synchronously so the UI responds
    // immediately and existing callers stay race-free.
    clear();
    try {
      await client?.auth.signOut();
    } catch {
      // Local session is already cleared; a failed remote call
      // must not resurrect it or surface credentials.
    }
  }, [client, clear]);

  const value = useMemo<AuthState>(
    () => ({
      token,
      devTenantId,
      setToken,
      setDevTenantId,
      clear,
      isConfigured: token !== null || devTenantId !== null,
      initializing,
      userEmail,
      supabaseConfigured: client !== null,
      signInWithEmail,
      signOut,
    }),
    [
      token,
      devTenantId,
      clear,
      initializing,
      userEmail,
      client,
      signInWithEmail,
      signOut,
    ],
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
