import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { userFacingErrorMessage } from "../../api/client";
import type { AuthCredentials } from "../../api/client";
import {
  registerRegulatorySource,
  type RegulatorySourceCreateRequest,
} from "../../api/regulatory";
import { useAuth } from "../../app/AuthContext";
import { RegisterSourceForm } from "./RegisterSourceForm";
import { REGULATORY_BASE, sourcePath } from "./regulatoryUi";

/**
 * Registration lives on its own page. On success the person lands
 * directly on the new source's document step instead of being left on a
 * list with the next step hidden further down the page.
 */
export function RegisterSourcePage() {
  const auth = useAuth() as AuthCredentials;
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const registerSource = useCallback(
    async (payload: RegulatorySourceCreateRequest): Promise<boolean> => {
      setError(null);
      try {
        const source = await registerRegulatorySource(auth, payload);
        navigate(sourcePath(source.id, "documents"), {
          state: { registered: source.title },
        });
        return true;
      } catch (caught) {
        setError(userFacingErrorMessage(caught));
        return false;
      }
    },
    [auth, navigate],
  );

  return (
    <div>
      <nav aria-label="Breadcrumb" className="reg-crumbs">
        <Link to={REGULATORY_BASE}>Regulatory sources</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">Register source</span>
      </nav>
      <header className="page-intro">
        <h1 className="reg-title">Register a regulatory source</h1>
        <p className="lede">
          Record the source&rsquo;s metadata first. You will upload the
          original document on the next screen.
        </p>
      </header>
      {error ? <p role="alert" className="ledger-reason">{error}</p> : null}
      <RegisterSourceForm auth={auth} onRegister={registerSource} />
    </div>
  );
}
