import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ThemeProvider } from "../../theme/theme";
import { NewShipmentPage } from "./NewShipmentPage";
import { listShipments } from "../../lib/shipments";
import type { WorkflowRecord } from "../../types/api";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: null,
  state: "created",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: [],
};

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

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

function renderPage() {
  stubMatchMedia();
  render(
    <MemoryRouter initialEntries={["/start"]}>
      <AuthProvider initial={{ devTenantId: "22222222-2222-2222-2222-222222222222" }}>
        <WorkflowProvider>
          <ThemeProvider>
            <Routes>
              <Route path="/start" element={<NewShipmentPage />} />
              <Route path="/dashboard" element={<div>Dashboard</div>} />
              <Route path="/workspace" element={<div>Workspace</div>} />
              <Route path="/session" element={<div>Session</div>} />
            </Routes>
          </ThemeProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("What are you exporting?"), "Cocoa beans");
  await user.type(screen.getByLabelText("Where is it going?"), "Netherlands");
  await user.type(screen.getByLabelText("Where is it leaving from?"), "Nigeria");
}

describe("NewShipmentPage", () => {
  it("opens with product and destination first, never technical identifiers", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: "Start a new shipment", level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Tell us what you’re exporting and where it’s going\./),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("What are you exporting?")).toBeInTheDocument();
    expect(screen.getByLabelText("Where is it going?")).toBeInTheDocument();
    expect(screen.getByText(/no port needed to begin/i)).toBeInTheDocument();
    expect(screen.queryByLabelText("Port", { exact: true })).toBeNull();
    expect(screen.queryByLabelText("Case ID")).toBeNull();
    expect(screen.queryByLabelText("Shipment ID")).toBeNull();
    expect(screen.getByRole("button", { name: "Continue" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to dashboard/i })).toBeInTheDocument();
  });

  it("renders only real follow-up fields, nothing invented", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Shipment details" })).toBeInTheDocument();
    for (const label of [
      "Where is it leaving from?",
      "Quantity (optional)",
      "Unit (optional)",
      "Shipment date (optional)",
    ]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    for (const unknown of [
      "I don’t know the quantity yet",
      "I don’t know the unit yet",
      "I don’t know the date yet",
    ]) {
      expect(screen.getByRole("checkbox", { name: unknown })).toBeInTheDocument();
    }
  });

  it("validates each required field in plain language with focus", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Tell us what you’re exporting.")).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByLabelText("What are you exporting?"));
    expect(screen.getByLabelText("What are you exporting?")).toHaveAttribute("aria-invalid", "true");

    await user.type(screen.getByLabelText("What are you exporting?"), "Cocoa beans");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Choose a destination country.")).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByLabelText("Where is it going?"));
  });

  it("keeps unknown explicit and lets optional work continue", async () => {
    const user = userEvent.setup();
    renderPage();
    const unknownQuantity = screen.getByRole("checkbox", { name: "I don’t know the quantity yet" });
    await user.click(unknownQuantity);
    expect(unknownQuantity).toBeChecked();
    const quantity = screen.getByLabelText("Quantity (optional)");
    expect(quantity).toBeDisabled();
    expect(quantity).toHaveValue("");
  });

  it("generates identifiers behind the form and remembers the shipment", async () => {
    const spy = vi.fn(async () =>
      new Response(
        JSON.stringify({
          workflow: RECORD,
          summary: { workflow_id: RECORD.id, state: "created" },
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", spy);
    const user = userEvent.setup();
    renderPage();
    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(screen.getByText("Workspace")).toBeInTheDocument());
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/compliance/workflows/start");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["case_id"]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(body["shipment_id"]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(body).not.toHaveProperty("product");
    const remembered = listShipments();
    expect(remembered).toHaveLength(1);
    expect(remembered[0].profile.product).toBe("Cocoa beans");
  });

  it("explains role-based denial without inventing meaning", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ error: { code: "permission_denied", message: "No." } }), {
          status: 403,
        }),
      ),
    );
    const user = userEvent.setup();
    renderPage();
    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText(/workspace owner/i)).toBeInTheDocument();
  });

  it("preserves entered information when the request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );
    const user = userEvent.setup();
    renderPage();
    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByLabelText("What are you exporting?")).toHaveValue("Cocoa beans");
    expect(screen.getByLabelText("Where is it going?")).toHaveValue("Netherlands");
  });

  it("shows real progress while creating, then navigates", async () => {
    let resolveFetch!: (response: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = resolve;
          }),
      ),
    );
    const user = userEvent.setup();
    renderPage();
    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/creating your shipment/i);
    resolveFetch(
      new Response(JSON.stringify({ workflow: RECORD, summary: {} }), { status: 201 }),
    );
    await waitFor(() => expect(screen.getByText("Workspace")).toBeInTheDocument());
  });

  it("navigates back to the dashboard without losing the shell", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /back to dashboard/i }));
    expect(await screen.findByText("Dashboard")).toBeInTheDocument();
  });

  it("suggests previously used products from this device, never invented ones", () => {
    sessionStorage.setItem(
      "xportra.shipments.v1",
      JSON.stringify([
        {
          caseId: "case-cashew",
          shipmentId: null,
          profile: {
            product: "Cashew nuts",
            origin: "Nigeria",
            destination: "India",
            quantity: "",
            unit: "",
            shipmentDate: "",
          },
          record: RECORD,
        },
      ]),
    );
    renderPage();
    const list = document.querySelector("datalist#past-products");
    expect(list).not.toBeNull();
    expect(list!.querySelector("option[value='Cashew nuts']")).not.toBeNull();
    // Free text stays free: no classification claims anywhere.
    expect(screen.getByRole("main").textContent).not.toMatch(/classified|AI suggests/i);
  });
});

