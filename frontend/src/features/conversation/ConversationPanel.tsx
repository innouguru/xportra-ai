import { useEffect, useId, useRef, useState } from "react";
import { postConversationMessage } from "../../api/conversations";
import { ApiError } from "../../api/client";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { ErrorNotice, Identifier, LoadingState, StatusBadge } from "../../components/StatusBits";
import {
  KNOWLEDGE_INTENTS,
  SHIPMENT_INTENTS,
  conversationStatusTone,
  shipmentContextLabel,
  suggestedPrompts,
  type IntentOption,
} from "../../lib/conversation";
import { workflowStateLabel } from "../../lib/workflow";
import type {
  ConversationIntent,
  ConversationMessageResponse,
  ConversationMode,
} from "../../types/api";
import { useConversation } from "./ConversationContext";
/**
 * Shipment-scoped "Ask Xportra" side panel.
 *
 * One shared surface for every entry point: the panel
 * sends exactly one stateless, read-only turn per
 * submission to `POST /conversations/messages` and
 * renders the grounded answer with its identifier and
 * source references. It cannot mutate, persist, or
 * propose actions — the workflow UI owns every action.
 * Knowledge mode structurally excludes shipment
 * context from the request.
 */

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: ConversationMessageResponse;
}

const DEFAULT_SHIPMENT_INTENT: ConversationIntent = "summarize_shipment_state";
const KNOWLEDGE_INTENT: ConversationIntent = "answer_regulatory_question";

