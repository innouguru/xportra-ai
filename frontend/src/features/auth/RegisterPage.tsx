import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, userFacingErrorMessage } from "../../api/client";
import { registerOrganization } from "../../api/organizations";
import { useAuth } from "../../app/AuthContext";
import {
  clearPendingRegistration,
  readPendingRegistration,
  savePendingRegistration,
  toRegistrationInput,
  type PendingRegistration,
} from "../../app/pendingRegistration";
import { AppShell } from "../../components/AppShell";
import type { OrganizationType } from "../../types/api";

const ORGANIZATION_TYPE_OPTIONS: { value: OrganizationType; label: string }[] = [
  { value: "farmer", label: "Farmer / grower" },
  { value: "cooperative", label: "Cooperative" },
  { value: "exporter", label: "Exporter" },
  { value: "service_provider", label: "Service provider" },
  { value: "other", label: "Other" },
];

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/**
 * Organization self-service registration (Phase 10.11).
 *
 * Registers organization profile input only — identity, tenant, and
 * the initial `owner` role are derived server-side from the verified
 * session, so this form has no tenant, user, or role field. Screen
 * copy states plainly that registering creates an active workspace
 * and is not a regulatory verification, approval, or compliance
 * status.
 *
 * Two paths share one validated form:
 * - Not signed in: request a magic-link that creates the account on
 *   first use, cache the profile for the callback, then finish when
 *   the link is opened.
 * - Already signed in (Supabase session): post the profile directly
 *   and continue to the workspace; an "already registered" result is
 *   treated as success.
 */
