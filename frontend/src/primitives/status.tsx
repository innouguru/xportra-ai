/**
 * Phase 10.8A status primitives.
 *
 * Display-only: every component takes human words
 * plus a tone. Components never know domain
 * internals and never render technical state
 * names — callers pass plain-English labels
 * (e.g. "Waiting for you", "Needs attention").
 */

export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

/** Indicator dot + status words (never color alone). */
export function StatusIndicator({
  tone,
  label,
  detail,
}: {
  tone: StatusTone;
  label: string;
  detail?: string;
}) {
  return (
    <span className={`xb-status xb-status--${tone}`}>
      <span className="xb-status-dot" aria-hidden="true" />
      {label}
      {detail ? <span className="xb-status__detail">{detail}</span> : null}
    </span>
  );
}

/** Compact labeled tone badge. */
export function StatusBadge({ tone, label }: { tone: StatusTone; label: string }) {
  return (
    <span className={`xb-badge xb-badge--${tone}`}>
      <span className="xb-status-dot" aria-hidden="true" />
      {label}
    </span>
  );
}

/** Value + label + optional hint for count summaries. */
export function MetricSummary({
  value,
  label,
  hint,
}: {
  value: string;
  label: string;
  hint?: string;
}) {
  return (
    <div className="xb-metric">
      <span className="xb-metric__value" aria-hidden="true">
        {value}
      </span>
      <span className="xb-metric__label">
        {label}: {value}
      </span>
      {hint ? <p className="xb-metric__hint">{hint}</p> : null}
    </div>
  );
}

/**
 * Quiet attention affordance for the dashboard
 * attention section (final placement is 10.8C).
 * Serious blockers stay subtle here because the
 * section itself already surfaces them.
 */
export function AttentionIndicator({ label }: { label: string }) {
  return <span className="xb-attention">{label}</span>;
}
