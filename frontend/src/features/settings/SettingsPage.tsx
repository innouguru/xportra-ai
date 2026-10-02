import { Link, useNavigate } from "react-router-dom";
import { apiBaseUrl } from "../../api/client";
import { useAuth } from "../../app/AuthContext";
import { BackButton, PageHeader } from "../../primitives/layout";
import { AuthenticatedShell } from "../../shell/AuthenticatedShell";
import { ThemeControl } from "../../theme/theme";
import "./settings.css";

/**
 * Settings (approved redesign reference
 * `docs/design/xportra-ui-redesign.*`).
 *
 * A secondary, quiet surface: left-hand text
 * nav (Account / Organization / Notifications /
 * Security) with content on the right, rendered
 * as label/value rows. Only controls backed by
 * real boundaries are functional: session sign
 * in/out (`AuthContext`), theme
 * (`ThemeProvider` via `ThemeControl`), and
 * read-only connection facts. Account details
 * beyond the session, organization management,
 * notification preferences, and server-side
 * security settings have no backend boundary,
 * so they render as honest unavailable states
 * — no pretend toggles, no fake persistence.
 */
export function SettingsPage() {
  const auth = useAuth();
  const navigate = useNavigate();

  const method = auth.token
    ? "Bearer token (kept in memory for this session only)"
    : auth.devTenantId
      ? "Development tenant (local development only)"
      : "Not connected";

  return (
    <AuthenticatedShell crumbs={[{ label: "Settings" }]}>
      <BackButton label="Back to dashboard" onBack={() => navigate("/dashboard")} />
      <PageHeader title="Settings" />
      <div className="xb-settings-wrap">
        <nav className="xb-settings-nav" aria-label="Settings sections">
          <a href="#settings-account">Account</a>
          <a href="#settings-organization">Organization</a>
          <a href="#settings-notifications">Notifications</a>
          <a href="#settings-security">Security</a>
        </nav>
        <div className="xb-settings-panel">
          <section aria-labelledby="settings-account">
            <h2 className="xb-settings-section-title" id="settings-account">
              Account
            </h2>
            <div className="xb-settings-row">
              <div>
                <p className="xb-settings-row__label">Connection</p>
                <p className="xb-settings-row__desc">{method}</p>
              </div>
            </div>
            <div className="xb-settings-row">
              <div>
                <p className="xb-settings-row__label">Session</p>
                <p className="xb-settings-row__desc">
                  {auth.isConfigured ? "Connected on this device." : "Not connected."}
                </p>
              </div>
              {auth.isConfigured ? (
                <button type="button" className="secondary-button" onClick={auth.clear}>
                  Sign out
                </button>
              ) : (
                <Link className="secondary-button" to="/session">
                  Connect
                </Link>
              )}
            </div>
            <div className="xb-settings-row">
              <div>
                <p className="xb-settings-row__label">Appearance</p>
                <p className="xb-settings-row__desc">Dark or light workspace theme.</p>
              </div>
            </div>
            <h3 className="xb-settings-section-title">Preferences</h3>
            <ThemeControl />
            <p className="xb-ws-muted">
              Detailed account management isn’t available in this workspace yet.
            </p>
          </section>
          <section aria-labelledby="settings-organization">
            <h2 className="xb-settings-section-title" id="settings-organization">
              Organization
            </h2>
            <p className="xb-ws-muted">
              Organization settings aren’t available yet. Tenant identity comes from your
              authenticated session.
            </p>
          </section>
          <section aria-labelledby="settings-notifications">
            <h2 className="xb-settings-section-title" id="settings-notifications">
              Notifications
            </h2>
            <p className="xb-ws-muted">
              There are no notification settings to configure. Shipment updates stay quiet
              and informational inside the workspace.
            </p>
          </section>
          <section aria-labelledby="settings-security">
            <h2 className="xb-settings-section-title" id="settings-security">
              Security
            </h2>
            <div className="xb-settings-row">
              <div>
                <p className="xb-settings-row__label">API endpoint</p>
                <p className="xb-settings-row__desc">{apiBaseUrl()}</p>
              </div>
            </div>
            <div className="xb-settings-row">
              <div>
                <p className="xb-settings-row__label">Workspace data</p>
                <p className="xb-settings-row__desc">
                  The active record and started shipments stay in this browser’s session
                  storage so a reload resumes where you left off.
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </AuthenticatedShell>
  );
}