export function RegisterPage() {
  const auth = useAuth();
  const navigate = useNavigate();

  const [organizationName, setOrganizationName] = useState("");
  const [organizationType, setOrganizationType] = useState<OrganizationType | "">("");
  const [countryCode, setCountryCode] = useState("");
  const [region, setRegion] = useState("");
  const [contactName, setContactName] = useState("");
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [recoveryProfile, setRecoveryProfile] = useState<PendingRegistration | null>(
    () => readPendingRegistration(),
  );
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const signedIn = auth.token !== null;

  const resumeRegistration = async () => {
    if (sending || !auth.token || recoveryProfile === null) return;
    if (
      auth.userEmail &&
      auth.userEmail.toLowerCase() !== recoveryProfile.email.toLowerCase()
    ) {
      setError("Sign in with the email address used to start this registration.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      await registerOrganization(
        { token: auth.token, devTenantId: null },
        toRegistrationInput(recoveryProfile),
      );
      clearPendingRegistration();
      setRecoveryProfile(null);
      navigate("/dashboard", { replace: true });
    } catch (caught) {
      if (
        caught instanceof ApiError &&
        caught.code === "organization_already_registered"
      ) {
        clearPendingRegistration();
        navigate("/dashboard", { replace: true });
        return;
      }
      setError(userFacingErrorMessage(caught));
    } finally {
      setSending(false);
    }
  };

  const validate = (): string | null => {
    if (!organizationName.trim()) {
      return "Enter your organization name.";
    }
    if (organizationType === "") {
      return "Choose the category that best describes your organization.";
    }
    if (!/^[A-Za-z]{2}$/.test(countryCode.trim())) {
      return "Enter a two-letter country code (for example, KE).";
    }
    if (!isValidEmail(email.trim())) {
      return "Enter a valid email address to confirm your account.";
    }
    return null;
  };

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (sending) {
      return;
    }
    const problem = validate();
    if (problem !== null) {
      setError(problem);
      return;
    }
    const pending = {
      email: email.trim(),
      organizationName: organizationName.trim(),
      organizationType: organizationType as OrganizationType,
      countryCode: countryCode.trim().toUpperCase(),
      region: region.trim() === "" ? null : region.trim(),
      contactName: contactName.trim() === "" ? null : contactName.trim(),
    };
    setSending(true);
    setError(null);
    try {
      if (auth.token !== null) {
        try {
          await registerOrganization(
            { token: auth.token, devTenantId: null },
            toRegistrationInput(pending),
          );
        } catch (caught) {
          if (
            caught instanceof ApiError &&
            caught.code === "organization_already_registered"
          ) {
            navigate("/dashboard", { replace: true });
            return;
          }
          throw caught;
        }
        clearPendingRegistration();
        navigate("/dashboard", { replace: true });
        return;
      }
      const result = await auth.registerWithEmail(pending.email);
      if (result.sent) {
        savePendingRegistration(pending);
        setSentTo(pending.email);
      } else {
        setError(
          result.errorMessage ??
            "We could not send your confirmation link. Try again.",
        );
      }
    } catch (caught) {
      setError(userFacingErrorMessage(caught));
    } finally {
      setSending(false);
    }
  };

  return (
    <AppShell title="Create your organization">
      <p className="lede">
        Register your organization to open an Xportra workspace. You become the
        workspace owner and can start recording shipments right away.
      </p>
      <p className="form-hint">
        Registering creates an active workspace. It is not a regulatory
        verification or approval, and it grants no compliance status.
      </p>

      {auth.initializationError ? (
        <section aria-label="Session recovery">
          <p role="alert">{auth.initializationError}</p>
          <button type="button" className="secondary-button" onClick={() => window.location.reload()}>
            Reload session
          </button>
        </section>
      ) : null}
      {sentTo ? (
        <section aria-label="Confirm your email">
          <p role="status">
            Check {sentTo} to confirm your email and finish creating your
            organization. The link expires soon and can be used once — request a
            new one if it lapses.
          </p>
          <p>
            <Link className="primary-button" to="/session">
              Already confirmed? Sign in
            </Link>
          </p>
        </section>
      ) : (
        <>
        {signedIn && recoveryProfile ? (
          <section aria-label="Resume organization registration">
            <p role="status">
              Saved registration details for {recoveryProfile.email} are
              available in this browser session. Resume to safely retry
              organization creation.
            </p>
            <button
              type="button"
              className="primary-button"
              onClick={() => void resumeRegistration()}
              disabled={sending}
            >
              {sending ? "Creating organization…" : "Resume registration"}
            </button>{" "}
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                clearPendingRegistration();
                setRecoveryProfile(null);
                setError(null);
              }}
              disabled={sending}
            >
              Cancel saved registration
            </button>
            {error ? <p role="alert">{error}</p> : null}
          </section>
        ) : null}
        {!(signedIn && recoveryProfile) ? (
        <form className="form" onSubmit={(event) => void onSubmit(event)} noValidate>
          <fieldset>
            <legend>Organization details</legend>

            {signedIn ? (
              <p className="form-hint">
                You are signed in
                {auth.userEmail ? ` as ${auth.userEmail}` : ""}. Submitting
                creates the organization for this account.
              </p>
            ) : null}

            <div className="form-row">
              <label htmlFor="register-organization-name">Organization name</label>
              <input
                id="register-organization-name"
                type="text"
                autoComplete="organization"
                value={organizationName}
                onChange={(event) => setOrganizationName(event.target.value)}
                placeholder="e.g. Rift Valley Fresh Produce"
                required
              />
            </div>

            <div className="form-row">
              <label htmlFor="register-organization-type">Organization category</label>
              <select
                id="register-organization-type"
                value={organizationType}
                onChange={(event) =>
                  setOrganizationType(event.target.value as OrganizationType | "")
                }
                required
              >
                <option value="">Select a category</option>
                {ORGANIZATION_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-row">
              <label htmlFor="register-country">Country</label>
              <input
                id="register-country"
                type="text"
                autoComplete="country"
                value={countryCode}
                onChange={(event) => setCountryCode(event.target.value)}
                placeholder="Two-letter code, e.g. KE"
                maxLength={2}
                required
              />
            </div>

            <div className="form-row">
              <label htmlFor="register-region">Region (optional)</label>
              <input
                id="register-region"
                type="text"
                value={region}
                onChange={(event) => setRegion(event.target.value)}
                placeholder="e.g. Central"
              />
            </div>

            <div className="form-row">
              <label htmlFor="register-contact-name">Your name (optional)</label>
              <input
                id="register-contact-name"
                type="text"
                autoComplete="name"
                value={contactName}
                onChange={(event) => setContactName(event.target.value)}
                placeholder="Defaults to the organization name"
              />
            </div>

            <div className="form-row">
              <label htmlFor="register-email">Email address</label>
              <input
                id="register-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                required
              />
              <p className="form-hint">
                {signedIn
                  ? "Used as the organization contact. Must match your signed-in account."
                  : "We email a one-time link to confirm this address and create your account."}
              </p>
            </div>

            {error ? <p role="alert">{error}</p> : null}
            {!auth.supabaseConfigured && !signedIn ? (
              <p role="alert">
                Registration is not configured for this build. Set the Supabase
                project URL and publishable key in the hosting environment and
                rebuild the frontend.
              </p>
            ) : null}

            <button
              type="submit"
              className="primary-button"
              disabled={sending || (!signedIn && !auth.supabaseConfigured)}
            >
              {signedIn
                ? sending
                  ? "Creating organization…"
                  : "Create organization"
                : sending
                  ? "Sending link…"
                  : "Email me a confirmation link"}
            </button>
          </fieldset>
        </form>
        ) : null}
        </>
      )}

      <p>
        Already have a workspace? <Link to="/session">Sign in</Link>.
      </p>
    </AppShell>
  );
}
