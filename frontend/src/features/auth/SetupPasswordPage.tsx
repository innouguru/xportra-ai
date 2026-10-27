import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { registerOrganization } from "../../api/organizations";
import {
  clearPendingRegistration,
  readPendingRegistration,
  toRegistrationInput,
} from "../../app/pendingRegistration";
import { saveOnboardingState, isOnboardingComplete } from "../../app/onboarding";
import { AppShell } from "../../components/AppShell";

const MIN_PASSWORD_LENGTH = 8;

/**
 * Dedicated password-creation screen for new signups after
 * email confirmation (Phase signup-flow fix).
 *
 * Enforced sequence:
 *   1. Confirm email (PKCE callback /auth/callback)
 *   2. Create password (this screen)
 *   3. Complete organization finalization (if pending)
 *   4. Navigate to dashboard
 *
 * The screen verifies a valid Supabase session and prevents
 * bypass through direct navigation. Missing or expired sessions
 * are handled gracefully with recoverable paths.
 */
export function SetupPasswordPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const nextPath = params.get("next") ? decodeURIComponent(params.get("next") || "").replace(/[^/\w-]/g, "") : "/dashboard";

  const handleSubmit = async (event: React.FormEvent) => {
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
    // Verify that any pending registration profile matches the
    // current session email to prevent stale-cache finalization.
    const pending = readPendingRegistration();
    if (
      pending !== null &&
      auth.userEmail !== null &&
      auth.userEmail.toLowerCase() !== pending.email.toLowerCase()
    ) {
      clearPendingRegistration();
      saveOnboardingState({
        completed: false,
        email: auth.userEmail,
        pendingRegistration: false,
      });
    }
    setBusy(true);
    setError(null);
    try {
      const result = await auth.updatePassword(password);
      if (!result.ok) {
        setError(result.errorMessage ?? "We could not set your password. Try again.");
        setBusy(false);
        return;
      }
      // Password saved successfully. Complete pending finalization.
      const pending = readPendingRegistration();
      if (pending !== null && auth.token !== null) {
        try {
          await registerOrganization(
            { token: auth.token, devTenantId: null },
            toRegistrationInput(pending),
          );
        } catch (caught: unknown) {
          // Organization finalization failure is recoverable; do not
          // treat it as a fatal authentication failure. The user can
          // retry via the callback or this page.
        }
        clearPendingRegistration();
      }
      saveOnboardingState({ completed: true, email: auth.userEmail || null, pendingRegistration: false });
      setCompleted(true);
      navigate(nextPath || "/dashboard", { replace: true });
    } catch {
      setError("We could not set your password. Check your connection and try again.");
      setBusy(false);
    }
  };

  // If the session is missing, show a recoverable state instead
  // of pretending the password was saved or allowing bypass.
  if (!auth.isConfigured) {
    return (
      <AppShell title="Complete your account">
        <section aria-label="Session unavailable">
          <p role="alert">
            Your session is not available. To complete your account, please sign in
            again or request a new confirmation link.
          </p>
          <p>
            <Link className="primary-button" to="/session">
              Back to sign in
            </Link>
          </p>
          <p>
            <Link className="secondary-button" to="/register">
              Restart registration
            </Link>
          </p>
        </section>
      </AppShell>
    );
  }

  // If onboarding is already complete, do not show this screen again.
  if (isOnboardingComplete() && completed) {
    navigate(nextPath || "/dashboard", { replace: true });
    return (
      <AppShell title="Completing setup">
        <p role="status">Completing your account setup…</p>
      </AppShell>
    );
  }

  return (
    <AppShell title="Create your password">
      <section aria-label="Create a password">
        <p className="lede">
          Create a password for your account before continuing to your workspace.
        </p>
        <form className="form" onSubmit={handleSubmit} noValidate>
          <fieldset disabled={busy}>
            <legend>New password</legend>
            <div className="form-row">
              <label htmlFor="setup-password">New password</label>
              <div className="password-field">
                <input
                  id="setup-password"
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
              <p className="form-hint">Use at least {MIN_PASSWORD_LENGTH} characters.</p>
            </div>
            <div className="form-row">
              <label htmlFor="setup-password-confirm">Confirm new password</label>
              <input
                id="setup-password-confirm"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                required
              />
            </div>
            {error ? <p role="alert">{error}</p> : null}
            <button type="submit" className="primary-button" disabled={busy}>
              {busy ? "Saving password…" : "Continue to workspace"}
            </button>
          </fieldset>
        </form>
      </section>
    </AppShell>
  );
}
