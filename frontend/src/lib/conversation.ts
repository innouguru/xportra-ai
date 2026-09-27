/**
 * Pure presentation helpers for conversation.
 *
 * Backend vocabularies (modes, intents, response
 * statuses) render verbatim; tones only aid scanning.
 * Suggested questions are prompts only — they assert
 * nothing about any actual requirement, regulation, or
 * shipment. No compliance logic lives here.
 */

import type { ConversationIntent, ConversationMode } from "../types/api";

export const CONVERSATION_MODES: ConversationMode[] = [
  "shipment_aware",
  "knowledge",
];

export function conversationModeLabel(mode: ConversationMode): string {
  return mode === "knowledge" ? "Regulatory knowledge" : "This shipment";
}

export interface IntentOption {
  intent: ConversationIntent;
  label: string;
  hint: string;
}

export const SHIPMENT_INTENTS: IntentOption[] = [
  {
    intent: "summarize_shipment_state",
    label: "Summarize this shipment",
    hint: "Current state, rounds, supplied evidence, open items.",
  },
  {
    intent: "explain_requirement_state",
    label: "Explain a requirement",
    hint: "Why one requirement is open and what it needs.",
  },
  {
    intent: "explain_evidence_gaps",
    label: "Explain evidence gaps",
    hint: "What information is still missing.",
  },
  {
    intent: "explain_finding",
    label: "Explain a finding",
    hint: "Why a recorded finding exists.",
  },
  {
    intent: "answer_regulatory_question",
    label: "Ask a regulatory question",
    hint: "Grounded in validated retrieval, with citations.",
  },
];

export const KNOWLEDGE_INTENTS: IntentOption[] = [
  {
    intent: "answer_regulatory_question",
    label: "Ask a regulatory question",
    hint: "No shipment context is sent in this mode.",
  },
];

/** Response statuses render verbatim; refusal draws attention. */
export function conversationStatusTone(
  status: string,
): "info" | "muted" | "attention" | "neutral" {
  if (status === "grounded") return "info";
  if (status === "partial") return "attention";
  if (status === "refused_unknown") return "attention";
  return "neutral";
}

/** Suggested prompts per entry context. Prompts only. */
export function suggestedPrompts(
  mode: ConversationMode,
  focus: "shipment" | "requirement" | "gap" | "finding" | "evidence",
): string[] {
  if (mode === "knowledge") {
    return [
      "What documents are normally required for this export?",
      "Explain this requirement.",
      "What does this regulation require?",
    ];
  }
  switch (focus) {
    case "requirement":
      return [
        "Why is this requirement still open?",
        "What should I provide next?",
        "Explain the open requirements.",
      ];
    case "gap":
      return [
        "What evidence is missing?",
        "What should I provide next?",
        "Which requirements still need information?",
      ];
    case "finding":
      return [
        "Why was this finding recorded?",
        "Why is this finding unresolved?",
        "What changed after the last analysis?",
      ];
    case "evidence":
      return [
        "What evidence is missing?",
        "What should I provide next?",
        "Explain the open requirements.",
      ];
    case "shipment":
    default:
      return [
        "What still needs my attention?",
        "What evidence is missing?",
        "Explain the open requirements.",
        "What changed after the last analysis?",
      ];
  }
}

/** True for canonical UUID text (entry-point guard only). */
export function isUuidLike(value: string): boolean {
  return /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(
    value.trim(),
  );
}

/**
 * Human shipment context label. Uses the shipment
 * reference and workflow state — never a workflow ID
 * as the primary label.
 */
export function shipmentContextLabel(
  shipmentId: string | null,
  workflowState: string,
): string {
  const reference = shipmentId ? `${shipmentId.slice(0, 8)}…` : "Unbound shipment";
  return `${reference} · ${workflowState}`;
}
