import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { readOnboardingState, saveOnboardingState } from "../../app/onboarding";
import {
  clearPendingRegistration,
  readPendingRegistration,
} from "../../app/pendingRegistration";
import { getSupabaseClient, safeReturnPath } from "../../app/supabaseClient";
import { AppShell } from "../../components/AppShell";

type CallbackState =
  | { kind: "working" }
  | {
      kind: "failed";
      reason: "missing" | "missing-profile" | "invalid" | "unconfigured" | "registration";
    };

/**
 * PKCE callback destination for Supabase magic-link sign-in.
 *
 * Exchanges the one-time `code` for a session through the shared
 * Supabase client. The URL (and any code it carries) is never
 * logged, displayed, or forwarded anywhere. Failures render a
 * recovery message instead of retrying.
 *
 * If a pending organization registration was cached before this
 * link was requested (Phase 10.11), the fresh bearer token is used
 * to finish creating the organization before continuing to the
 * workspace. Identity still comes from the verified session — the
 * cached profile supplies organization fields only — and an
 * "already registered" result is treated as success.
 */
export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [state, setState] = useState<CallbackState>({ kind: "working" });
  const attempted = useRef(false);
  const next = safeReturnPath(params.get("next"));

  useEffect(() => {
    // Guard against double-exchange (StrictMode double effects):
    // a PKCE code is single-use, so only the first attempt counts.
    if (attempted.current) {
      return;
    }
    attempted.current = true;
    const client = getSupabaseClient();
    if (client === null) {
      setState({ kind: "failed", reason: "unconfigured" });
      return;
    }
    const code = params.get("code");
    if (params.get("error") || !code) {
      setState({
        kind: "failed",
        reason: !code && !params.get("error") ? "missing" : "invalid",
      });
      return;
    }
    let cancelled = false;
    client.auth
      .exchangeCodeForSession(code)
      .then(({ data, error }) => {
        if (cancelled) {
          return;
        }
        if (error || data.session === null) {
          setState({ kind: "failed", reason: "invalid" });
          return;
        }
        const pending = readPendingRegistration();
        const sessionEmail = data.session.user?.email ?? null;
        const onboardingState = readOnboardingState();
        // Treat null onboarding state as complete when there's no
        // pending profile — this covers existing users and normal
        // magic-link sign-in without a new-registration flow.
        const onboardingIncomplete =
          onboardingState !== null ? !onboardingState.completed : false;

        // If the registration flow has no pending profile, the user
        // started registration but did not cache their profile; show
        // the recoverable error instead of redirecting to password setup.
        if (pending === null && params.get("flow") === "registration") {
          setState({ kind: "failed", reason: "missing-profile" });
          return;
        }

        // New registrations that require password setup must complete
        // onboarding at /setup-password before accessing the workspace.
        // Organization finalization is deferred to /setup-password so it
        // runs only after the user has successfully set a password.
        if (pending !== null || onboardingIncomplete) {
          // If there's a stale profile from a different account, clean
          // it up before redirecting so /setup-password does not
          // attempt finalization for the wrong identity.
          if (
            pending !== null &&
            sessionEmail !== null &&
            sessionEmail.toLowerCase() !== pending.email.toLowerCase()
          ) {
            clearPendingRegistration();
            saveOnboardingState({
              completed: false,
              email: sessionEmail,
              pendingRegistration: false,
            });
          } else if (pending !== null) {
            saveOnboardingState({
              completed: false,
              email: sessionEmail ?? pending.email,
              pendingRegistration: true,
            });
          } else {
            saveOnboardingState({
              completed: false,
              email: sessionEmail,
              pendingRegistration: false,
            });
          }
          navigate(`/setup-password?next=${encodeURIComponent(next)}`, { replace: true });
          return;
        }

        // Onboarding is complete and no pending profile: navigate
        // directly as before.
        if (params.get("flow") === "registration") {
          setState({ kind: "failed", reason: "missing-profile" });
          return;
        }
        navigate(next, { replace: true });
        return;
      })
      .catch(() => {
        if (!cancelled) {
          setState({ kind: "failed", reason: "invalid" });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (state.kind === "working") {
    return (
      <AppShell title="Completing sign-in">
        <p role="status">Completing sign-in…</p>
      </AppShell>
    );
  }
  if (state.reason === "registration") {
    return (
      <AppShell title="Could not finish registration">
        <p role="alert">
          Your email is confirmed, but we could not finish creating your
          organization. Return to registration to try again.
        </p>
        <p>
          <Link className="primary-button" to="/register">
            Back to registration
          </Link>{" "}
          <Link className="secondary-button" to="/session">
            Sign in
          </Link>
        </p>
      </AppShell>
    );
  }
  if (state.reason === "missing-profile") {
    return (
      <AppShell title="Registration details unavailable">
        <p role="alert">
          Your email is confirmed, but the organization details could not be
          recovered from this browser tab. Registration details are kept only
          for the current browser session; they may be unavailable if the link
          opened in another tab or browser.
        </p>
        <p>
          <Link className="primary-button" to="/register">
            Restart registration
          </Link>{" "}
          <Link className="secondary-button" to="/session">
            Sign in
          </Link>
        </p>
      </AppShell>
    );
  }
  return (
    <AppShell title="Sign-in link unavailable">
      <p role="alert">
        {state.reason === "unconfigured"
          ? "Sign-in is not configured for this build. Ask your workspace owner to configure it, then try again."
          : "This sign-in link is invalid, expired, or already used. Request a new link to sign in."}
      </p>
      <p>
        <Link className="primary-button" to="/session">
          Back to sign in
        </Link>
      </p>
    </AppShell>
  );
}
