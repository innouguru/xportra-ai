import { useState } from "react";
import { Link } from "react-router-dom";
import { useWorkflow } from "../../app/WorkflowContext";
import { EmptyState } from "../../components/StatusBits";
import { EvidencePage } from "./EvidencePage";
import { GapsPage } from "./GapsPage";
import { AdditionalEvidencePage } from "./AdditionalEvidencePage";

/**
 * Documents — one home for supplied documents, processing
 * state, information needs, and requested evidence.
 *
 * Tabs compose the existing evidence screens unchanged:
 * upload/processing/download, readiness gaps, and the
 * request/supply loop all keep their backend contracts.
 * The tabs only change how the areas are reached — the
 * underlying domain concepts are untouched.
 */

type DocumentsTab = "documents" | "needed" | "requested";

const TABS: Array<{ id: DocumentsTab; label: string; hint: string }> = [
  {
    id: "documents",
    label: "Documents",
    hint: "Supplied documents, processing state, uploads, downloads.",
  },
  {
    id: "needed",
    label: "Needed",
    hint: "Information the backend reports as still missing.",
  },
  {
    id: "requested",
    label: "Requested",
    hint: "Explicitly requested evidence: request, supply, re-run.",
  },
];

export function DocumentsPage() {
  const { record } = useWorkflow();
  const [tab, setTab] = useState<DocumentsTab>("documents");

  if (!record) {
    return (
      <EmptyState
        title="No active shipment"
        body="Open a compliance case first."
        action={
          <Link className="primary-button" to="/start">
            Start a new shipment
          </Link>
        }
      />
    );
  }

  const select = (next: DocumentsTab) => () => setTab(next);

  const onTabKeyDown = (event: React.KeyboardEvent) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") {
      return;
    }
    event.preventDefault();
    const order = TABS.map((item) => item.id);
    const at = order.indexOf(tab);
    const step = event.key === "ArrowRight" ? 1 : -1;
    const next = order[(at + step + order.length) % order.length];
    setTab(next);
    document.getElementById(`documents-tab-${next}`)?.focus();
  };

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Shipment documents</p>
        <p className="lede">
          Everything the shipment has supplied, what is still processing,
          and what information is still needed — without needing to know
          how Xportra organizes evidence underneath.
        </p>
      </header>
      <div className="filter-chips" role="tablist" aria-label="Document areas">
        {TABS.map((item) => (
          <button
            key={item.id}
            id={`documents-tab-${item.id}`}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            aria-controls={`documents-panel-${item.id}`}
            tabIndex={tab === item.id ? 0 : -1}
            className="chip"
            title={item.hint}
            onClick={select(item.id)}
            onKeyDown={onTabKeyDown}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`documents-panel-${tab}`}
        aria-labelledby={`documents-tab-${tab}`}
      >
        {tab === "documents" ? <EvidencePage /> : null}
        {tab === "needed" ? <GapsPage /> : null}
        {tab === "requested" ? <AdditionalEvidencePage /> : null}
      </div>
    </div>
  );
}
