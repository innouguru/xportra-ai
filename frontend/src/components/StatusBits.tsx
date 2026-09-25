import { useState } from "react";
import { userFacingErrorMessage } from "../api/client";

/** Small labeled value row for structured record display. */
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** Monospace identifier with full value on hover/focus. */
export function Identifier({ value, short = 8 }: { value: string; short?: number }) {
  return (
    <code className="identifier" title={value}>
      {value.length > short ? `${value.slice(0, short)}…` : value}
    </code>
  );
}

/** Backend status rendered verbatim with a non-color cue. */
export function StatusBadge({ value, tone }: { value: string; tone: "info" | "muted" | "attention" | "neutral" }) {
  return (
    <span className={`badge badge--${tone}`}>
      <span className="badge-dot" aria-hidden="true" />
      {value}
    </span>
  );
}

/** Error notice: backend message preserved, never reinterpreted. */
export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="notice notice--error" role="alert">
      <p>{userFacingErrorMessage(error)}</p>
      {onRetry ? (
        <button type="button" className="secondary-button" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

/** Empty state with an optional action. */
export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="empty-state">
      <h2>{title}</h2>
      <p>{body}</p>
      {action}
    </div>
  );
}

/** Accessible loading indicator with status text. */
export function LoadingState({ text }: { text: string }) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{text}</p>
    </div>
  );
}

/**
 * Terminal-state announcement.
 *
 * Communicates closure through text, structure and an `aria-label`
 * (never color alone). Restrained: no alarm styling, no decoration.
 */
export function TerminalNotice({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="terminal-banner" aria-label={title}>
      <p className="eyebrow">Final — permanently closed</p>
      <p className="terminal-banner__title">{title}</p>
      {children}
    </section>
  );
}

/** Collapsible section (details/summary for keyboard + screen-reader support). */
export function Collapsible({ title, children, defaultOpen = false }: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details className="collapsible" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>{title}</summary>
      <div className="collapsible-body">{children}</div>
    </details>
  );
}
