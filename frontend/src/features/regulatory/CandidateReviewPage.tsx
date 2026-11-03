import { Link, useParams } from "react-router-dom";
import type { AuthCredentials } from "../../api/client";
import { useAuth } from "../../app/AuthContext";
import { CandidateReview } from "./CandidateReview";
import { REGULATORY_BASE, sourcePath } from "./regulatoryUi";

/** A candidate gets a full page of its own: facts left, decisions right. */
export function CandidateReviewPage() {
  const { sourceId = "", candidateId = "" } = useParams();
  const auth = useAuth() as AuthCredentials;
  const backTo = sourcePath(sourceId, "candidates");

  return (
    <div className="reg-source">
      <nav aria-label="Breadcrumb" className="reg-crumbs">
        <Link to={REGULATORY_BASE}>Regulatory sources</Link>
        <span aria-hidden="true">/</span>
        <Link to={backTo}>Source candidates</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">Candidate review</span>
      </nav>
      <CandidateReview auth={auth} candidateId={candidateId} backTo={backTo} />
    </div>
  );
}
