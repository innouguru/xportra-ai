import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import type { WorkflowRecord } from "../../types/api";
import { AskXportraButton } from "./AskXportraButton";
import { ConversationPanel } from "./ConversationPanel";
import { ConversationProvider } from "./ConversationContext";

const RECORD: WorkflowRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  case_id: "33333333-3333-3333-3333-333333333333",
  shipment_id: "abcdef12-3456-7890-abcd-ef1234567890",
  state: "evidence_pending",
  rounds: [],
  supplied_evidence_ids: [],
  open_requirements: ["44444444-4444-4444-4444-444444444444"],
};

const CONVERSATION_ID = "99999999-9999-9999-9999-999999999999";

function groundedAnswer(overrides: Record<string, unknown> = {}) {
  return {
    conversation_id: CONVERSATION_ID,
    mode: "shipment_aware",
    intent: "summarize_shipment_state",
    status: "grounded",
    summary_text: "Two open requirements need information.",
    shipment_references: [
      { kind: "workflow", id: RECORD.id },
      { kind: "requirement", id: "44444444-4444-4444-4444-444444444444" },
    ],
    citations: [
      {
        label: "[E1]",
        rank_position: 1,
        evidence: {
          chunk_id: "55555555-5555-5555-5555-555555555555",
          document_id: "66666666-6666-6666-6666-666666666666",
          chunk_index: 0,
          source_id: "SONCAP",
          source_type: "regulation",
          source_location: "Section 4",
          document_version: null,
          content_fingerprint: "fp",
        },
      },
    ],
    refusal_reason: null,
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderPanel(seed?: Parameters<typeof AskXportraButton>[0]["seed"]) {
  sessionStorage.setItem("xportra.workflow-record.v1", JSON.stringify(RECORD));
  render(
    <MemoryRouter>
      <AuthProvider initial={{ devTenantId: RECORD.tenant_id }}>
        <WorkflowProvider>
          <ConversationProvider>
            <AskXportraButton seed={seed} />
            <ConversationPanel />
          </ConversationProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function stubMessages(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  const calls: Array<{ url: string; body: Record<string, unknown> }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (typeof url === "string" && url.endsWith("/conversations/messages")) {
        calls.push({ url, body: JSON.parse(String(init?.body)) });
      }
      return handler(url, init);
    }),
  );
  return calls;
}

function okAnswer(overrides: Record<string, unknown> = {}) {
  return stubMessages(() => new Response(JSON.stringify(groundedAnswer(overrides)), { status: 200 }));
}

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Ask Xportra" }));
  await screen.findByRole("dialog");
}

async function ask(user: ReturnType<typeof userEvent.setup>, text: string) {
  const dialog = screen.getByRole("dialog");
  await user.type(within(dialog).getByLabelText(/Ask about/), text);
  await user.click(within(dialog).getByRole("button", { name: /^Ask Xportra$|^Asking…$/ }));
}

