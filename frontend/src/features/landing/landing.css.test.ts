import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const css = readFileSync(join(process.cwd(), "src", "features", "landing", "landing.css"), "utf-8");
const tokens = readFileSync(join(process.cwd(), "src", "theme", "tokens.css"), "utf-8");

/**
 * Landing stylesheet contract (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * Public chrome on canonical tokens only —
 * no second color system, no gradients, no
 * glassmorphism, no card grids.
 */

const REQUIRED_SELECTORS = [
  ".xb-land",
  ".xb-land-nav",
  ".xb-land-nav--scrolled",
  ".xb-land-wordmark",
  ".xb-land-nav__links",
  ".xb-land-main",
  ".xb-land-hero",
  ".xb-land-display",
  ".xb-land-lede",
  ".xb-land-ctas",
  ".xb-land-strip",
  ".xb-land-section",
  ".xb-land-cols",
  ".xb-land-reveal",
  ".xb-land-flow",
  ".xb-land-flow__steps",
  ".xb-land-footer",
] as const;

describe("landing styles", () => {
  it("defines every required landing selector", () => {
    for (const selector of REQUIRED_SELECTORS) {
      expect(css, selector).toContain(selector);
    }
  });

  it("carries no literal colors (tokens only)", () => {
    expect(css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
  });

  it("introduces no gradients, glassmorphism, or blur", () => {
    expect(css).not.toMatch(/gradient\(/);
    expect(css).not.toMatch(/backdrop-filter/);
    expect(css).not.toMatch(/blur\(/);
  });

  it("resolves every referenced token in the canonical token file", () => {
    const used = new Set<string>();
    for (const match of css.matchAll(/var\(\s*(--xb-[a-z0-9-]+)/g)) {
      used.add(match[1]);
    }
    expect(used.size).toBeGreaterThan(0);
    for (const token of used) {
      expect(tokens, token).toContain(`${token}:`);
    }
  });

  it("keeps the responsive and focus foundations", () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*860px\)/);
    expect(css).toMatch(/:focus-visible/);
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  });

  it("keeps the header sticky with a quiet token-based scrolled state", () => {
    const nav = css.match(/\.xb-land-nav\s*{([^}]*)}/);
    expect(nav).not.toBeNull();
    expect(nav![1]).toMatch(/position:\s*sticky/);
    expect(nav![1]).toMatch(/top:\s*0/);
    const scrolled = css.match(/\.xb-land-nav--scrolled\s*{([^}]*)}/);
    expect(scrolled).not.toBeNull();
    expect(scrolled![1]).toMatch(/var\(--xb-surface\)/);
    expect(scrolled![1]).toMatch(/var\(--xb-border-strong\)/);
  });

  it("drives calm motion from canonical motion tokens", () => {
    expect(css).toMatch(/\[data-anim/);
    expect(css).toMatch(/var\(--xb-motion-ease\)/);
    expect(css).toMatch(/var\(--xb-motion-base\)/);
    expect(css).toMatch(/\.xb-land-reveal/);
    expect(css).toMatch(/--reveal-index/);
  });

  it("animates the workflow highlight slowly with brand-only emphasis", () => {
    expect(css).toMatch(/@keyframes\s+xb-land-flow-dot/);
    expect(css).toMatch(/@keyframes\s+xb-land-flow-name/);
    expect(css).toMatch(/--step-index/);
    const flow = css.match(/\.xb-land-flow__dot\s*{([^}]*)}/);
    expect(flow).not.toBeNull();
    expect(flow![1]).toMatch(/12s/);
    expect(flow![1]).toMatch(/infinite/);
  });

  it("stops decorative motion under prefers-reduced-motion", () => {
    const reduce = css.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)([\s\S]*)$/);
    expect(reduce).not.toBeNull();
    expect(reduce![1]).toMatch(/animation:\s*none/);
    expect(reduce![1]).toMatch(/transition:\s*none/);
    expect(reduce![1]).toMatch(/opacity:\s*1/);
  });

  it("sets the hero from the reference scale (serif, 25–40px natural wrap)", () => {
    const display = css.match(/\.xb-land-display\s*{([^}]*)}/);
    expect(display).not.toBeNull();
    expect(display![1]).toMatch(/var\(--xb-font-display\)/);
    expect(display![1]).toMatch(/clamp\(1\.5625rem,[^,]+,\s*2\.5rem\)/);
    expect(display![1]).not.toMatch(/<br/);
    const lede = css.match(/\.xb-land-lede\s*{([^}]*)}/);
    expect(lede).not.toBeNull();
    expect(lede![1]).toMatch(/1\.03125rem/);
    expect(lede![1]).toMatch(/var\(--xb-text-secondary\)/);
  });

  it("keeps the heading dominant but proportionate to the supporting copy", () => {
    const display = css.match(/\.xb-land-display\s*{([^}]*)}/);
    expect(display).not.toBeNull();
    const max = display![1].match(/clamp\([\d.]+\w*,\s*[^,]+,\s*([\d.]+)rem\)/);
    expect(max).not.toBeNull();
    const headingPx = Number.parseFloat(max![1]) * 16;
    const lede = css.match(/\.xb-land-lede\s*{([^}]*)}/)![1].match(
      /font-size:\s*([\d.]+)rem/,
    )!;
    const ledePx = Number.parseFloat(lede[1]) * 16;
    // 40px over 16.5px: clearly dominant (~2.4x), not aggressive (~2.8x).
    expect(headingPx).toBeGreaterThan(ledePx);
    expect(headingPx / ledePx).toBeLessThan(2.6);
  });

  it("composes the desktop hero wide-heading-first within 1150–1200px", () => {
    const display = css.match(/\.xb-land-display\s*{([^}]*)}/);
    expect(display).not.toBeNull();
    const width = display![1].match(/max-width:\s*([\d.]+)rem/);
    expect(width).not.toBeNull();
    const px = Number.parseFloat(width![1]) * 16;
    expect(px).toBeGreaterThanOrEqual(1150);
    expect(px).toBeLessThanOrEqual(1200);
    // Left-aligned, never centered or force-broken.
    expect(display![1]).toMatch(/text-align:\s*left/);
    expect(display![1]).not.toMatch(/text-align:\s*center/);
  });

  it("keeps supporting copy narrower than the heading and the CTA row compact", () => {
    const displayWidth = css.match(/\.xb-land-display\s*{([^}]*)}/)![1].match(
      /max-width:\s*([\d.]+)rem/,
    )!;
    const lede = css.match(/\.xb-land-lede\s*{([^}]*)}/);
    expect(lede).not.toBeNull();
    const ledeWidth = lede![1].match(/max-width:\s*([\d.]+)rem/);
    expect(ledeWidth).not.toBeNull();
    // Deliberate secondary block: substantially wider than a
    // narrow column, still comfortably narrower than the heading.
    const ledeRem = Number.parseFloat(ledeWidth![1]);
    expect(ledeRem).toBeGreaterThanOrEqual(52);
    expect(ledeRem).toBeLessThanOrEqual(60);
    expect(ledeRem).toBeLessThan(Number.parseFloat(displayWidth[1]));
    const ctas = css.match(/\.xb-land-ctas\s*{([^}]*)}/);
    expect(ctas).not.toBeNull();
    expect(ctas![1]).toMatch(/display:\s*flex/);
    expect(ctas![1]).toMatch(/flex-wrap:\s*wrap/);
  });

  it("preserves the desktop gutter and editorial alignment", () => {
    const main = css.match(/\.xb-land-main\s*{([^}]*)}/);
    expect(main).not.toBeNull();
    expect(main![1]).toMatch(/padding:\s*0 3rem/);
    expect(main![1]).toMatch(/margin:\s*0 auto/);
    // Broad canvas: at 1366px the content spans the viewport
    // behind comfortable gutters instead of sitting in a
    // narrow centered column, with room for the heading cap.
    const canvas = main![1].match(/max-width:\s*([\d.]+)rem/);
    expect(canvas).not.toBeNull();
    const displayWidth = css.match(/\.xb-land-display\s*{([^}]*)}/)![1].match(
      /max-width:\s*([\d.]+)rem/,
    )!;
    expect(Number.parseFloat(canvas![1])).toBeGreaterThanOrEqual(84);
    expect(Number.parseFloat(canvas![1])).toBeGreaterThanOrEqual(
      Number.parseFloat(displayWidth[1]) + 6,
    );
    // Narrow widths keep mobile gutters; the heading cap
    // below simply stops binding so copy wraps naturally.
    const mobile = css.match(/@media\s*\(max-width:\s*860px\)([\s\S]*)$/);
    expect(mobile).not.toBeNull();
    expect(mobile![1]).toMatch(/1\.25rem/);
  });

  it("distributes the supporting strip across three equal columns", () => {
    const strip = css.match(/\.xb-land-strip\s*{([^}]*)}/);
    expect(strip).not.toBeNull();
    expect(strip![1]).toMatch(/display:\s*grid/);
    expect(strip![1]).toMatch(/grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/);
    expect(strip![1]).toMatch(/3\.25rem/);
    expect(strip![1]).toMatch(/width:\s*100%/);
    // Readable internal measure; the columns distribute,
    // the text does not stretch to full width.
    const item = css.match(/\.xb-land-strip__item\s*{([^}]*)}/);
    expect(item).not.toBeNull();
    expect(item![1]).toMatch(/max-width:\s*13\.75rem/);
    // Narrow widths keep the existing stacking behavior.
    const mobile = css.match(/@media\s*\(max-width:\s*860px\)([\s\S]*)$/);
    expect(mobile).not.toBeNull();
    expect(mobile![1]).toMatch(/\.xb-land-strip\s*{[^}]*grid-template-columns:\s*1fr/);
  });

  it("reuses the established brand mark in the header lockup on tokens", () => {
    const lockup = css.match(/\.xb-land-wordmark\s+\.brand-glyph\s*{([^}]*)}/);
    expect(lockup).not.toBeNull();
    expect(lockup![1]).toMatch(/var\(--xb-brand\)/);
    expect(lockup![1]).toMatch(/var\(--xb-brand-foreground\)/);
    expect(lockup![1]).toMatch(/var\(--xb-radius-sm\)/);
    const wordmark = css.match(/\.xb-land-wordmark\s*{([^}]*)}/);
    expect(wordmark).not.toBeNull();
    expect(wordmark![1]).toMatch(/display:\s*inline-flex/);
    expect(wordmark![1]).toMatch(/align-items:\s*center/);
  });
});
