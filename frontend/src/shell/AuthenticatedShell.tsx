import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../app/AuthContext";
import { BrandMark } from "../components/BrandMark";
import { Breadcrumbs, WorkspaceContainer } from "../primitives/layout";
import { useEscapeKey, useFocusRestore } from "../primitives/a11y";
import { useTheme } from "../theme/theme";

/**
 * Phase 10.8B authenticated application shell.
 *
 * Shipment-first workspace frame (R-10.8.1–R-10.8.3,
 * ADR-0012): expandable sidebar with exactly two
 * primary destinations (Dashboard, View Shipments),
 * brand link opening the public landing route in a
 * new tab, compact account control, subtle
 * notification entry point, theme toggle, and a
 * mobile navigation drawer. Product pages
 * (dashboard content, shipments table, workspace,
 * settings) arrive in later 10.8 phases; this file
 * only frames them.
 */

const SIDEBAR_STORAGE_KEY = "xportra.shell.sidebar.v1";

function prefersCollapsed(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(max-width: 1100px)").matches;
}

function storedSidebar(): boolean | null {
  try {
    const raw = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (raw === "collapsed") {
      return true;
    }
    if (raw === "expanded") {
      return false;
    }
    return null;
  } catch {
    return null;
  }
}

function icon(path: string) {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false">
      <path
        d={path}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const DASHBOARD_ICON = "M3 3h7v7H3zM10 3h7v4h-7zM10 10h7v7h-7zM3 13h7v4H3z";
const SHIPMENTS_ICON = "M4 5h12M4 10h12M4 15h7";
const BELL_ICON = "M10 3a5 5 0 0 0-5 5v3L3.5 13.5h13L15 11V8a5 5 0 0 0-5-5zM8.5 16a1.5 1.5 0 0 0 3 0";
const USER_ICON = "M10 9.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM4 16.5c0-3 2.7-5 6-5s6 2 6 5";
const SUN_ICON = "M10 4v1.5M10 14.5V16M4 10h1.5M14.5 10H16M5.8 5.8l1 1M13.2 13.2l1 1M14.2 5.8l-1 1M6.8 13.2l-1 1M10 7.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z";
const MOON_ICON = "M15.5 12.5A6 6 0 0 1 7.5 4.5a6 6 0 1 0 8 8z";
const MENU_ICON = "M3.5 6h13M3.5 10h13M3.5 14h13";
const CLOSE_ICON = "M5 5l10 10M15 5L5 15";
const CHEVRON_LEFT = "M12.5 5L7.5 10l5 5";
const CHEVRON_RIGHT = "M7.5 5l5 5-5 5";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: DASHBOARD_ICON },
  { to: "/shipments", label: "View Shipments", icon: SHIPMENTS_ICON },
] as const;

function ThemeToggle() {
  const { resolved, setMode } = useTheme();
  const toLight = resolved === "dark";
  return (
    <button
      type="button"
      className="xb-icon-btn"
      aria-label={toLight ? "Switch to light theme" : "Switch to dark theme"}
      title={toLight ? "Light theme" : "Dark theme"}
      onClick={() => setMode(toLight ? "light" : "dark")}
    >
      {icon(toLight ? SUN_ICON : MOON_ICON)}
    </button>
  );
}

function NotificationEntry() {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  useEscapeKey(() => {
    if (open) {
      setOpen(false);
      buttonRef.current?.focus();
    }
  });

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onPointerDown = (event: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open ]);

  return (
    <div className="xb-menu-wrap" ref={wrapRef}>
      <button
        ref={buttonRef}
        type="button"
        className="xb-icon-btn"
        aria-label="Notifications"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {icon(BELL_ICON)}
      </button>
      {open ? (
        <div className="xb-popover" role="status">
          <p>
            <strong>You are all caught up.</strong>
          </p>
          <p>Shipment updates will appear here in a later update.</p>
        </div>
      ) : null}
    </div>
  );
}

function AccountMenu({ onNavigate }: { onNavigate?: () => void }) {
  const auth = useAuth();
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const close = () => {
    setOpen(false);
    buttonRef.current?.focus();
  };
  useEscapeKey(() => {
    if (open) {
      close();
    }
  });

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onPointerDown = (event: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open ]);

  const focusItem = (direction: 1 | -1) => {
    const items = Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>("[data-menuitem]:not([aria-disabled='true'])") ?? [],
    );
    if (items.length === 0) {
      return;
    }
    const active = document.activeElement;
    const index = items.findIndex((item) => item === active);
    const next = index === -1 ? (direction === 1 ? 0 : items.length - 1) : (index + direction + items.length) % items.length;
    items[next].focus();
  };

  const onMenuKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusItem(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusItem(-1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusItem(1);
    } else if (event.key === "End") {
      event.preventDefault();
      focusItem(-1);
    }
  };

  const signOut = () => {
    auth.clear();
    setOpen(false);
    onNavigate?.();
  };

  return (
    <div className="xb-menu-wrap" ref={wrapRef}>
      <button
        ref={buttonRef}
        type="button"
        className="xb-app-account-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="xb-avatar" aria-hidden="true">
          {icon(USER_ICON)}
        </span>
        <span className="xb-sidebar__label">Account</span>
      </button>
      {open ? (
        <ul className="xb-menu" role="menu" aria-label="Account" ref={menuRef} onKeyDown={onMenuKeyDown}>
          <li role="none" className="xb-menu__header" aria-hidden="true">
            Account
          </li>
          <li role="none">
            <span role="menuitem" aria-disabled="true" className="xb-menu__item xb-menu__item--disabled" data-menuitem tabIndex={-1}>
              Profile <span className="xb-menu__soon">Soon</span>
            </span>
          </li>
          <li role="none">
            <span role="menuitem" aria-disabled="true" className="xb-menu__item xb-menu__item--disabled" data-menuitem tabIndex={-1}>
              Organization <span className="xb-menu__soon">Soon</span>
            </span>
          </li>
          <li role="none">
            <Link role="menuitem" className="xb-menu__item" data-menuitem to="/settings" onClick={() => { setOpen(false); onNavigate?.(); }}>
              Settings
            </Link>
          </li>
          <li role="none">
            {auth.isConfigured ? (
              <button role="menuitem" type="button" className="xb-menu__item" data-menuitem onClick={signOut}>
                Sign out
              </button>
            ) : (
              <Link role="menuitem" className="xb-menu__item" data-menuitem to="/session" onClick={() => { setOpen(false); onNavigate?.(); }}>
                Sign in
              </Link>
            )}
          </li>
        </ul>
      ) : null}
    </div>
  );
}

