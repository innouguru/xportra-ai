import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { getSupabaseClient } from "../../app/supabaseClient";
import { AppShell } from "../../components/AppShell";

const MIN_PASSWORD_LENGTH = 8;

type Phase = "request" | "sent" | "exchanging" | "form" | "updated" | "invalid" | "unconfigured";

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/** Public recovery request and PKCE recovery callback surface. */
export function ResetPasswordPage() {
  const auth = useAuth();
  const [params] = useSearchParams();
  const [phase, setPhase] = useState<Phase>(() => {
    if (!getSupabaseClient()) return "unconfigured";
    if (params.get("error") || params.get("error_description")) return "invalid";
    return params.get("code") ? "exchanging" : auth.isPasswordRecovery ? "form" : "request";
  });
  const attempted = useRef(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;
    const client = getSupabaseClient();
    if (!client) {
      setPhase("unconfigured");
      return;
    }
    const code = params.get("code");
    if (!code) {
      if (auth.isPasswordRecovery) setPhase("form");
      return;
    }
    let cancelled = false;
    client.auth.exchangeCodeForSession(code).then(({ data, error: exchangeError }) => {
      if (cancelled) return;
      setPhase(exchangeError || !data.session ? "invalid" : "form");
    }).catch(() => {
      if (!cancelled) setPhase("invalid");
    });
    return () => { cancelled = true; };
    // The callback code is consumed exactly once when this page mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const requestRecovery = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    const address = email.trim();
    if (!isValidEmail(address)) {
      setError("Enter a valid email address to request a recovery link.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await auth.requestPasswordReset(address);
      if (result.sent) setPhase("sent");
      else setError(result.errorMessage ?? "We could not send a recovery link. Try again.");
    } catch {
      setError("We could not send a recovery link. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  const updatePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Choose a password with at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await auth.updatePassword(password);
      if (result.ok) setPhase("updated");
      else setError(result.errorMessage ?? "We could not set your new password. Try again.");
    } catch {
      setError("We could not set your new password. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell title="Reset your password">
      {phase === "unconfigured" ? (
        <p role="alert">Sign-in is not configured for this build. Ask the site administrator to configure it, then try again.</p>
      ) : phase === "exchanging" ? (
        <p role="status">Checking your recovery link…</p>
      ) : phase === "invalid" ? (
        <>
          <p role="alert">This password recovery link is invalid, expired, or already used. Request a new one to continue.</p>
          <p><Link className="primary-button" to="/reset-password">Request a new link</Link></p>
          <p><Link to="/session">Back to sign in</Link></p>
        </>
      ) : phase === "sent" ? (
        <>
          <p role="status">If an account exists for that email address, a recovery link is on its way.</p>
          <p><Link to="/session">Back to sign in</Link></p>
        </>
      ) : phase === "updated" ? (
        <>
          <p role="status">Your password has been updated.</p>
          <p><Link className="primary-button" to="/session">Continue to sign in</Link></p>
        </>
      ) : phase === "form" || auth.isPasswordRecovery ? (
        <>
          <p className="lede">Choose a new password for your account.</p>
          <form className="form" onSubmit={updatePassword} noValidate>
            <fieldset disabled={busy}>
              <legend>New password</legend>
              <div className="form-row">
                <label htmlFor="reset-password">New password</label>
                <div className="password-field">
                  <input id="reset-password" type={showPassword ? "text" : "password"} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
                  <button type="button" className="ghost-button" aria-pressed={showPassword} onClick={() => setShowPassword((value) => !value)}>{showPassword ? "Hide" : "Show"}</button>
                </div>
                <p className="form-hint">Use at least {MIN_PASSWORD_LENGTH} characters.</p>
              </div>
              <div className="form-row">
                <label htmlFor="reset-password-confirm">Confirm new password</label>
                <input id="reset-password-confirm" type={showPassword ? "text" : "password"} autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} required />
              </div>
              {error ? <p role="alert">{error}</p> : null}
              <button type="submit" className="primary-button" disabled={busy}>{busy ? "Saving…" : "Set new password"}</button>
            </fieldset>
          </form>
          <p><Link to="/session">Back to sign in</Link></p>
        </>
      ) : (
        <>
          <p className="lede">Enter your account email and we’ll send a password recovery link.</p>
          <form className="form" onSubmit={requestRecovery} noValidate>
            <fieldset disabled={busy}>
              <legend>Recover your account</legend>
              <div className="form-row">
                <label htmlFor="recovery-email">Email address</label>
                <input id="recovery-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
              </div>
              {error ? <p role="alert">{error}</p> : null}
              <button type="submit" className="primary-button" disabled={busy || !auth.supabaseConfigured}>{busy ? "Sending recovery link…" : "Send recovery link"}</button>
            </fieldset>
          </form>
          {!auth.supabaseConfigured ? <p role="alert">Sign-in is not configured for this build. Ask the site administrator to configure it, then try again.</p> : null}
          <p><Link to="/session">Back to sign in</Link></p>
        </>
      )}
    </AppShell>
  );
}
