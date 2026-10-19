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
import {
  authCallbackUrl,
  getSupabaseClient,
  passwordResetUrl,
  supabaseConfigError,
} from "./supabaseClient";

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
   * Request a magic-link email that will create a Supabase account
   * when none exists yet (organization self-service registration,
   * Phase 10.11). Resolves to a safe status payload; failures stay
   * generic so the surface is not an account-existence oracle.
   */
  registerWithEmail: (email: string) => Promise<{
    sent: boolean;
    errorMessage: string | null;
  }>;
  /**
   * Sign in with an existing account email and password. Never
   * creates accounts. Resolves to a safe status payload; failures
   * stay generic so the surface is not an account-existence oracle.
   */
  signInWithPassword: (
    email: string,
    password: string,
  ) => Promise<{ ok: boolean; errorMessage: string | null }>;
  /**
   * Request a password-recovery email for an existing account.
   * Resolves to a safe status payload with a generic failure message.
   */
  requestPasswordReset: (
    email: string,
  ) => Promise<{ sent: boolean; errorMessage: string | null }>;
  /**
   * Set a new password for the current recovery/session user.
   * Resolves to a safe status payload.
   */
  updatePassword: (
    password: string,
  ) => Promise<{ ok: boolean; errorMessage: string | null }>;
  /**
   * Sign out and clear session-derived state only after Supabase
   * confirms termination. Rejects with a safe error on failure.
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
    let authEventVersion = 0;
    const restoreVersion = authEventVersion;
    client.auth
      .getSession()
      .then(({ data }) => {
        if (cancelled || authEventVersion !== restoreVersion) {
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
        authEventVersion += 1;
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

  const registerWithEmail = useCallback(
    async (email: string) => {
      if (client === null) {
        return { sent: false as const, errorMessage: supabaseConfigError() };
      }
      const { error } = await client.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${authCallbackUrl()}?flow=registration`,
          // Registration is the one deliberate account-creation
          // surface: the visitor has no account yet. Identity and
          // the initial role are still derived server-side.
          shouldCreateUser: true,
        },
      });
      if (error) {
        return {
          sent: false as const,
          errorMessage:
            "We could not send your confirmation link. Check the email address and try again.",
        };
      }
      return { sent: true as const, errorMessage: null };
    },
    [client],
  );

  const signInWithPassword = useCallback(
    async (email: string, password: string) => {
      if (client === null) {
        return { ok: false as const, errorMessage: supabaseConfigError() };
      }
      const { data, error } = await client.auth.signInWithPassword({
        email,
        password,
      });
      if (error || data.session === null) {
        // Deliberately generic: no account-existence oracle, no
        // provider details in the UI.
        return {
          ok: false as const,
          errorMessage:
            "We could not sign you in. Check your email and password and try again.",
        };
      }
      // Set the session synchronously from the returned session so
      // callers can navigate immediately without racing the listener.
      setToken(data.session.access_token);
      setUserEmail(data.session.user?.email ?? null);
      return { ok: true as const, errorMessage: null };
    },
    [client],
  );

  const requestPasswordReset = useCallback(
    async (email: string) => {
      if (client === null) {
        return { sent: false as const, errorMessage: supabaseConfigError() };
      }
      const { error } = await client.auth.resetPasswordForEmail(email, {
        redirectTo: passwordResetUrl(),
      });
      if (error) {
        return {
          sent: false as const,
          errorMessage:
            "We could not send a reset link. Check the email address and try again.",
        };
      }
      return { sent: true as const, errorMessage: null };
    },
    [client],
  );

  const updatePassword = useCallback(
    async (password: string) => {
      if (client === null) {
        return { ok: false as const, errorMessage: supabaseConfigError() };
      }
      const { error } = await client.auth.updateUser({ password });
      if (error) {
        return {
          ok: false as const,
          errorMessage:
            "We could not set your new password. Request a new reset link and try again.",
        };
      }
      return { ok: true as const, errorMessage: null };
    },
    [client],
  );

  const signOut = useCallback(async () => {
    if (client === null) {
      clear();
      return;
    }
    try {
      const { error } = await client.auth.signOut();
      if (error) {
        throw error;
      }
      clear();
    } catch {
      throw new Error("We could not sign you out. Check your connection and try again.");
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
      registerWithEmail,
      signInWithPassword,
      requestPasswordReset,
      updatePassword,
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
      registerWithEmail,
      signInWithPassword,
      requestPasswordReset,
      updatePassword,
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
