import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  createConversation,
  getConversation,
  listConversations,
  postConversationMessage,
} from "../../api/conversations";
import { ApiError, type AuthCredentials } from "../../api/client";
import { useAuth } from "../../app/AuthContext";
import { ErrorNotice, LoadingState, StatusBadge } from "../../components/StatusBits";
import { Identifier } from "../../components/StatusBits";
import {
  conversationStatusTone,
  conversationModeLabel,
} from "../../lib/conversation";
import type {
  ConversationDetailResponse,
  ConversationListItem,
  ConversationMode,
} from "../../types/api";
import "./ask.css";

/** Initial suggested questions for knowledge mode. */
const SUGGESTED_QUESTIONS: string[] = [
  "What documents are normally required for this export?",
  "What does this regulation require?",
  "Explain this requirement.",
];

export function AskPage() {
  const auth = useAuth();
  const credentials: AuthCredentials = useMemo(
    () => ({
      token: auth.token ?? null,
      devTenantId: auth.devTenantId ?? null,
    }),
    [auth.token, auth.devTenantId],
  );

  const [conversations, setConversations] = useState<ConversationListItem[]>(
    [],
  );
  const [current, setCurrent] = useState<ConversationDetailResponse | null>(
    null,
  );
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [mode, setMode] = useState<ConversationMode>("knowledge");
  const [listLoading, setListLoading] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Load conversation history on mount.
  useEffect(() => {
    setListLoading(true);
    listConversations(credentials)
      .then((data) => setConversations(data.conversations))
      .catch((err) => {
        // History load failure is non-fatal: the user can still start
        // a new conversation.
        console.warn("Failed to load conversation history", err);
      })
      .finally(() => setListLoading(false));
  }, [credentials]);

  const scrollToBottom = useCallback(() => {
    window.setTimeout(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }, 0);
  }, []);

  const startConversation = useCallback(async (nextMode: ConversationMode) => {
    setMode(nextMode);
    setError(null);
    setInput("");
    setCurrent(null);
    try {
      const created = await createConversation(credentials, {
        mode: nextMode,
      });
    const detail = await getConversation(credentials, created.id);
    setCurrent(detail);
    setMode(detail.mode as ConversationMode);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err
          : new ApiError(0, "unexpected_error", "Could not start conversation."),
      );
    }
  }, [credentials, scrollToBottom]);

  const openConversation = useCallback(
    async (id: string) => {
      setError(null);
      try {
        const detail = await getConversation(credentials, id);
        setCurrent(detail);
        setMode(detail.mode as ConversationMode);
        scrollToBottom();
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err
            : new ApiError(0, "unexpected_error", "Could not open conversation."),
        );
      }
    },
    [credentials, scrollToBottom],
  );

  const send = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || pending || !current) {
      return;
    }

    setError(null);
    setPending(true);

    const userMessageId = `msg-${Date.now()}`;
    const optimisticUser: ConversationMessageItem = {
      id: userMessageId,
      role: "user",
      content: text,
      intent: "answer_regulatory_question",
      status: null,
      citations: [],
      shipment_references: [],
      refusal_reason: null,
      created_at: new Date().toISOString(),
    };

    setCurrent((prev) =>
      prev
        ? {
            ...prev,
            messages: [...prev.messages, optimisticUser],
          }
        : null,
    );
    setInput("");

    try {
      const response = await postConversationMessage(credentials, {
        conversation_id: current.id,
        mode: current.mode as ConversationMode,
        intent: "answer_regulatory_question",
        user_text: text,
        information_need: text,
        retrieval_mode: "hybrid",
      });

      const assistantMessage: ConversationMessageItem = {
        id: `msg-${Date.now() + 1}`,
        role: "assistant",
        content: response.summary_text,
        intent: response.intent,
        status: response.status,
        citations: response.citations.map((c) => ({
          label: c.label,
          rank_position: c.rank_position,
          evidence: {
            chunk_id: c.evidence.chunk_id,
            document_id: c.evidence.document_id,
            chunk_index: c.evidence.chunk_index,
            source_id: c.evidence.source_id,
            source_type: c.evidence.source_type,
            source_location: c.evidence.source_location,
            document_version: c.evidence.document_version,
            content_fingerprint: c.evidence.content_fingerprint,
          },
        })),
        shipment_references: response.shipment_references.map((r) => ({
          kind: r.kind,
          id: r.id,
        })),
        refusal_reason: response.refusal_reason,
        created_at: new Date().toISOString(),
      };

      setCurrent((prev) =>
        prev
          ? {
              ...prev,
              messages: prev.messages.map((m) =>
                m.id === userMessageId ? m : m,
              ).concat(assistantMessage),
            }
          : null,
      );
      scrollToBottom();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err
          : new ApiError(0, "unexpected_error", "Could not send message."),
      );
      setInput(text);
    } finally {
      setPending(false);
    }
  }, [input, current, pending, credentials, scrollToBottom]);

  const renderCitation = (c: ConversationMessageItem["citations"][number]) => (
    <li key={`${c.label}-${c.evidence.chunk_id}`} className="xb-ask-citation">
      <p>
        <strong>[{c.label}]</strong>{" "}
        <span className="xb-ask-citation-source">
          {c.evidence.source_type} · {c.evidence.source_id}
        </span>
      </p>
      {c.evidence.document_version && (
        <p className="xb-ask-citation-meta">
          Document version: {c.evidence.document_version}
        </p>
      )}
      {c.evidence.source_location && (
        <p className="xb-ask-citation-meta">
          Source: {c.evidence.source_location}
        </p>
      )}
      <button
        type="button"
        className="xb-ask-citation-inspect"
        onClick={() => {
          // Source inspection: the citation evidence is the traceable
          // pointer. Rendering it here is the inspection surface.
        }}
      >
        Inspect source
      </button>
    </li>
  );

  const renderMessage = (m: ConversationMessageItem) => {
    const isUser = m.role === "user";
    const refused = m.status === "refused_unknown";
    return (
      <li
        key={m.id}
        className={`xb-ask-message xb-ask-message--${isUser ? "user" : "assistant"}`}
      >
        <p className="xb-ask-message-eyebrow">
          {isUser ? "You" : "Xportra"}
        </p>
        <p className="xb-ask-message-text">{m.content}</p>
        {!isUser && (
          <div className="xb-ask-message-meta">
            <StatusBadge
              value={m.status ?? "grounded"}
              tone={conversationStatusTone(m.status ?? "grounded")}
            />
            {refused && m.refusal_reason && (
              <p className="xb-ask-refusal-reason">
                <span className="xb-ask-refusal-label">Why:</span>{" "}
                {m.refusal_reason}
              </p>
            )}
            {!refused && m.citations.length > 0 && (
              <>
                <p className="xb-ask-citations-heading">Sources</p>
                <ul className="xb-ask-citations">
                  {m.citations.map(renderCitation)}
                </ul>
              </>
            )}
            {!refused && m.citations.length === 0 && m.status !== "refused_unknown" && (
              <p className="xb-ask-no-sources">No sources returned.</p>
            )}
          </div>
        )}
      </li>
    );
  };

  const emptyState = (
    <div className="xb-ask-empty-state">
      <p className="xb-ask-empty-text">
        {mode === "knowledge"
          ? "Ask a regulatory question. Answers carry validated source references."
          : "Ask about this shipment. Answers quote Xportra records."}
      </p>
      <ul className="xb-ask-suggestions" aria-label="Suggested questions">
        {SUGGESTED_QUESTIONS.map((s) => (
          <li key={s}>
            <button
              type="button"
              className="xb-ask-suggestion-chip"
              onClick={() => {
                setInput(s);
                inputRef.current?.focus();
              }}
            >
              {s}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <div className="xb-ask">
      <header className="xb-ask-header">
        <Link to="/" className="xb-land-wordmark" aria-label="Xportra home">
          <span className="brand-glyph" aria-hidden="true">X</span>
          <span>
            Xportra<span className="xb-land-wordmark__dot" aria-hidden="true">.</span>
          </span>
        </Link>
      </header>

      <main id="main" className="xb-ask-main">
        <h1>Ask Xportra</h1>

        {/* Conversation history sidebar */}
        <section className="xb-ask-history">
          <h2 className="xb-ask-history-heading">Conversations</h2>
          {listLoading ? (
            <LoadingState text="Loading history…" />
          ) : conversations.length === 0 ? (
            <p className="xb-ask-history-empty">
              No conversations yet. Start one below.
            </p>
          ) : (
            <ul ref={listRef} className="xb-ask-history-list">
              {conversations.map((c) => (
                <li key={c.id} className="xb-ask-history-item">
                  <button
                    type="button"
                    className="xb-ask-history-button"
                    onClick={() => openConversation(c.id)}
                  >
                    <span className="xb-ask-history-mode">
                      {conversationModeLabel(c.mode as ConversationMode)}
                    </span>
                    <span className="xb-ask-history-updated">
                      {new Date(c.updated_at).toLocaleString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            className="primary-button xb-ask-new-conversation"
            onClick={() => startConversation(mode)}
          >
            New conversation
          </button>
        </section>

        {/* Active conversation panel */}
        {current ? (
          <section className="xb-ask-conversation">
            <div className="xb-ask-conversation-head">
              <h2>{conversationModeLabel(current.mode as ConversationMode)}</h2>
              <p className="xb-ask-conversation-id">
                <Identifier value={current.id} short={8} />
              </p>
            </div>

            {error && <ErrorNotice error={error} />}

            <div className="xb-ask-messages" ref={scrollRef}>
              {current.messages.length === 0 && !pending ? emptyState : null}
              {current.messages.map(renderMessage)}
              {pending && <LoadingState text="Asking Xportra…" />}
            </div>

            <form className="xb-ask-form" onSubmit={send}>
              <label htmlFor="xb-ask-input" className="xb-ask-label">
                Your regulatory question
              </label>
              <textarea
                ref={inputRef}
                id="xb-ask-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  mode === "knowledge"
                    ? "e.g. What documents are normally required for this export?"
                    : "e.g. What still needs my attention?"
                }
                rows={3}
                maxLength={2000}
                disabled={pending}
              />
              <div className="xb-ask-form-actions">
                <button
                  type="button"
                  className="xb-ask-mode-toggle"
                  onClick={() =>
                    startConversation(
                      mode === "knowledge" ? "shipment_aware" : "knowledge",
                    )
                  }
                >
                  Switch to {mode === "knowledge" ? "this shipment" : "regulatory knowledge"}
                </button>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={pending || !input.trim()}
                >
                  {pending ? "Asking…" : "Ask Xportra"}
                </button>
              </div>
              <p className="xb-ask-form-hint">
                Read-only: answers explain recorded state or validated
                regulatory retrieval. Actions stay in the workflow screens.
              </p>
            </form>
          </section>
        ) : (
          <section className="xb-ask-start">
            <p className="xb-ask-start-text">
              Start a conversation to ask a regulatory question. Answers
              are grounded in retrieved regulatory evidence and carry
              validated source references.
            </p>
            <div className="xb-ask-start-actions">
              <button
                type="button"
                className="primary-button"
                onClick={() => startConversation("knowledge")}
              >
                New regulatory conversation
              </button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

interface ConversationMessageItem {
  id: string;
  role: string;
  content: string;
  intent: string | null;
  status: string | null;
  citations: Array<{
    label: string;
    rank_position: number;
    evidence: {
      chunk_id: string;
      document_id: string;
      chunk_index: number;
      source_id: string;
      source_type: string;
      source_location: string | null;
      document_version: string | null;
      content_fingerprint: string;
    };
  }>;
  shipment_references: Array<{ kind: string; id: string }>;
  refusal_reason: string | null;
  created_at: string;
}
