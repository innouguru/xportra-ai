import type { ReactNode } from "react";

/**
 * Phase 10.8A layout primitives.
 *
 * Reusable, unopinionated boundaries for page
 * composition. Final shell composition (sidebar
 * navigation items, drawer behavior, route
 * structure) belongs to Phase 10.8B and later;
 * these primitives only reserve the landmark,
 * sizing, and slot contracts 10.8B will fill.
 */

/** Constrained page container with safe gutters. */
export function WorkspaceContainer({ children }: { children: ReactNode }) {
  return <div className="xb-workspace">{children}</div>;
}

/** Kicker + title + description + optional actions. */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="xb-page-header">
      {eyebrow ? <p className="xb-page-header__eyebrow">{eyebrow}</p> : null}
      <h1 className="xb-page-header__title">{title}</h1>
      {description ? <p className="xb-page-header__description">{description}</p> : null}
      {actions ? <div className="xb-page-header__actions">{actions}</div> : null}
    </div>
  );
}

/** Ordered breadcrumb trail; current page via `current`. */
export function Breadcrumbs({ trail }: { trail: { label: string; href?: string }[] }) {
  return (
    <nav className="xb-breadcrumbs" aria-label="Breadcrumb">
      <ol>
        {trail.map((item, index) => {
          const isLast = index === trail.length - 1;
          return (
            <li key={`${index}-${item.label}`}>
              {item.href && !isLast ? (
                <a href={item.href}>{item.label}</a>
              ) : (
                <span aria-current="page">{item.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Back-navigation button (history-back by default). */
export function BackButton({ label = "Back", onBack }: { label?: string; onBack?: () => void }) {
  const goBack = () => {
    if (onBack) {
      onBack();
    } else {
      window.history.back();
    }
  };
  return (
    <button type="button" className="xb-back" onClick={goBack}>
      <span aria-hidden="true">←</span> {label}
    </button>
  );
}

/** Contextual header container (slots only). */
export function TopBar({
  context,
  actions,
}: {
  context?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="xb-topbar">
      {context}
      {actions}
    </div>
  );
}

/**
 * Sidebar container boundary: brand, nav, and
 * footer slots plus the collapsed state class.
 * Navigation items, collapse wiring, and mobile
 * drawer composition arrive in Phase 10.8B.
 */
export function Sidebar({
  label,
  brand,
  nav,
  footer,
  collapsed = false,
}: {
  label: string;
  brand?: ReactNode;
  nav?: ReactNode;
  footer?: ReactNode;
  collapsed?: boolean;
}) {
  return (
    <aside
      className={collapsed ? "xb-sidebar xb-sidebar--collapsed" : "xb-sidebar"}
      aria-label={label}
    >
      {brand ? <div className="xb-sidebar__brand">{brand}</div> : null}
      {nav ? <nav className="xb-sidebar__nav" aria-label={`${label} sections`}>{nav}</nav> : null}
      {footer ? <div className="xb-sidebar__footer">{footer}</div> : null}
    </aside>
  );
}
