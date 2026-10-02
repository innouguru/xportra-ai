import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Phase 10.8A theme infrastructure.
 *
 * - Dark is the primary Xportra brand experience;
 *   light is supported (R-10.8.6, superseding the
 *   Phase 10.7B theme-switcher exclusion).
 * - The resolved theme is published as
 *   `data-theme` on `<html>`; all color flows
 *   through `theme/tokens.css` so component
 *   styles never duplicate per theme.
 * - With no stored preference the system
 *   preference applies (and keeps following it
 *   while mode is `system`).
 * - No global state library: one context plus
 *   `localStorage`, kept entirely client-side.
 * - Safe outside a provider (isolated component
 *   tests): `useTheme` falls back to the dark
 *   brand default.
 */

export type ThemeMode = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "xportra.theme.mode.v1";
export const THEME_MODES: readonly ThemeMode[] = ["light", "dark", "system"];

function systemTheme(): ResolvedTheme {
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  return "dark";
}

function storedMode(): ThemeMode | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw === "light" || raw === "dark" || raw === "system" ? raw : null;
  } catch {
    return null;
  }
}

function applyTheme(theme: ResolvedTheme): void {
  if (typeof document !== "undefined") {
    document.documentElement.dataset.theme = theme;
  }
}

interface ThemeState {
  /** Explicit preference (`system` follows the OS setting). */
  mode: ThemeMode;
  /** Concrete theme currently applied to the document. */
  resolved: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => storedMode() ?? "system");
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    mode === "system" ? systemTheme() : mode,
  );

  // Follow the OS setting while no explicit choice is stored.
  useEffect(() => {
    if (mode !== "system" || typeof window.matchMedia !== "function") {
      return undefined;
    }
    const query = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = (event: MediaQueryListEvent) => {
      setResolved(event.matches ? "light" : "dark");
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [mode]);

  useEffect(() => {
    applyTheme(resolved);
  }, [resolved]);

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    setResolved(next === "system" ? systemTheme() : next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private-mode storage failure must not break theming.
    }
  }, []);

  const value = useMemo<ThemeState>(() => ({ mode, resolved, setMode }), [mode, resolved, setMode]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const state = useContext(ThemeContext);
  if (state !== null) {
    return state;
  }
  // Provider-free fallback for isolated tests and
  // non-themed legacy surfaces: dark brand default.
  return {
    mode: "dark",
    resolved: "dark",
    setMode: () => undefined,
  };
}

/**
 * Accessible theme selector for the future
 * Settings/account experience (Phase 10.8I owns
 * final placement). Native radios in a
 * fieldset/legend group: keyboard-operable with
 * visible focus by construction.
 */
export function ThemeControl() {
  const { mode, setMode } = useTheme();
  return (
    <fieldset className="xb-theme-control">
      <legend>Theme</legend>
      {THEME_MODES.map((option) => (
        <label key={option} className="xb-theme-control__option">
          <input
            type="radio"
            name="xportra-theme"
            value={option}
            checked={mode === option}
            onChange={() => setMode(option)}
          />
          {option === "light" ? "Light" : option === "dark" ? "Dark" : "System"}
        </label>
      ))}
    </fieldset>
  );
}