describe("ConversationPanel", () => {
  it("renders the Ask Xportra entry button", () => {
    renderPanel();
    expect(screen.getByRole("button", { name: "Ask Xportra" })).toBeInTheDocument();
  });

  it("opens the panel and closes it from the Close control", async () => {
    const user = userEvent.setup();
    renderPanel();
    expect(screen.queryByRole("dialog")).toBeNull();
    await openPanel(user);
    expect(screen.getByRole("heading", { name: "Shipment assistant" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close conversation panel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("closes on Escape and returns focus to the entry button", async () => {
    const user = userEvent.setup();
    renderPanel();
    const entry = screen.getByRole("button", { name: "Ask Xportra" });
    await user.click(entry);
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(entry).toHaveFocus();
  });

  it("displays the shipment in context without workflow IDs", async () => {
    const user = userEvent.setup();
    renderPanel();
    await openPanel(user);
    expect(screen.getByText(/Shipment:/)).toBeInTheDocument();
    expect(screen.getByText(/abcdef12…/)).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).queryByText(RECORD.id)).toBeNull();
  });

  it("sends permitted shipment context and no tenant identity", async () => {
    const user = userEvent.setup();
    const calls = okAnswer();
    renderPanel({
      intent: "explain_requirement_state",
      requirementId: "44444444-4444-4444-4444-444444444444",
      focus: "requirement",
    });
    await openPanel(user);
    await ask(user, "Why is this requirement still open?");
    await waitFor(() => expect(calls).toHaveLength(1));
    const body = calls[0].body;
    expect(body["mode"]).toBe("shipment_aware");
    expect(body["intent"]).toBe("explain_requirement_state");
    expect(body["requirement_id"]).toBe("44444444-4444-4444-4444-444444444444");
    expect((body["workflow"] as Record<string, unknown>)["id"]).toBe(RECORD.id);
    expect(body).not.toHaveProperty("tenant_id");
    expect(body).not.toHaveProperty("evidence_id");
  });

  it("sends knowledge turns with no shipment context", async () => {
    const user = userEvent.setup();
    const calls = okAnswer({ mode: "knowledge", shipment_references: [] });
    renderPanel();
    await openPanel(user);
    await user.click(screen.getByLabelText(/Regulatory knowledge/));
    await ask(user, "What documents are normally required?");
    await waitFor(() => expect(calls).toHaveLength(1));
    const body = calls[0].body;
    expect(body["mode"]).toBe("knowledge");
    expect(body["intent"]).toBe("answer_regulatory_question");
    expect(body["information_need"]).toBe("What documents are normally required?");
    expect(body).not.toHaveProperty("workflow");
    expect(body).not.toHaveProperty("requirement_id");
    expect(body).not.toHaveProperty("evidence_id");
  });

  it("renders the user message and the grounded assistant answer", async () => {
    const user = userEvent.setup();
    okAnswer();
    renderPanel();
    await openPanel(user);
    await ask(user, "What still needs my attention?");
    expect(await screen.findByText("What still needs my attention?")).toBeInTheDocument();
    expect(await screen.findByText("Two open requirements need information.")).toBeInTheDocument();
    expect(screen.getByText("grounded")).toBeInTheDocument();
    expect(screen.getByText("Xportra record")).toBeInTheDocument();
    expect(screen.getByText("Explanation")).toBeInTheDocument();
    expect(screen.getByText("[E1]")).toBeInTheDocument();
    expect(screen.getByText(/SONCAP/)).toBeInTheDocument();
  });

  it("shows a loading state while waiting", async () => {
    const user = userEvent.setup();
    let release = () => {};
    stubMessages(
      () =>
        new Promise<Response>((resolve) => {
          release = () =>
            resolve(new Response(JSON.stringify(groundedAnswer()), { status: 200 }));
        }),
    );
    renderPanel();
    await openPanel(user);
    await ask(user, "Summarize, please.");
    expect(await screen.findByText("Asking Xportra…")).toBeInTheDocument();
    release();
    await screen.findByText("Two open requirements need information.");
  });

  it("renders API errors without backend internals", async () => {
    const user = userEvent.setup();
    stubMessages(
      () =>
        new Response(
          JSON.stringify({ error: { code: "stale_analysis", message: "Stale." } }),
          { status: 409 },
        ),
    );
    renderPanel();
    await openPanel(user);
    await ask(user, "Summarize, please.");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A newer analysis exists. Review the latest results first.",
    );
  });

  it("renders unauthorized and forbidden states", async () => {
    const user = userEvent.setup();
    stubMessages(
      () =>
        new Response(
          JSON.stringify({ error: { code: "authentication_required", message: "No." } }),
          { status: 401 },
        ),
    );
    renderPanel();
    await openPanel(user);
    await ask(user, "Summarize, please.");
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign in again");
  });

  it("renders refusals honestly with no fabricated claims", async () => {
    const user = userEvent.setup();
    okAnswer({
      status: "refused_unknown",
      summary_text:
        "The answer could not be established from authoritative shipment state.",
      shipment_references: [],
      citations: [],
      refusal_reason: "No validated retrieval available.",
    });
    renderPanel();
    await openPanel(user);
    await ask(user, "Is this shipment compliant?");
    expect(await screen.findByText("refused_unknown")).toBeInTheDocument();
    expect(
      screen.getByText("The answer could not be established from authoritative shipment state."),
    ).toBeInTheDocument();
    expect(screen.getByText(/No validated retrieval available/)).toBeInTheDocument();
  });

  it("notes when a non-refused answer carries no references", async () => {
    const user = userEvent.setup();
    okAnswer({ shipment_references: [], citations: [] });
    renderPanel();
    await openPanel(user);
    await ask(user, "Summarize, please.");
    expect(await screen.findByText("No references returned.")).toBeInTheDocument();
  });

  it("opens from a contextual entry with prefilled question", async () => {
    const user = userEvent.setup();
    okAnswer();
    renderPanel({
      intent: "explain_finding",
      requirementId: "44444444-4444-4444-4444-444444444444",
      suggestedText: "Why was this finding recorded?",
      focus: "finding",
    });
    await openPanel(user);
    expect(screen.getByLabelText(/Ask about/)).toHaveValue("Why was this finding recorded?");
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /^Ask Xportra$/ }));
    await waitFor(() =>
      expect(screen.getByText("Why was this finding recorded?")).toBeInTheDocument(),
    );
    expect(await screen.findByText("Two open requirements need information.")).toBeInTheDocument();
  });

  it("keeps the drawer structure usable on narrow viewports", async () => {
    const user = userEvent.setup();
    renderPanel();
    await openPanel(user);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveClass("conversation-panel");
    expect(document.querySelector(".conversation-overlay")).not.toBeNull();
    expect(document.querySelector(".conversation-messages")).not.toBeNull();
  });

  it("only ever calls the read-only messages route", async () => {
    const user = userEvent.setup();
    const seen: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        seen.push(url);
        return new Response(JSON.stringify(groundedAnswer()), { status: 200 });
      }),
    );
    renderPanel();
    await openPanel(user);
    await ask(user, "Summarize, please.");
    await screen.findByText("Two open requirements need information.");
    expect(seen.length).toBeGreaterThan(0);
    for (const url of seen) {
      expect(url).toMatch(/\/conversations\/messages$/);
    }
  });

  it("exposes labelled controls and live status updates", async () => {
    const user = userEvent.setup();
    renderPanel();
    await openPanel(user);
    await waitFor(() =>
      expect(screen.getByLabelText(/Ask about/)).toHaveFocus(),
    );
    expect(screen.getByLabelText("Question type")).toBeInTheDocument();
    expect(screen.getByRole("log", { name: "Conversation" })).toHaveAttribute(
      "aria-live",
      "polite",
    );
    expect(screen.getByRole("radiogroup", { name: "Conversation mode" })).toBeInTheDocument();
  });
});
