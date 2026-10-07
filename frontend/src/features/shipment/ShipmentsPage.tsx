import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { EmptyState, ErrorState, LoadingState } from "../../primitives/feedback";
import { PageHeader } from "../../primitives/layout";
import { ShipmentWorklistRow } from "../../primitives/shipment";
import { fetchShipmentList } from "../../api/shipments";
import {
  forgetShipment,
  type ShipmentEntry,
} from "../../lib/shipments";
import type { DashboardShipment } from "../dashboard/dashboard";
import {
  EMPTY_FILTER,
  queryArchive,
  type ArchiveFilter,
  type ArchiveStatus,
} from "./shipmentsArchive";
import "./shipments.css";

/**
 * View Shipments archive (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * One search field plus four filter chips
 * (All / Active / Incomplete / Completed),
 * results grouped under quiet Active,
 * Incomplete, and Completed labels in that
 * order. Every row uses the same worklist
 * language as the dashboard; completed rows
 * read dimmer as history. Search covers stored
 * profile text only. Completed shipments open
 * the read-only historical report — never the
 * mutable workspace. Forgetting removes the
 * device entry only and never touches the
 * backend.
 */

type ArchiveLoad =
  | { status: "loading" }
  | { status: "ready"; entries: ShipmentEntry[] }
  | { status: "error" };

const CHIPS: { value: ArchiveStatus; label: string }[] = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "incomplete", label: "Incomplete" },
  { value: "completed", label: "Completed" },
];

function rowName(item: DashboardShipment): string {
  const product = item.entry.profile.product.trim();
  return product || item.title;
}

function rowRoute(item: DashboardShipment): string | undefined {
  const destination = item.entry.profile.destination.trim();
  return destination ? `→ ${destination}` : undefined;
}

export function ShipmentsPage() {
  const auth = useAuth();
  const { setRecord } = useWorkflow();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<ArchiveFilter>(EMPTY_FILTER);
  const [load, setLoad] = useState<ArchiveLoad>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    // Durable archive first: persisted shipments
    // appear even when this device remembers nothing.
    fetchShipmentList(auth)
      .then((entries) => {
        if (!cancelled) {
          setLoad({ status: "ready", entries });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoad({ status: "error" });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reload = () => {
    setLoad({ status: "loading" });
    fetchShipmentList(auth)
      .then((entries) => setLoad({ status: "ready", entries }))
      .catch(() => setLoad({ status: "error" }));
  };

  const entries = load.status === "ready" ? load.entries : [];
  const results = useMemo(() => queryArchive(entries, filter), [entries, filter]);
  const filtered = filter.query.trim() !== "" || filter.status !== "all";

  const groups = useMemo(() => {
    const stateOf = (item: (typeof results)[number]) => item.entry.record?.state ?? null;
    const active = results.filter(
      (item) => !item.complete && stateOf(item) !== null && stateOf(item) !== "created" && stateOf(item) !== "information_provided",
    );
    const incomplete = results.filter(
      (item) => !item.complete && (stateOf(item) === null || stateOf(item) === "created" || stateOf(item) === "information_provided"),
    );
    const completed = results.filter((item) => item.complete);
    return [
      { key: "active", label: "Active", items: active },
      { key: "incomplete", label: "Incomplete", items: incomplete },
      { key: "completed", label: "Completed", items: completed },
    ].filter((group) => group.items.length > 0);
  }, [results]);

  const open = (item: DashboardShipment) => {
    if (!item.complete) {
      setRecord(item.entry.record);
    }
    navigate(item.action.destination);
  };

  const remove = (item: DashboardShipment) => {
    // Device-local hiding only: the server row is
    // untouched, and the row only stays hidden here.
    forgetShipment(item.entry.caseId, item.entry.shipmentId);
    setLoad((current) =>
      current.status === "ready"
        ? { status: "ready", entries: current.entries.filter((entry) => entry.caseId !== item.entry.caseId) }
        : current,
    );
  };

  return (
    <div>
      <PageHeader
        title="Your shipments"
        actions={
          <Link className="primary-button" to="/start">
            New shipment
          </Link>
        }
      />
      {load.status === "loading" ? <LoadingState text="Loading your shipments…" /> : null}
      {load.status === "error" ? (
        <ErrorState
          title="We couldn’t load your shipments right now."
          message="Your search and filters are kept — please try again."
          onRetry={reload}
        />
      ) : null}
      {load.status === "ready" && entries.length === 0 ? (
        <EmptyState
          title="You don’t have any shipments yet."
          body="Start one to see what it needs."
          action={
            <Link className="primary-button" to="/start">
              New shipment
            </Link>
          }
        />
      ) : null}
      {load.status === "ready" && entries.length > 0 ? (
        <>
          <form
            className="xb-archive-toolbar"
            role="search"
            aria-label="Search and filter shipments"
            onSubmit={(event) => event.preventDefault()}
          >
            <label className="xb-archive-search">
              <span className="xb-archive-search__label">Search shipments</span>
              <input
                className="xb-input"
                type="search"
                autoComplete="off"
                value={filter.query}
                onChange={(event) => setFilter((current) => ({ ...current, query: event.target.value }))}
                placeholder="Search by product or destination"
              />
            </label>
            <div className="xb-archive-chips" role="group" aria-label="Filter by status">
              {CHIPS.map((chip) => (
                <button
                  key={chip.value}
                  type="button"
                  className={filter.status === chip.value ? "xb-chip xb-chip--active" : "xb-chip"}
                  aria-pressed={filter.status === chip.value}
                  onClick={() => setFilter((current) => ({ ...current, status: chip.value }))}
                >
                  {chip.label}
                </button>
              ))}
            </div>
            {filtered ? (
              <button type="button" className="secondary-button" onClick={() => setFilter(EMPTY_FILTER)}>
                Clear
              </button>
            ) : null}
          </form>
          <p role="status" className="xb-ws-muted">
            {results.length === 0
              ? "No shipments match your search."
              : `${results.length} shipment${results.length === 1 ? "" : "s"}`}
          </p>
          {results.length === 0 ? (
            <EmptyState
              title="No shipments match your search."
              body="Try a different product, destination, or filter — or clear everything to see the full archive."
              action={
                <button type="button" className="secondary-button" onClick={() => setFilter(EMPTY_FILTER)}>
                  Clear search and filters
                </button>
              }
            />
          ) : (
            groups.map((group) => (
              <section key={group.key} aria-labelledby={`archive-group-${group.key}`}>
                <h2 className="xb-archive-group-label" id={`archive-group-${group.key}`}>
                  {group.label}
                </h2>
                <ul className="xb-worklist">
                  {group.items.map((item) => (
                    <ShipmentWorklistRow
                      key={item.entry.caseId}
                      name={rowName(item)}
                      route={rowRoute(item)}
                      state={item.attention ?? item.statusLabel}
                      tone={item.tone}
                      href={item.action.destination}
                      actionLabel={item.action.label}
                      onSelect={() => open(item)}
                      dimmed={item.complete}
                      secondaryAction={{
                        label: "Forget",
                        ariaLabel: `Forget ${item.title}`,
                        onSelect: () => remove(item),
                      }}
                    />
                  ))}
                </ul>
              </section>
            ))
          )}
        </>
      ) : null}
    </div>
  );
}
