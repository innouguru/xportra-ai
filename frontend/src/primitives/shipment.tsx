import type { ReactNode } from "react";
import { StatusIndicator, type StatusTone } from "./status";

/**
 * Phase 10.8A shipment-oriented primitives.
 *
 * Presentation boundaries for later phases to
 * compose (dashboard 10.8C, workspace 10.8E,
 * verification 10.8F). Display-only props:
 * human words in, no business logic, no domain
 * knowledge, no invented compliance semantics.
 * Fixtures live in test files only.
 *
 * The approved reference
 * (`docs/design/xportra-ui-redesign.*`) composes
 * shipments and requirements as ledger/worklist
 * rows — dividers, alignment, and typography —
 * not cards. `ShipmentWorklistRow` and
 * `RequirementLedgerRow` below are the row
 * presentations; the older `ShipmentCard` /
 * `RequirementCard` remain only for the legacy
 * deep-link tree until it converges.
 */

/** User-facing shipment status (words + tone). */
export function ShipmentStatus({
  tone,
  label,
  detail,
}: {
  tone: StatusTone;
  label: string;
  detail?: string;
}) {
  return <StatusIndicator tone={tone} label={label} detail={detail} />;
}

/**
 * Briefing-focused shipment card. The whole card
 * is clickable through `href`; the primary
 * action stays a separately focusable control
 * above the stretched link.
 *
 * When `onSelect` is provided (e.g. the caller
 * must load session state before navigating),
 * the title link invokes it instead of following
 * `href`; `href` remains as the honest
 * destination hint.
 */
export function ShipmentCard({
  title,
  meta,
  status,
  href,
  action,
  onSelect,
}: {
  title: string;
  meta?: string;
  status: ReactNode;
  href: string;
  action?: ReactNode;
  onSelect?: () => void;
}) {
  return (
    <li className="xb-card">
      <h3 className="xb-card__title">
        <a
          className="xb-card__link"
          href={href}
          onClick={
            onSelect
              ? (event) => {
                  event.preventDefault();
                  onSelect();
                }
              : undefined
          }
        >
          {title}
        </a>
      </h3>
      {meta ? <p className="xb-card__meta">{meta}</p> : null}
      <div>{status}</div>
      {action ? (
        <div className="xb-card__footer">
          <span className="xb-card__action">{action}</span>
        </div>
      ) : null}
    </li>
  );
}

/** Structured shipment facts (label/value rows). */
export function ShipmentSummary({ rows }: { rows: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="xb-summary">
      {rows.map((row) => (
        <div key={row.label}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** User-facing requirement status (words + tone). */
export function RequirementStatus({ tone, label }: { tone: StatusTone; label: string }) {
  return <StatusIndicator tone={tone} label={label} />;
}

/** Minimal requirement card: name + status + action, with room for disclosure. */
export function RequirementCard({
  name,
  status,
  action,
  children,
}: {
  name: string;
  status: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <article className="xb-req-card">
      <h3 className="xb-req-card__name">{name}</h3>
      <div>{status}</div>
      {action}
      {children}
    </article>
  );
}

/**
 * Shipment worklist row (approved reference):
 * semantic dot, shipment name, route, and a
 * one-line state — separated by a hairline,
 * never a card. The name links to `href`; when
 * `onSelect` is provided (e.g. session state
 * must load before navigating) it runs instead.
 * An optional trailing action (`Review →`)
 * performs the same open as a separately
 * focusable control.
 */
export function ShipmentWorklistRow({
  name,
  route,
  state,
  tone,
  href,
  actionLabel,
  onSelect,
  dimmed = false,
  secondaryAction,
}: {
  name: string;
  route?: string;
  state: string;
  tone: StatusTone;
  href: string;
  actionLabel?: string;
  onSelect?: () => void;
  dimmed?: boolean;
  secondaryAction?: { label: string; ariaLabel?: string; onSelect: () => void };
}) {
  const open = onSelect ?? (() => undefined);
  const usesSelect = onSelect !== undefined;
  return (
    <li className={dimmed ? "xb-row xb-row--dimmed" : "xb-row"}>
      <span className={`xb-row__dot xb-row__dot--${tone}`} aria-hidden="true" />
      <span className="xb-row__main">
        <a
          className="xb-row__link"
          href={href}
          onClick={
            usesSelect
              ? (event) => {
                  event.preventDefault();
                  open();
                }
              : undefined
          }
        >
          {name}
        </a>
        {route ? <span className="xb-row__route">{route}</span> : null}
      </span>
      <span className="xb-row__state">{state}</span>
      {actionLabel ? (
        usesSelect ? (
          <button type="button" className="xb-row__go" onClick={open}>
            {actionLabel} <span aria-hidden="true">→</span>
          </button>
        ) : (
          <a className="xb-row__go" href={href}>
            {actionLabel} <span aria-hidden="true">→</span>
          </a>
        )
      ) : null}
      {secondaryAction ? (
        <button
          type="button"
          className="xb-row__forget"
          aria-label={secondaryAction.ariaLabel ?? secondaryAction.label}
          onClick={secondaryAction.onSelect}
        >
          {secondaryAction.label}
        </button>
      ) : null}
    </li>
  );
}

/**
 * Requirement ledger row (approved reference):
 * dot, plain-language name, one-line "why",
 * right-aligned state phrase, optional evidence
 * line — separated by a hairline, never a card.
 * With `onOpen` the whole row is one button
 * opening the requirement drawer; without it
 * the row renders static (read-only history).
 * Status is dot + words, never a pill or raw
 * internal state.
 */
export function RequirementLedgerRow({
  name,
  why,
  state,
  tone,
  evidence,
  onOpen,
}: {
  name: string;
  why?: string;
  state: string;
  tone: StatusTone;
  evidence?: string;
  onOpen?: () => void;
}) {
  const body = (
    <>
      <span className={`xb-ledger-row__dot xb-ledger-row__dot--${tone}`} aria-hidden="true" />
      <span className="xb-ledger-row__main">
        <span className="xb-ledger-row__name">{name}</span>
        {why ? <span className="xb-ledger-row__why">{why}</span> : null}
        {evidence ? <span className="xb-ledger-row__evidence">{evidence}</span> : null}
      </span>
      <span className={`xb-ledger-row__state xb-ledger-row__state--${tone}`}>{state}</span>
    </>
  );
  if (!onOpen) {
    return (
      <li className="xb-ledger-row">
        <div className="xb-ledger-row__static">{body}</div>
      </li>
    );
  }
  return (
    <li className="xb-ledger-row">
      <button type="button" className="xb-ledger-row__button" onClick={onOpen} aria-label={`${name} — ${state}`}>
        {body}
      </button>
    </li>
  );
}

/** Document verification stage (words + tone). */
export function DocumentStatus({ tone, label }: { tone: StatusTone; label: string }) {
  return <StatusIndicator tone={tone} label={label} />;
}
