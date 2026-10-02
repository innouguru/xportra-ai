import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";

/**
 * Landing-page motion helpers (public route only).
 *
 * Calm, honest motion: a quiet scrolled-header
 * state, a one-shot hero entrance, and
 * viewport reveals for editorial sections. No
 * animation carries meaning on its own — every
 * animated element is fully legible as static
 * text, and all decorative motion is disabled
 * under `prefers-reduced-motion` in
 * `landing.css`. No animation dependencies;
 * IntersectionObserver is platform API with an
 * immediate-visible fallback where unsupported.
 */

/** True once the window has scrolled past `threshold` CSS pixels. */
export function useScrolled(threshold = 8): boolean {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const read = () => {
      setScrolled(window.scrollY > threshold);
    };
    read();
    window.addEventListener("scroll", read, { passive: true });
    return () => {
      window.removeEventListener("scroll", read);
    };
  }, [threshold]);
  return scrolled;
}

/** True on the frame after first paint — triggers the one-shot hero entrance. */
export function useHeroReady(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (typeof window.requestAnimationFrame === "function") {
      const frame = window.requestAnimationFrame(() => setReady(true));
      return () => window.cancelAnimationFrame(frame);
    }
    const timer = window.setTimeout(() => setReady(true), 16);
    return () => window.clearTimeout(timer);
  }, []);
  return ready;
}

/** Observes one element and reports when it has entered the viewport (once). */
export function useReveal<T extends HTMLElement = HTMLDivElement>(): {
  ref: RefObject<T | null>;
  visible: boolean;
} {
  const ref = useRef<T | null>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (node === null) {
      return;
    }
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.2 },
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
    };
  }, []);
  return { ref, visible };
}