function newConversationId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `conversation-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  }
}

function intentsFor(mode: ConversationMode): IntentOption[] {
  return mode === "knowledge" ? KNOWLEDGE_INTENTS : SHIPMENT_INTENTS;
}

export function ConversationPanel() {
  const auth = useAuth();
  const { record } = useWorkflow();
  const { open, seed, close } = useConversation();
  const [mode, setMode] = useState<ConversationMode>("shipment_aware");
  const [intent, setIntent] = useState<ConversationIntent>(DEFAULT_SHIPMENT_INTENT);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const openerRef = useRef<Element | null>(null);
  const messageCounter = useRef(0);
  const headingId = useId();
  const inputId = useId();
  const intentId = useId();
  const modeGroupId = useId();
  const wasOpen = useRef(false);

  // Reset per opening; capture the opener for focus return.
  useEffect(() => {
    if (open && !wasOpen.current) {
      openerRef.current =
        typeof document !== "undefined" ? document.activeElement : null;
      const preferred = seed.mode ?? (record ? "shipment_aware" : "knowledge");
      const nextMode: ConversationMode =
        preferred === "knowledge" || record ? preferred : "knowledge";
      const options = intentsFor(nextMode);
      const nextIntent =
        seed.intent && options.some((option) => option.intent === seed.intent)
          ? seed.intent
          : options[0].intent;
      setMode(nextMode);
      setIntent(nextIntent);
      setInput(seed.suggestedText ?? "");
      setMessages([]);
      setError(null);
      setPending(false);
      setConversationId(newConversationId());
      messageCounter.current = 0;
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
    if (!open && wasOpen.current) {
      const opener = openerRef.current;
      if (opener instanceof HTMLElement) {
        opener.focus();
      }
    }
    wasOpen.current = open;
  }, [open, seed, record]);

  // Escape closes; Tab cycles inside the drawer while open.
  useEffect(() => {
    if (!open) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) {
        return;
      }
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button, [href], textarea, input, select, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => !element.hasAttribute("disabled"));
      if (focusable.length === 0) {
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  if (!open) {
    return null;
  }

  const shipmentAvailable = record !== null;
  const focus = seed.focus ?? "shipment";
  const suggestions = suggestedPrompts(mode, focus);

  const changeMode = (next: ConversationMode) => {
    if (next === mode) {
      return;
    }
    setMode(next);
    const options = intentsFor(next);
    if (!options.some((option) => option.intent === intent)) {
      setIntent(options[0].intent);
    }
    setError(null);
  };

  const send = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const text = input.trim();
    if (!text || pending) {
      return;
    }
    if (mode === "shipment_aware" && !record) {
      setError(
        new ApiError(
          400,
          "invalid_input",
          "Shipment questions need an active shipment. Switch to regulatory knowledge instead.",
        ),
      );
      return;
    }
    setError(null);
    setPending(true);
    const userMessage: ChatMessage = {
      id: `message-${++messageCounter.current}`,
      role: "user",
      text,
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    try {
      const response = await postConversationMessage(auth, {
        conversation_id: conversationId,
        mode,
        intent,
        user_text: text,
        ...(mode === "shipment_aware" && record
          ? {
              workflow: record,
              ...(seed.requirementId ? { requirement_id: seed.requirementId } : {}),
              ...(seed.evidenceId ? { evidence_id: seed.evidenceId } : {}),
            }
          : {}),
        ...(intent === KNOWLEDGE_INTENT ? { information_need: text } : {}),
      });
      const assistantMessage: ChatMessage = {
        id: `message-${++messageCounter.current}`,
        role: "assistant",
        text: response.summary_text,
        response,
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch (err) {
      setError(err);
      setInput(text);
      window.setTimeout(() => inputRef.current?.focus(), 0);
    } finally {
      setPending(false);
    }
  };

  const contextLine =
    mode === "knowledge" ? (
      <p className="muted">Regulatory knowledge — no shipment context is sent.</p>
    ) : record ? (
      <p className="muted">
        Shipment: {shipmentContextLabel(record.shipment_id, workflowStateLabel(record.state))}
      </p>
    ) : (
      <p className="muted">No active shipment — switch to regulatory knowledge.</p>
    );

  return (
    <div className="conversation-overlay">
      <div className="conversation-scrim" aria-hidden="true" onClick={close} />
      <section
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        className="conversation-panel"
      >
        <header className="conversation-panel__head">
          <div>
            <p className="page-kicker">Ask Xportra</p>
            <h2 id={headingId}>Shipment assistant</h2>
            {contextLine}
          </div>
          <button
            type="button"
            className="ghost-button"
            onClick={close}
            aria-label="Close conversation panel"
          >
            Close
          </button>
        </header>

        <div
          className="conversation-modes"
          role="radiogroup"
          aria-label="Conversation mode"
          id={modeGroupId}
        >
          <label className="conversation-modes__option">
            <input
              type="radio"
              name={`${modeGroupId}-mode`}
              checked={mode === "shipment_aware"}
              disabled={!shipmentAvailable}
              onChange={() => changeMode("shipment_aware")}
            />
            <span>
              <strong>This shipment</strong>
              <span className="muted"> — answers from this workflow&apos;s recorded state.</span>
            </span>
          </label>
          <label className="conversation-modes__option">
            <input
              type="radio"
              name={`${modeGroupId}-mode`}
              checked={mode === "knowledge"}
              onChange={() => changeMode("knowledge")}
            />
            <span>
              <strong>Regulatory knowledge</strong>
              <span className="muted"> — general questions; shipment context is never sent.</span>
            </span>
          </label>
        </div>

        <div className="form-row">
          <label htmlFor={intentId}>Question type</label>
          <select
            id={intentId}
            value={intent}
            onChange={(event) => setIntent(event.target.value as ConversationIntent)}
          >
            {intentsFor(mode).map((option) => (
              <option key={option.intent} value={option.intent}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="form-hint">
            {intentsFor(mode).find((option) => option.intent === intent)?.hint}
          </p>
        </div>

        {messages.length === 0 && !pending ? (
          <div className="conversation-empty">
            <p className="muted">
              {mode === "knowledge"
                ? "Ask a general regulatory question. Answers carry validated source references."
                : "Ask about the recorded state of this shipment. Answers quote Xportra records — they never decide compliance."}
            </p>
            <ul className="conversation-suggestions" aria-label="Suggested questions">
              {suggestions.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    className="chip"
                    onClick={() => {
                      setInput(suggestion);
                      inputRef.current?.focus();
                    }}
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <ol className="conversation-messages" role="log" aria-live="polite" aria-label="Conversation">
          {messages.map((message) =>
            message.role === "user" ? (
              <li key={message.id} className="conversation-message conversation-message--user">
                <p className="eyebrow">You</p>
                <p>{message.text}</p>
              </li>
            ) : (
              <li
                key={message.id}
                className="conversation-message conversation-message--assistant"
              >
                <p className="eyebrow">Xportra</p>
                {message.response ? (
                  <AssistantTurn response={message.response} />
                ) : (
                  <p>{message.text}</p>
                )}
              </li>
            ),
          )}
        </ol>
        {pending ? <LoadingState text="Asking Xportra…" /> : null}
        {error ? <ErrorNotice error={error} /> : null}

        <form className="conversation-composer" onSubmit={(event) => void send(event)}>
          <div className="form-row">
            <label htmlFor={inputId}>Ask about {mode === "knowledge" ? "regulations" : "this shipment"}</label>
            <textarea
              ref={inputRef}
              id={inputId}
              value={input}
              maxLength={2000}
              rows={3}
              onChange={(event) => setInput(event.target.value)}
              placeholder={
                mode === "knowledge"
                  ? "e.g. What documents are normally required for this export?"
                  : "e.g. What still needs my attention?"
              }
            />
          </div>
          <button type="submit" className="primary-button" disabled={pending || input.trim().length === 0}>
            {pending ? "Asking…" : "Ask Xportra"}
          </button>
          <p className="form-hint">
            Read-only: answers explain recorded state. Actions stay in the workflow screens.
          </p>
        </form>
      </section>
    </div>
  );
}

function AssistantTurn({ response }: { response: ConversationMessageResponse }) {
  const refused = response.status === "refused_unknown";
  return (
    <div className="conversation-answer">
      <p>
        <StatusBadge value={response.status} tone={conversationStatusTone(response.status)} />
      </p>
      {refused ? (
        <>
          <p>{response.summary_text}</p>
          {response.refusal_reason ? (
            <p className="muted">Why: {response.refusal_reason}</p>
          ) : null}
        </>
      ) : (
        <>
          <div className="conversation-explanation">
            <p className="eyebrow">Explanation</p>
            <p>{response.summary_text}</p>
          </div>
          <div className="conversation-record">
            <p className="eyebrow">Xportra record</p>
            {response.shipment_references.length === 0 &&
            response.citations.length === 0 ? (
              <p className="muted">No references returned.</p>
            ) : null}
            {response.shipment_references.length > 0 ? (
              <ul className="conversation-references">
                {response.shipment_references.map((reference) => (
                  <li key={`${reference.kind}-${reference.id}`}>
                    <span className="muted">{reference.kind}: </span>
                    <Identifier value={reference.id} short={8} />
                  </li>
                ))}
              </ul>
            ) : null}
            {response.citations.length > 0 ? (
              <ul className="conversation-references">
                {response.citations.map((citation) => (
                  <li key={`${citation.label}-${citation.evidence.chunk_id}`}>
                    <p>
                      <strong>{citation.label}</strong>{" "}
                      <span className="muted">
                        {citation.evidence.source_type} · {citation.evidence.source_id}
                      </span>
                    </p>
                    {citation.evidence.source_location ? (
                      <p className="muted">{citation.evidence.source_location}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
            <p className="form-hint">
              The explanation above interprets these records; the records stay authoritative.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
