import { describe, expect, it } from "vitest";
import {
  KNOWLEDGE_INTENTS,
  SHIPMENT_INTENTS,
  conversationStatusTone,
  isUuidLike,
  shipmentContextLabel,
  suggestedPrompts,
} from "./conversation";

describe("conversation presentation helpers", () => {
  it("keeps shipment and knowledge intents separated", () => {
    expect(SHIPMENT_INTENTS.map((option) => option.intent)).toContain(
      "summarize_shipment_state",
    );
    expect(KNOWLEDGE_INTENTS.map((option) => option.intent)).toEqual([
      "answer_regulatory_question",
    ]);
  });

  it("tones response statuses without verdicts", () => {
    expect(conversationStatusTone("grounded")).toBe("info");
    expect(conversationStatusTone("partial")).toBe("attention");
    expect(conversationStatusTone("refused_unknown")).toBe("attention");
  });

  it("suggests prompts without asserting facts", () => {
    for (const mode of ["shipment_aware", "knowledge"] as const) {
      for (const focus of [
        "shipment",
        "requirement",
        "gap",
        "finding",
        "evidence",
      ] as const) {
        for (const prompt of suggestedPrompts(mode, focus)) {
          expect(prompt).not.toMatch(/compliant|approved|certified|guaranteed/i);
        }
      }
    }
    expect(suggestedPrompts("knowledge", "shipment")).toHaveLength(3);
  });

  it("validates UUID text for entry-point guards", () => {
    expect(isUuidLike("11111111-1111-1111-1111-111111111111")).toBe(true);
    expect(isUuidLike("REQ-42")).toBe(false);
    expect(isUuidLike("")).toBe(false);
  });

  it("labels shipment context without workflow IDs", () => {
    const label = shipmentContextLabel("abcdef12-3456-7890-abcd-ef1234567890", "Evidence pending");
    expect(label).toContain("abcdef12…");
    expect(label).toContain("Evidence pending");
    expect(label).not.toContain("abcdef12-3456-7890-abcd-ef1234567890");
  });
});
