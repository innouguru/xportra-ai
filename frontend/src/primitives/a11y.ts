import { useEffect, useRef } from "react";

/**
 * Phase 10.8A accessibility primitives.
 *
 * Minimal focus/keyboard infrastructure for the
 * future drawer/modal work (10.8B+). No visual
 * output; no behavior change to existing UI.
 */

/** Invoke `onEscape` when Escape is pressed. */
export function useEscapeKey(onEscape: () => void): void {
  const ref = useRef(onEscape);
  ref.current = onEscape;
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        ref.current();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);
}

/**
 * Return focus to the previously focused element
 * when the owning component unmounts (drawer /
 * modal close pattern for 10.8B+).
 */
export function useFocusRestore(): void {
  const previous = useRef<Element | null>(null);
  useEffect(() => {
    previous.current = document.activeElement;
    return () => {
      if (previous.current instanceof HTMLElement) {
        previous.current.focus();
      }
    };
  }, []);
}
