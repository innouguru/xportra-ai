import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { safeReturnPath } from "../../app/supabaseClient";
import { AppShell } from "../../components/AppShell";

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

type SignInMode = "magic" | "password";

/**
 * Session setup. Production signs in with a Supabase email
 * magic link or account password; local development may use the
 * dev tenant header (labeled as dev-only — never a production
 * mechanism, and never rendered outside a development build).
 */
export function SessionPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeReturnPath(params.get("next"));
  // Inline Vite flag: production replaces this with `false`, so the
  // development-only control is tree-shaken out of the shipped bundle.
  const devEnabled = import.meta.env.DEV;

  const [mode, setMode] = useState<SignInMode>("magic");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [devTenantId, setDevTenantId] = useState("");
  const [sending, setSending] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [signOutError, setSignOutError] = useState<string | null>(null);

  const switchMode = (nextMode: SignInMode) => {
    if (nextMode === mode) {
      return;
    }
    setMode(nextMode);
    setError(null);
    setSentTo(null);
  };

  const connectDev = (event: React.FormEvent) => {
    event.preventDefault();
    if (!devTenantId.trim()) {
      return;
    }
    auth.setToken(null);
    auth.setDevTenantId(devTenantId.trim());
    navigate(next);
  };

  const requestLink = async (event: React.FormEvent) => {
    event.preventDefault();
    if (sending) {
      return;
    }
    const address = email.trim();
    if (!isValidEmail(address)) {
      setError("Enter a valid email address to receive a sign-in link.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      const result = await auth.signInWithEmail(address);
      if (result.sent) {
        setSentTo(address);
      } else {
        setError(result.errorMessage ?? "We could not send a sign-in link. Try again.");
      }
    } catch {
      setError("We could not send a sign-in link. Check your connection and try again.");
    } finally {
      setSending(false);
    }
  };

  const submitPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    if (sending) {
      return;
    }
    const address = email.trim();
    if (!isValidEmail(address)) {
      setError("Enter a valid email address to sign in.");
      return;
    }
    if (!password) {
      setError("Enter your account password to sign in.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      const result = await auth.signInWithPassword(address, password);
      if (result.ok) {
        navigate(next);
      } else {
        setError(result.errorMessage ?? "We could not sign you in. Try again.");
      }
    } catch {
      setError("We could not sign you in. Check your connection and try again.");
    } finally {
      setSending(false);
    }
  };

  const onSubmit = (event: React.FormEvent) => {
    if (mode === "password") {
      void submitPassword(event);
    } else {
      void requestLink(event);
    }
  };

  const signOut = () => {
    void auth.signOut().then(
      () => setSignOutError(null),
      () => setSignOutError("We could not sign you out. Check your connection and try again."),
    );
  };

  return (
    <AppShell title="Connect to your workspace">
      <p className="lede">
        Xportra identifies your tenant from your authenticated session. Sign in
        with a one-time email link or your account password.
        {devEnabled
          ? " The development tenant field below is for local development only."
          : ""}
      </p>

      {auth.initializationError ? (
        <section aria-label="Session recovery">
          <p role="alert">{auth.initializationError}</p>
          <button type="button" className="secondary-button" onClick={() => window.location.reload()}>
            Reload session
          </button>
        </section>
      ) : null}
      {auth.isConfigured ? (
        <section aria-label="Current session">
          {signOutError ? <p role="alert">{signOutError}</p> : null}
          <p role="status">
            {auth.userEmail
              ? `Signed in as ${auth.userEmail}.`
              : "You are signed in."}
          </p>
          <p className="form-hint">
            Your tenant is identified from this session.
          </p>
          <p>
            <Link className="primary-button" to={next}>
              Continue to the workspace
            </Link>{" "}
            <button type="button" className="secondary-button" onClick={signOut}>
              Sign out
            </button>
          </p>
        </section>
      ) : (
        // noValidate: this form owns validation so errors surface
        // through the accessible alert below in every browser.
        <form className="form" onSubmit={onSubmit} noValidate>
          <fieldset>
            <legend>Sign in</legend>

            <div className="auth-modes" role="group" aria-label="Sign-in method">
              <button
                type="button"
                className="auth-mode"
                aria-pressed={mode === "magic"}
                onClick={() => switchMode("magic")}
              >
                Email link
              </button>
              <button
                type="button"
                className="auth-mode"
                aria-pressed={mode === "password"}
                onClick={() => switchMode("password")}
              >
                Password
              </button>
            </div>

            {sentTo ? (
              <p role="status">
                Check {sentTo} for your sign-in link. The link expires soon
                and can be used once — request a new one if it lapses.
              </p>
            ) : (
              <>
                <div className="form-row">
                  <label htmlFor="signin-email">Email address</label>
                  <input
                    id="signin-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    required
                  />
                </div>
                {mode === "password" ? (
                  <div className="form-row">
                    <label htmlFor="signin-password">Password</label>
                    <div className="password-field">
                      <input
                        id="signin-password"
                        type={showPassword ? "text" : "password"}
                        autoComplete="current-password"
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
                      Use the password set for your account. Forgot it? Request
                      a reset link instead.
                    </p>
                  </div>
                ) : (
                  <p className="form-hint">
                    We email you a one-time sign-in link. It signs in this
                    browser only.
                  </p>
                )}
              </>
            )}

            {error ? (
              <p role="alert">{error}</p>
            ) : null}
            {!auth.supabaseConfigured ? (
              <p role="alert">
                Sign-in is not configured for this build. Set the Supabase
                project URL and publishable key in the hosting environment
                and rebuild the frontend.
              </p>
            ) : null}

            {sentTo ? null : (
              <button
                type="submit"
                className="primary-button"
                disabled={sending || !auth.supabaseConfigured}
              >
                {mode === "password"
                  ? sending
                    ? "Signing in…"
                    : "Sign in"
                  : sending
                    ? "Sending link…"
                    : "Email me a sign-in link"}
              </button>
            )}

            {mode === "password" && !sentTo ? (
              <p>
                <Link className="ghost-button" to="/reset-password">
                  Forgot password?
                </Link>
              </p>
            ) : null}
          </fieldset>
        </form>
      )}

      {devEnabled ? (
        <form className="form" onSubmit={connectDev}>
          <fieldset>
            <legend>Local development</legend>
            <div className="form-row">
              <label htmlFor="dev-tenant">
                Development tenant ID{" "}
                <span className="tag">local development only</span>
              </label>
              <input
                id="dev-tenant"
                type="text"
                autoComplete="off"
                value={devTenantId}
                onChange={(event) => setDevTenantId(event.target.value)}
                placeholder="Tenant UUID for local development"
              />
              <p className="form-hint">
                Never a production mechanism — local development only.
              </p>
            </div>
            <button
              type="submit"
              className="primary-button"
              disabled={!devTenantId.trim()}
            >
              Connect
            </button>
          </fieldset>
        </form>
      ) : null}
      <p>
        New to Xportra? <Link to="/register">Create an account</Link>.
      </p>
    </AppShell>
  );
}
