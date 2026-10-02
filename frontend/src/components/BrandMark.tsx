import { Link } from "react-router-dom";

/**
 * Xportra brand lockup (wordmark + glyph slot).
 *
 * The glyph span is a deliberate seam, not a final
 * mark: when an X/P monogram asset is explicitly
 * approved, replace the contents of `.brand-glyph`
 * with that asset and leave this component's structure,
 * link target, and accessible name untouched. Do not
 * invent logo geometry, illustrations, or placeholder
 * artwork here.
 *
 * - Default: in-app home link (unchanged legacy
 *   behavior for the existing shell and tests).
 * - `newTab`: opens the public landing route in a
 *   new browser tab without touching session
 *   state (Phase 10.8 authenticated shell).
 * - `compact`: glyph-only mark for collapsed
 *   sidebars; keeps the same link target and
 *   accessible name.
 */
export function BrandMark({ newTab = false, compact = false }: {
  newTab?: boolean;
  compact?: boolean;
} = {}) {
  const label = newTab ? "Xportra AI home (opens in a new tab)" : "Xportra AI home";
  if (compact) {
    return (
      <div className="brand">
        {newTab ? (
          <a
            href="/"
            target="_blank"
            rel="noreferrer"
            className="brand-glyph brand-glyph--link"
            aria-label={label}
          >
            X
          </a>
        ) : (
          <Link to="/" className="brand-glyph brand-glyph--link" aria-label={label}>
            X
          </Link>
        )}
      </div>
    );
  }
  const wordmark = newTab ? (
    <a href="/" target="_blank" rel="noreferrer" className="brand-mark" aria-label={label}>
      Xportra&nbsp;AI
    </a>
  ) : (
    <Link to="/" className="brand-mark" aria-label="Xportra AI home">
      Xportra&nbsp;AI
    </Link>
  );
  return (
    <div className="brand">
      <span className="brand-glyph" aria-hidden="true">
        X
      </span>
      <span className="brand-stack">
        {wordmark}
        <span className="brand-sub">Export Compliance Intelligence</span>
      </span>
    </div>
  );
}
