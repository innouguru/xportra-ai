import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { getSupabaseClient, safeReturnPath } from "../../app/supabaseClient";
import { AppShell } from "../../components/AppShell";

/** Minimum length enforced before calling Supabase. */
const MIN_PASSWORD_LENGTH = 8;

type Phase =
  | "awaiting"
  | "exchanging"
  | "form"
  | "invalid"
  | "missing"
  | "unconfigured";

/**
 * Password-recovery destination for Supabase reset emails.
 *
 * The recovery link carries a one-time PKCE `code`; it is
 * exchanged for a short-lived recovery session, then the user sets
 * a new password through the shared client. The URL (and any code
 * it carries) is never logged, displayed, or forwarded. When the
 * visitor already holds a session (or opens the route directly),
 * the form still requires a valid session to apply the change; the
 * backend remains the authority on the resulting token.
 */
export function ResetPasswordPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeReturnPath(params.get("next"));

  const [phase, setPhase] = useState<Phase>(() => {
    const client = getSupabaseClient();
    if (client === null) {
      return "unconfigured";
    }
    if (params.get("error")) {
      return "invalid";
    }
    return params.get("code") ? "exchanging" : "awaiting";
  });
  const attempted = useRef(false);

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (attempted.current) {
      return;
    }
    attempted.current = true;
    const client = getSupabaseClient();
    if (client === null) {
      setPhase("unconfigured");
      return;
    }
    const code = params.get("code");
    if (!code) {
      // No code to exchange: an existing session decides the view.
      return;
    }
    let cancelled = false;
    client.auth
      .exchangeCodeForSession(code)
      .then(({ error: exchangeError }) => {
        if (cancelled) {
          return;
        }
        setPhase(exchangeError ? "invalid" : "form");
      })
      .catch(() => {
        if (!cancelled) {
          setPhase("invalid");
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const view: Phase =
    phase === "awaiting"
      ? auth.initializing
        ? "exchanging"
        : auth.isConfigured
          ? "form"
          : "missing"
      : phase;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving) {
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(
        `Choose a password with at least ${MIN_PASSWORD_LENGTH} characters.`,
      );
      return;
    }
    if (password !== confirm) {
      setError("The passwords do not match.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await auth.updatePassword(password);
      if (result.ok) {
        navigate(next, { replace: true });
      } else {
        setError(
          result.errorMessage ?? "We could not set your new password. Try again.",
        );
      }
    } catch {
      setError(
        "We could not set your new password. Check your connection and try again.",
      );
    } finally {
      setSaving(false);
    }
  };

  if (view !== "form") {
    return (
      <AppShell title="Reset your password">
        {view === "exchanging" ? (
          <p role="status">Preparing password reset…</p>
        ) : (
          <>
            <p role="alert">
              {view === "unconfigured"
                ? "Sign-in is not configured for this build. Ask your workspace owner to configure it, then try again."
                : view === "missing"
                  ? "Open the password reset link from your email to continue. If it has expired, request a new one from the sign-in page."
                  : "This password reset link is invalid, expired, or already used. Request a new one to continue."}
            </p>
            <p>
              <Link className="primary-button" to="/session">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </AppShell>
    );
  }

  return (
    <AppShell title="Reset your password">
      <p className="lede">Choose a new password for your account.</p>
      <form className="form" onSubmit={submit} noValidate>
        <fieldset>
          <legend>New password</legend>
          <div className="form-row">
            <label htmlFor="reset-password">New password</label>
            <div className="password-field">
              <input
                id="reset-password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <button
                type="button"
                className="ghost-button"
                aria-pressed={showPassword}
                onClick={() => setShowPassword((value) => !value)}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            <p className="form-hint">
              Use at least {MIN_PASSWORD_LENGTH} characters.
            </p>
          </div>
          <div className="form-row">
            <label htmlFor="reset-password-confirm">Confirm new password</label>
            <input
              id="reset-password-confirm"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              required
            />
          </div>
          {error ? (
            <p role="alert">{error}</p>
          ) : null}
          <button type="submit" className="primary-button" disabled={saving}>
            {saving ? "Saving…" : "Set new password"}
          </button>
        </fieldset>
      </form>
    </AppShell>
  );
}