function SidebarBody({
  collapsed,
  onToggleCollapse,
  showCollapse,
  onNavigate,
}: {
  collapsed: boolean;
  onToggleCollapse: () => void;
  showCollapse: boolean;
  onNavigate?: () => void;
}) {
  return (
    <>
      <div className="xb-sidebar__brand">
        <BrandMark newTab compact={collapsed} />
      </div>
      <nav className="xb-sidebar__nav" aria-label="Primary">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            title={collapsed ? item.label : undefined}
            onClick={onNavigate}
            className={({ isActive }) => (isActive ? "xb-app-nav-link active" : "xb-app-nav-link")}
          >
            {icon(item.icon)}
            <span className="xb-app-nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="xb-sidebar__footer">
        <div className="xb-footer-row">
          <NotificationEntry />
          <ThemeToggle />
        </div>
        <AccountMenu onNavigate={onNavigate} />
        {showCollapse ? (
          <button
            type="button"
            className="xb-icon-btn"
            aria-expanded={!collapsed}
            aria-controls="xb-app-sidebar"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={onToggleCollapse}
          >
            {icon(collapsed ? CHEVRON_RIGHT : CHEVRON_LEFT)}
          </button>
        ) : null}
      </div>
    </>
  );
}

/** Mobile navigation drawer with dialog semantics. */
function MobileDrawer({ onClose }: { onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  useEscapeKey(onClose);
  useFocusRestore();

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  const trapTab = (event: React.KeyboardEvent) => {
    if (event.key !== "Tab") {
      return;
    }
    const items = Array.from(
      panelRef.current?.querySelectorAll<HTMLElement>(
        "a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])",
      ) ?? [],
    ).filter((item) => item.getAttribute("aria-disabled") !== "true");
    if (items.length === 0) {
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <>
      <button type="button" className="xb-app-scrim" aria-label="Dismiss navigation" onClick={onClose} />
      <aside
        ref={panelRef}
        id="xb-app-drawer"
        className="xb-sidebar xb-app-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Application navigation"
        onKeyDown={trapTab}
      >
        <div className="xb-app-drawer-head">
          <button ref={closeRef} type="button" className="xb-icon-btn" aria-label="Close navigation" onClick={onClose}>
            {icon(CLOSE_ICON)}
          </button>
        </div>
        <SidebarBody collapsed={false} onToggleCollapse={onClose} showCollapse={false} onNavigate={onClose} />
      </aside>
    </>
  );
}

/**
 * Authenticated workspace frame. Pages render as
 * children and supply their own content; the shell
 * only provides navigation, brand, account,
 * notification entry, theme, and the contextual
 * breadcrumb bar.
 */
export function AuthenticatedShell({
  crumbs,
  children,
}: {
  crumbs?: { label: string; href?: string }[];
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState<boolean>(() => storedSidebar() ?? prefersCollapsed());
  const [drawerOpen, setDrawerOpen] = useState(false);

  const toggleCollapse = () => {
    setCollapsed((value) => {
      const next = !value;
      try {
        window.localStorage.setItem(SIDEBAR_STORAGE_KEY, next ? "collapsed" : "expanded");
      } catch {
        // Private-mode storage failure must not break navigation.
      }
      return next;
    });
  };

  return (
    <div className="xb-app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside
        id="xb-app-sidebar"
        className={
          collapsed
            ? "xb-sidebar xb-app-sidebar xb-app-sidebar--desktop xb-sidebar--collapsed"
            : "xb-sidebar xb-app-sidebar xb-app-sidebar--desktop"
        }
        aria-label="Application"
      >
        <SidebarBody collapsed={collapsed} onToggleCollapse={toggleCollapse} showCollapse />
      </aside>
      {drawerOpen ? <MobileDrawer onClose={() => setDrawerOpen(false)} /> : null}
      <div className="xb-app-main">
        <div className="xb-app-contextbar">
          <button
            type="button"
            className="xb-icon-btn xb-hamburger"
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
            aria-controls="xb-app-drawer"
            onClick={() => setDrawerOpen(true)}
          >
            {icon(MENU_ICON)}
          </button>
          {crumbs && crumbs.length > 0 ? <Breadcrumbs trail={crumbs} /> : null}
        </div>
        <main id="main">
          <WorkspaceContainer>{children}</WorkspaceContainer>
        </main>
      </div>
    </div>
  );
}
