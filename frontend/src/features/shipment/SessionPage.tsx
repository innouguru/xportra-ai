import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { AppShell } from "../../components/AppShell";

/**
 * Session setup. Production uses a bearer token; local
 * development may use the dev tenant header (labeled as
 * dev-only — never a production mechanism).
 */
export function SessionPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [token, setToken] = useState("");
  const [devTenantId, setDevTenantId] = useState("");

  const connect = (event: React.FormEvent) => {
    event.preventDefault();
    if (token.trim()) {
      auth.setToken(token.trim());
      auth.setDevTenantId(null);
    } else if (devTenantId.trim()) {
      auth.setToken(null);
      auth.setDevTenantId(devTenantId.trim());
    }
    navigate("/");
  };

  return (
    <AppShell title="Connect to your workspace">
      <p className="lede">
        Xportra identifies your tenant from your credentials. Use a bearer
        token in production; the development tenant field below is for local
        development only.
      </p>
      <form className="form" onSubmit={connect}>
        <fieldset>
          <legend>Production credentials</legend>
          <div className="form-row">
            <label htmlFor="bearer-token">Bearer token (production)</label>
            <input
              id="bearer-token"
              type="password"
              autoComplete="off"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Supabase JWT access token"
            />
            <p className="form-hint">
              Your tenant is identified from this token. It stays in memory
              for this session only.
            </p>
          </div>
        </fieldset>
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
        </fieldset>
        <button type="submit" className="primary-button" disabled={!token.trim() && !devTenantId.trim()}>
          Connect
        </button>
      </form>
    </AppShell>
  );
}
