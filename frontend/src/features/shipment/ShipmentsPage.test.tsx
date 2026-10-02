import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ThemeProvider } from "../../theme/theme";
import { AuthenticatedShell } from "../../shell/AuthenticatedShell";
import { ShipmentsPage } from "./ShipmentsPage";
import { rememberShipment, type ShipmentEntry } from "../../lib/shipments";
import type { WorkflowRecord } from "../../types/api";

/**
 * Archive page contract (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * Entries are remembered through the real
 * device registry; fixtures are test-only.
 * One search field plus four chips filter a
 * grouped worklist (Active / Incomplete /
 * Completed) sharing the dashboard row
 * language — no tables, no cards.
 */

function workflow(caseId: string, state: string, extra?: Partial<WorkflowRecord>): WorkflowRecord {
  return {
    id: `id-${caseId}`,
    tenant_id: "tenant-1",
    case_id: caseId,
    shipment_id: null,
    state,
    rounds: [],
    supplied_evidence_ids: [],
    open_requirements: [],
    ...extra,
  };
}

function seedEntry(
  caseId: string,
  product: string,
  destination: string,
  state: string,
  extra?: Partial<WorkflowRecord>,
): ShipmentEntry {
  const record = workflow(caseId, state, extra);
  return {
    caseId,
    shipmentId: null,
    profile: { product, origin: "Lagos", destination, quantity: "", unit: "", shipmentDate: "" },
    record,
  };
}

function seed(entries: ShipmentEntry[]) {
  for (const entry of entries) {
    rememberShipment(entry);
  }
}

function stubMatchMedia() {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

function renderPage() {
  stubMatchMedia();
  render(
    <MemoryRouter initialEntries={["/shipments"]}>
      <AuthProvider initial={{ token: "test-token" }}>
        <WorkflowProvider>
          <ThemeProvider>
            <Routes>
              <Route
                path="/shipments"
                element={
                  <AuthenticatedShell crumbs={[{ label: "View Shipments" }]}>
                    <ShipmentsPage />
                  </AuthenticatedShell>
                }
              />
              <Route path="/shipments/:caseId" element={<div>Workspace stub</div>} />
              <Route path="/shipments/:caseId/report" element={<div>Historical report stub</div>} />
              <Route path="/start" element={<div>Start stub</div>} />
            </Routes>
          </ThemeProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("ShipmentsPage archive", () => {
  it("titles the archive and explains the empty list", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Your shipments", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "You don’t have any shipments yet." })).toBeInTheDocument();
    const actions = screen.getAllByRole("link", { name: "New shipment" });
    expect(actions.length).toBeGreaterThan(0);
    for (const action of actions) {
      expect(action).toHaveAttribute("href", "/start");
    }
  });

  it("groups active before incomplete before completed with translated statuses", () => {
    seed([
      seedEntry("case-done", "Cocoa", "Rotterdam", "assessment_package_ready"),
      seedEntry("case-new", "Sesame", "Accra", "created"),
      seedEntry("case-busy", "Ginger", "Canada", "evidence_pending"),
    ]);
    renderPage();
    const active = screen.getByRole("heading", { name: "Active" });
    const incomplete = screen.getByRole("heading", { name: "Incomplete" });
    const completed = screen.getByRole("heading", { name: "Completed" });
    expect(active.compareDocumentPosition(incomplete) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(incomplete.compareDocumentPosition(completed) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(active.closest("section") as HTMLElement).getByRole("link", { name: "Ginger" })).toBeInTheDocument();
    expect(within(incomplete.closest("section") as HTMLElement).getByRole("link", { name: "Sesame" })).toBeInTheDocument();
    const completedSection = within(completed.closest("section") as HTMLElement);
    expect(completedSection.getByRole("link", { name: "Cocoa" })).toBeInTheDocument();
    expect(completedSection.getByText("Completed", { selector: "span.xb-row__state" })).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(main.querySelector("table")).toBeNull();
    expect(main.querySelector(".xb-card, .xb-req-card")).toBeNull();
    expect(main.textContent).not.toContain("assessment_package_ready");
  });

  it("searches and chips, then clears back to the full archive", async () => {
    seed([
      seedEntry("case-1", "Cocoa", "Rotterdam", "created"),
      seedEntry("case-2", "Sesame", "Accra", "created"),
    ]);
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText("Search by product or destination"), "sesame");
    expect(screen.getByRole("status")).toHaveTextContent("1 shipment");
    expect(screen.queryByRole("link", { name: "Cocoa" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Completed" }));
    expect(screen.getByRole("status")).toHaveTextContent("No shipments match your search.");
    expect(screen.getByRole("heading", { name: "No shipments match your search." })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear search and filters" }));
    expect(screen.getByRole("status")).toHaveTextContent("2 shipments");
  });

  it("opens active shipments into the workspace mechanism", async () => {
    seed([seedEntry("case-1", "Cocoa", "Rotterdam", "created")]);
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Workspace stub")).toBeInTheDocument();
  });

  it("opens completed shipments as historical reports, never workspaces", async () => {
    seed([seedEntry("case-done", "Cocoa", "Rotterdam", "assessment_package_ready")]);
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "View report" }));
    expect(await screen.findByText("Historical report stub")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continue" })).toBeNull();
    expect(screen.queryByRole("button", { name: /edit|reopen|finalize|upload|verify/i })).toBeNull();
  });

  it("forgets a shipment without touching the backend", async () => {
    const spy = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", spy);
    seed([seedEntry("case-1", "Cocoa", "Rotterdam", "created")]);
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Forget Cocoa · Lagos → Rotterdam" }));
    expect(
      screen.getByRole("heading", { name: "You don’t have any shipments yet." }),
    ).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("introduces no analytics, scores, or technical vocabulary", () => {
    seed([seedEntry("case-1", "Cocoa", "Rotterdam", "created")]);
    renderPage();
    const main = screen.getByRole("main");
    expect(main.textContent).not.toMatch(/%|score|Run Compliance|AI insights/i);
    for (const name of ["Documents", "Requirements", "Evidence", "Assessment"]) {
      expect(screen.queryByRole("link", { name })).toBeNull();
    }
  });
});
