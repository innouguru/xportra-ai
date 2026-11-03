import { useOutletContext } from "react-router-dom";
import type { AuthCredentials } from "../../api/client";
import type {
  RegulatoryArtifact,
  RegulatoryCandidate,
  RegulatoryGovernanceFlag,
  RegulatoryIngestionJob,
  RegulatorySource,
} from "../../api/regulatory";

/** Data and actions shared by every tab of one source's page. */
export interface SourceContextValue {
  auth: AuthCredentials;
  sourceId: string;
  source: RegulatorySource;
  artifacts: RegulatoryArtifact[];
  jobs: RegulatoryIngestionJob[];
  candidates: RegulatoryCandidate[];
  flags: RegulatoryGovernanceFlag[];
  /** True while a user-initiated reload is in flight. */
  loading: boolean;
  /** Refetch everything. Silent reloads never toggle ``loading``. */
  reload: (options?: { silent?: boolean }) => Promise<void>;
}

export function useSourceContext(): SourceContextValue {
  return useOutletContext<SourceContextValue>();
}
