import type { ReactNode } from "react";

/**
 * Phase 10.8A feedback primitives.
 *
 * Canonical token-based states for new (Phase
 * 10.8+) surfaces. Same prop shapes as the
 * legacy `StatusBits` states so 10.8B+ pages can
 * migrate by changing the import path; legacy
 * components stay untouched for existing pages.
 */

/** Friendly, action-oriented empty state. */
export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="xb-empty">
      <h2 className="xb-empty__title">{title}</h2>
      <p className="xb-empty__body">{body}</p>
      {action}
    </div>
  );
}

/** Accessible loading indicator with status text. */
export function LoadingState({ text }: { text: string }) {
  return (
    <div className="xb-loading" role="status" aria-live="polite">
      <span className="xb-spinner" aria-hidden="true" />
      <p>{text}</p>
    </div>
  );
}

/** Error state: calm message with optional retry. */
export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="xb-error" role="alert">
      <p>
        <strong>{title}</strong> {message}
      </p>
      {onRetry ? (
        <button type="button" className="xb-back" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}
