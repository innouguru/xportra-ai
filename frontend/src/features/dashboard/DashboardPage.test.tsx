import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ThemeProvider } from "../../theme/theme";
import type { ShipmentEntry } from "../../lib/shipments";
import type { WorkflowRecord } from "../../types/api";
import { DashboardPage } from "./DashboardPage";

/**
 * Dashboard page contract (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * "Your shipments" is a resumption workspace:
 * one attention block, one recent worklist, one
 * "View all" link — no greeting, no counts, no
 * cards, no analytics. Entries arrive through the
 * durable server list (`api/shipments`); fixtures
 * are test-only display data served by the mocked
 * fetch. The error path rejects the fetch once —
 * the production code path is a genuine network
 * failure with retry.
 */

vi.mock("../../api/shipments", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/shipments")>();
  return { ...actual, fetchShipmentList: (...args: unknown[]) => mockedFetch(...args) };
});

const { mockedFetch } = vi.hoisted(() => {
  return {
    mockedFetch: vi.fn() as unknown as Mock<(...args: unknown[]) => Promise<unknown>>,
  };
});

function record(state: string, extra?: Partial<WorkflowRecord>): WorkflowRecord {
  return {
    id: `id-${state}`,
    tenant_id: "22222222-2222-2222-2222-222222222222",
    case_id: `case-${state}`,
    shipment_id: null,
    state,
    rounds: [],
    supplied_evidence_ids: [],
    open_requirements: [],
    ...extra,
  };
}

function seededEntry(product: string, state: string, extra?: Partial<WorkflowRecord>): ShipmentEntry {
  const workflow = record(state, { case_id: `case-${product}`, ...extra });
  return {
    caseId: workflow.case_id,
    shipmentId: `ship-${product}`,
    profile: { product, origin: "Lagos", destination: "Rotterdam", quantity: "", unit: "", shipmentDate: "" },
    record: workflow,
  };
}

function serve(entries: ShipmentEntry[]) {
  mockedFetch.mockResolvedValue(entries);
}

function renderPage() {
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
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AuthProvider initial={{ token: "test-token" }}>
        <WorkflowProvider>
          <ThemeProvider>
            <DashboardPage />
          </ThemeProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
  mockedFetch.mockReset();
});

describe("dashboard header", () => {
  it("titles the page and offers New shipment without dashboard chrome", async () => {
    serve([seededEntry("Cocoa", "created"), seededEntry("Sesame", "evidence_pending")]);
    renderPage();
    expect(await screen.findByRole("heading", { name: "Your shipments", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New shipment" })).toHaveAttribute("href", "/start");
    const main = screen.getByRole("main");
    expect(main.textContent).not.toMatch(/Good (morning|afternoon|evening)/);
    expect(main.textContent).not.toMatch(/active shipments/);
  });
});

describe("attention and recent sections", () => {
  it("places attention above recent with plain-English statuses", async () => {
    serve([
      seededEntry("Cocoa", "created"),
      seededEntry("Sesame", "applicability_determined"),
      seededEntry("Ginger", "assessment_package_ready"),
    ]);
    renderPage();
    const attention = await screen.findByRole("heading", { name: "Needs your attention" });
    const recent = screen.getByRole("heading", { name: "Recent shipments" });
    expect(attention.compareDocumentPosition(recent) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText(/Incomplete — continue where you left off/)).toBeInTheDocument();
    const block = attention.closest("section");
    expect(block).not.toBeNull();
    expect(within(block as HTMLElement).getByText("Cocoa")).toBeInTheDocument();
    expect(within(block as HTMLElement).getByRole("button", { name: "Continue" })).toBeInTheDocument();
    const main = screen.getByRole("main");
    for (const technical of ["evidence_pending", "review_required", "applicability_determined"]) {
      expect(main.textContent).not.toContain(technical);
    }
  });

  it("hides the attention block when nothing needs attention", async () => {
    serve([seededEntry("Sesame", "applicability_determined")]);
    renderPage();
    await screen.findByRole("heading", { name: "Recent shipments" });
    expect(screen.queryByRole("heading", { name: "Needs your attention" })).toBeNull();
  });

  it("limits recent shipments to five worklist rows", async () => {
    serve([
      seededEntry("One", "evidence_pending", { supplied_evidence_ids: ["e1"] }),
      seededEntry("Two", "evidence_pending", { supplied_evidence_ids: ["e2"] }),
      seededEntry("Three", "applicability_determined"),
      seededEntry("Four", "evidence_pending", { supplied_evidence_ids: ["e4"] }),
      seededEntry("Five", "applicability_determined"),
      seededEntry("Six", "evidence_pending", { supplied_evidence_ids: ["e6"] }),
    ]);
    renderPage();
    const recent = await screen.findByRole("heading", { name: "Recent shipments" });
    const section = recent.closest("section");
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getAllByRole("link", { name: /^(One|Two|Three|Four|Five|Six)$/ })).toHaveLength(5);
    expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute("href", "/shipments");
  });

  it("shows server shipments with an empty device registry", async () => {
    window.sessionStorage.clear();
    serve([seededEntry("Cocoa", "created")]);
    renderPage();
    expect(await screen.findByText("Cocoa")).toBeInTheDocument();
  });
});

describe("empty, loading, and error states", () => {
  it("welcomes first-time users with a direction-giving empty state", async () => {
    serve([]);
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "You don't have any shipments yet." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Start one to see what it needs.")).toBeInTheDocument();
    const actions = screen.getAllByRole("link", { name: "New shipment" });
    expect(actions).toHaveLength(2);
    for (const action of actions) {
      expect(action).toHaveAttribute("href", "/start");
    }
  });

  it("explains load failures plainly with a working retry", async () => {
    mockedFetch.mockRejectedValueOnce(new Error("network down"));
    mockedFetch.mockResolvedValue([seededEntry("Cocoa", "created")]);
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't load your shipments right now.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Needs your attention" })).toBeInTheDocument();
  });
});

describe("dashboard scope pins", () => {
  it("introduces no analytics, charts, cards, or workflow navigation", async () => {
    serve([seededEntry("Cocoa", "created")]);
    renderPage();
    await screen.findByText("Cocoa");
    const main = screen.getByRole("main");
    expect(main.querySelector("svg, canvas")).toBeNull();
    expect(main.querySelector(".xb-card, .xb-card-grid")).toBeNull();
    expect(main.textContent).not.toMatch(/%|AI insights|trend|score/i);
    for (const name of ["Documents", "Requirements", "Evidence", "Assessment"]) {
      expect(screen.queryByRole("link", { name })).toBeNull();
    }
  });
});
