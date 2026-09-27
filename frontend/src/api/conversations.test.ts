import { describe, expect, it, vi, afterEach } from "vitest";
import { postConversationMessage } from "./conversations";
import type { AuthCredentials } from "./client";

const CREDENTIALS: AuthCredentials = { token: "tok", devTenantId: null };

type FetchCall = [string, RequestInit];

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubJson(body: unknown, status = 200) {
  const spy = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

const ANSWER = {
  conversation_id: "11111111-1111-1111-1111-111111111111",
  mode: "shipment_aware",
  intent: "summarize_shipment_state",
  status: "grounded",
  summary_text: "Three rounds recorded.",
  shipment_references: [{ kind: "workflow", id: "22222222-2222-2222-2222-222222222222" }],
  citations: [],
  refusal_reason: null,
};

describe("conversations API function", () => {
  it("posts one turn to the existing messages route", async () => {
    const spy = stubJson(ANSWER);
    await postConversationMessage(CREDENTIALS, {
      conversation_id: "11111111-1111-1111-1111-111111111111",
      mode: "shipment_aware",
      intent: "summarize_shipment_state",
      user_text: "What still needs my attention?",
      workflow: {
        id: "22222222-2222-2222-2222-222222222222",
        tenant_id: "33333333-3333-3333-3333-333333333333",
        case_id: "44444444-4444-4444-4444-444444444444",
        shipment_id: null,
        state: "evidence_pending",
        rounds: [],
        supplied_evidence_ids: [],
        open_requirements: [],
      },
    });
    const [url, init] = spy.mock.calls[0] as unknown as FetchCall;
    expect(url).toBe("http://localhost:8000/conversations/messages");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["mode"]).toBe("shipment_aware");
    expect(body["intent"]).toBe("summarize_shipment_state");
    expect(body).not.toHaveProperty("tenant_id");
  });

  it("sends knowledge turns without shipment context", async () => {
    const spy = stubJson({ ...ANSWER, mode: "knowledge" });
    await postConversationMessage(CREDENTIALS, {
      conversation_id: "11111111-1111-1111-1111-111111111111",
      mode: "knowledge",
      intent: "answer_regulatory_question",
      user_text: "What documents are normally required?",
      information_need: "What documents are normally required?",
    });
    const [, init] = spy.mock.calls[0] as unknown as FetchCall;
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body["mode"]).toBe("knowledge");
    expect(body).not.toHaveProperty("workflow");
    expect(body).not.toHaveProperty("requirement_id");
    expect(body).not.toHaveProperty("evidence_id");
  });

  it("returns the grounded answer unchanged", async () => {
    stubJson(ANSWER);
    const answer = await postConversationMessage(CREDENTIALS, {
      conversation_id: "11111111-1111-1111-1111-111111111111",
      mode: "shipment_aware",
      intent: "summarize_shipment_state",
      user_text: "Summarize.",
      workflow: null,
    });
    expect(answer.status).toBe("grounded");
    expect(answer.shipment_references).toHaveLength(1);
    expect(answer.refusal_reason).toBeNull();
  });
});
