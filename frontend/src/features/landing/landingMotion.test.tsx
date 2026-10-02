import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useScrolled, useHeroReady, useReveal } from "./landingMotion";

/**
 * Landing motion-hook contract.
 *
 * Hooks report honest UI state (scroll
 * position, first paint, viewport entry) for
 * calm CSS-driven motion. No hook invents
 * content or carries meaning — visibility is
 * always achievable without animation.
 */

function setScrollY(value: number) {
  Object.defineProperty(window, "scrollY", {
    configurable: true,
    writable: true,
    value,
  });
}

function ScrolledProbe() {
  const scrolled = useScrolled();
  return <div data-testid="probe" data-scrolled={scrolled ? "true" : "false"} />;
}

function HeroProbe() {
  const ready = useHeroReady();
  return <div data-testid="probe" data-ready={ready ? "true" : "false"} />;
}

function RevealProbe() {
  const { ref, visible } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} data-testid="probe" data-visible={visible ? "true" : "false"} />
  );
}

/** Minimal controllable IntersectionObserver stand-in. */
class FakeObserver {
  static instances: FakeObserver[] = [];
  callback: IntersectionObserverCallback;
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
    FakeObserver.instances.push(this);
  }
  observe() {
    // No-op: visibility is driven explicitly via `trigger`.
  }
  unobserve() {
    // No-op.
  }
  disconnect() {
    // No-op.
  }
  trigger(isIntersecting: boolean) {
    this.callback(
      [{ isIntersecting } as IntersectionObserverEntry],
      this as unknown as IntersectionObserver,
    );
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeObserver.instances = [];
  setScrollY(0);
});

describe("useScrolled", () => {
  it("reports false at the top and true once past the threshold", async () => {
    setScrollY(0);
    render(<ScrolledProbe />);
    expect(screen.getByTestId("probe")).toHaveAttribute("data-scrolled", "false");
    setScrollY(120);
    fireEvent.scroll(window);
    await waitFor(() => {
      expect(screen.getByTestId("probe")).toHaveAttribute("data-scrolled", "true");
    });
    setScrollY(0);
    fireEvent.scroll(window);
    await waitFor(() => {
      expect(screen.getByTestId("probe")).toHaveAttribute("data-scrolled", "false");
    });
  });
});

describe("useHeroReady", () => {
  it("flips ready on the frame after mount", async () => {
    render(<HeroProbe />);
    await waitFor(() => {
      expect(screen.getByTestId("probe")).toHaveAttribute("data-ready", "true");
    });
  });
});

describe("useReveal", () => {
  it("reveals immediately where IntersectionObserver is unavailable", () => {
    vi.stubGlobal("IntersectionObserver", undefined);
    render(<RevealProbe />);
    expect(screen.getByTestId("probe")).toHaveAttribute("data-visible", "true");
  });

  it("stays hidden until the element enters the viewport", async () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    render(<RevealProbe />);
    expect(screen.getByTestId("probe")).toHaveAttribute("data-visible", "false");
    expect(FakeObserver.instances).toHaveLength(1);
    FakeObserver.instances[0].trigger(false);
    expect(screen.getByTestId("probe")).toHaveAttribute("data-visible", "false");
    FakeObserver.instances[0].trigger(true);
    await waitFor(() => {
      expect(screen.getByTestId("probe")).toHaveAttribute("data-visible", "true");
    });
  });
});
