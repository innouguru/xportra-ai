import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import type { AuthCredentials } from "../../api/client";
import {
  getRegulatorySource,
  listSourceArtifacts,
  listSourceCandidates,
  listSourceGovernanceFlags,
  listSourceJobs,
  type RegulatoryArtifact,
  type RegulatoryCandidate,
  type RegulatoryGovernanceFlag,
  type RegulatoryIngestionJob,
  type RegulatorySource,
} from "../../api/regulatory";
import { useAuth } from "../../app/AuthContext";
import { ErrorNotice, LoadingState, StatusBadge } from "../../components/StatusBits";
import type { SourceContextValue } from "./SourceContext";
import { NextActionCard, SourceProgress } from "./SourceProgress";
import {
  REGULATORY_BASE,
  deriveSourceProgress,
  documentJobs,
  sourcePath,
  tone,
  type SourceTab,
} from "./regulatoryUi";

/** How often to refresh while a document ingestion job is still running. */
const POLL_INTERVAL_MS = 5000;

interface SourceData {
  source: RegulatorySource;
  artifacts: RegulatoryArtifact[];
  jobs: RegulatoryIngestionJob[];
  candidates: RegulatoryCandidate[];
  flags: RegulatoryGovernanceFlag[];
}

/**
 * One source = one page. Loads the source and everything attached to it
 * once, shows where it stands (stepper + next step), and hands the data
 * to whichever tab is open. Switching tabs never refetches.
 */
export function SourceLayout() {
  const { sourceId = "" } = useParams();
  const auth = useAuth() as AuthCredentials;
  const location = useLocation();
  const [data, setData] = useState<SourceData | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  // Sequence guard: only the most recent request may mutate state, so a
  // slow response for a previously opened source can never overwrite
  // the one now on screen.
  const loadTokenRef = useRef(0);

  const reload = useCallback(
    async (options?: { silent?: boolean }) => {
      const token = ++loadTokenRef.current;
      const silent = options?.silent === true;
      if (!silent) {
        setLoading(true);
        setError(null);
      }
      try {
        const source = await getRegulatorySource(auth, sourceId);
        if (token !== loadTokenRef.current) return;
        const [artifacts, jobs, candidates, flags] = await Promise.all([
          listSourceArtifacts(auth, sourceId),
          listSourceJobs(auth, sourceId),
          listSourceCandidates(auth, sourceId),
          listSourceGovernanceFlags(auth, sourceId),
        ]);
        if (token !== loadTokenRef.current) return;
        setData({
          source,
          artifacts: artifacts.items,
          jobs: jobs.items,
          candidates: candidates.items,
          flags: flags.items,
        });
        setError(null);
      } catch (caught) {
        if (token !== loadTokenRef.current) return;
        // Keep the last known snapshot but mark it stale after any failed refresh.
        setError(caught);
      } finally {
        if (!silent && token === loadTokenRef.current) setLoading(false);
      }
    },
    [auth, sourceId],
  );

  // Opening a different source starts clean, so a previous source's data
  // is never shown under the new one's title.
  useEffect(() => {
    setData(null);
    void reload();
  }, [reload]);

  const progress = useMemo(
    () => (data ? deriveSourceProgress(data) : null),
    [data],
  );
  const inFlight = progress?.inFlight ?? false;

  // Keep the page honest while the worker runs: poll quietly, only while
  // a job is in flight and the tab is visible.
  useEffect(() => {
    if (!inFlight) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void reload({ silent: true });
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [inFlight, reload]);

  // /regulatory/:sourceId/:tab — the segment after the source id.
  const activeTab = location.pathname.split("/")[3] as SourceTab | undefined;

  // On narrow screens the tab strip scrolls sideways; keep the open tab visible.
  useEffect(() => {
    document
      .querySelector(".reg-tab--active")
      ?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [activeTab, data]);

  const registeredTitle =
    (location.state as { registered?: string } | null)?.registered ?? null;

  const tabs: { tab: SourceTab; label: string; count?: number }[] = data
    ? [
        { tab: "documents", label: "Documents", count: data.artifacts.length },
        { tab: "ingestion", label: "Ingestion", count: documentJobs(data.jobs).length },
        { tab: "candidates", label: "Candidates", count: data.candidates.length },
        { tab: "governance", label: "Governance", count: data.flags.length },
        { tab: "details", label: "Details" },
      ]
    : [];

  const context: SourceContextValue | null = data
    ? { auth, sourceId, ...data, loading, refreshError: error, reload }
    : null;

  return (
    <div className="reg-source">
      <nav aria-label="Breadcrumb" className="reg-crumbs">
        <Link to={REGULATORY_BASE}>Regulatory sources</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{data?.source.title ?? "Source"}</span>
      </nav>

      {loading && !data ? <LoadingState text="Loading source…" /> : null}
      {error ? <ErrorNotice error={error} onRetry={() => void reload()} /> : null}

      {data && progress && context ? (
        <>
          {registeredTitle ? (
            <p className="reg-banner" role="status">
              Source “{registeredTitle}” registered. Next, upload the original
              regulatory document.
            </p>
          ) : null}

          <header className="reg-source-head">
            <div>
              <h1 className="reg-title">{data.source.title}</h1>
              <p className="muted">
                {data.source.jurisdiction} · version {data.source.version ?? "—"}
              </p>
            </div>
            <StatusBadge value={data.source.status} tone={tone(data.source.status)} />
          </header>

          <SourceProgress steps={progress.steps} />
          <NextActionCard next={progress.next} sourceId={sourceId} activeTab={activeTab} />

          <nav aria-label="Source sections" className="reg-tabs">
            {tabs.map(({ tab, label, count }) => (
              <NavLink
                key={tab}
                to={sourcePath(sourceId, tab)}
                className={({ isActive }) => `reg-tab${isActive ? " reg-tab--active" : ""}`}
              >
                {label}
                {count !== undefined ? (
                  <span className="reg-tab-count">{count}</span>
                ) : null}
              </NavLink>
            ))}
          </nav>

          <div className="reg-panel">
            <Outlet context={context} />
          </div>
        </>
      ) : null}
    </div>
  );
}
