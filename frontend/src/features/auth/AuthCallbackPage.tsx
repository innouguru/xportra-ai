import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getSupabaseClient, safeReturnPath } from "../../app/supabaseClient";
import { AppShell } from "../../components/AppShell";

type CallbackState =
  | { kind: "working" }
  | { kind: "failed"; reason: "missing" | "invalid" | "unconfigured" };

/**
 * PKCE callback destination for Supabase magic-link sign-in.
 *
 * Exchanges the one-time `code` for a session through the shared
 * Supabase client. The URL (and any code it carries) is never
 * logged, displayed, or forwarded anywhere. Failures render a
 * recovery message instead of retrying.
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
      .then(({ error }) => {
        if (cancelled) {
          return;
        }
        if (error) {
          setState({ kind: "failed", reason: "invalid" });
          return;
        }
        navigate(next, { replace: true });
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
