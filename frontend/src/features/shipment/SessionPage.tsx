import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { safeReturnPath } from "../../app/supabaseClient";
import { AppShell } from "../../components/AppShell";

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/**
 * Session setup. Production signs in with a Supabase email
 * magic link; local development may use the dev tenant header
 * (labeled as dev-only — never a production mechanism).
 */
export function SessionPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeReturnPath(params.get("next"));
  const [email, setEmail] = useState("");
  const [devTenantId, setDevTenantId] = useState("");
  const [sending, setSending] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const signOut = () => {
    void auth.signOut();
  };

  return (
    <AppShell title="Connect to your workspace">
      <p className="lede">
        Xportra identifies your tenant from your credentials. Sign in with
        your email to receive a secure sign-in link; the development tenant
        field below is for local development only.
      </p>

      {auth.initializing ? (
        <p role="status">Preparing sign-in…</p>
      ) : auth.token ? (
        <section aria-label="Current session">
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
        <form className="form" onSubmit={requestLink} noValidate>
          <fieldset>
            <legend>Sign in with email</legend>
            {sentTo ? (
              <p role="status">
                Check {sentTo} for your sign-in link. The link expires soon
                and can be used once — request a new one if it lapses.
              </p>
            ) : (
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
                <p className="form-hint">
                  We email you a one-time sign-in link. It signs in this
                  browser only.
                </p>
              </div>
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
                {sending ? "Sending link…" : "Email me a sign-in link"}
              </button>
            )}
          </fieldset>
        </form>
      )}

      <form className="form" onSubmit={connectDev}>
        <fieldset>
          <legend>Local development</legend>
          <div className="form-row">
            <label htmlFor="dev-tenant">
              Development tenant ID <span className="tag">local development only</span>
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
    </AppShell>
  );
}
