import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const css = readFileSync(join(process.cwd(), "src", "theme", "tokens.css"), "utf-8");

/**
 * Phase 10.8A canonical token contract.
 *
 * The `xb-` system is the authority for new
 * interface work. These tests pin token coverage
 * in both themes, brand/semantic separation, and
 * the no-literals / no-gradient / no-glass rules
 * so components cannot silently regress to
 * hard-coded theme colors.
 */

const REQUIRED_TOKENS = [
  "--xb-background",
  "--xb-surface",
  "--xb-surface-elevated",
  "--xb-border",
  "--xb-border-strong",
  "--xb-text-primary",
  "--xb-text-secondary",
  "--xb-text-muted",
  "--xb-brand",
  "--xb-brand-hover",
  "--xb-brand-foreground",
  "--xb-brand-bg",
  "--xb-success",
  "--xb-success-bg",
  "--xb-warning",
  "--xb-warning-bg",
  "--xb-danger",
  "--xb-danger-bg",
  "--xb-info",
  "--xb-info-bg",
  "--xb-neutral-bg",
  "--xb-focus",
  "--xb-focus-ring-width",
  "--xb-disabled",
  "--xb-text-display",
  "--xb-text-title",
  "--xb-text-section",
  "--xb-text-card",
  "--xb-text-lead",
  "--xb-text-body",
  "--xb-text-small",
  "--xb-text-meta",
  "--xb-space-xs",
  "--xb-space-sm",
  "--xb-space-md",
  "--xb-space-lg",
  "--xb-space-xl",
  "--xb-page-gutter",
  "--xb-card-padding",
  "--xb-control-height",
  "--xb-radius-sm",
  "--xb-radius-md",
  "--xb-radius-lg",
  "--xb-shadow-sm",
  "--xb-shadow-md",
  "--xb-motion-fast",
  "--xb-motion-base",
] as const;

function darkBlock(): string {
  const match = css.match(/:root\s*,\s*:root\[data-theme="dark"\]\s*{([\s\S]*?)}/);
  expect(match).not.toBeNull();
  return match![1];
}

function lightBlock(): string {
  const match = css.match(/:root\[data-theme="light"\]\s*{([\s\S]*?)}/);
  expect(match).not.toBeNull();
  return match![1];
}

function tokenValue(block: string, name: string): string | null {
  const match = block.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  return match ? match[1].trim() : null;
}

describe("canonical tokens", () => {
  it("defines every required token in the dark theme", () => {
    const dark = darkBlock();
    for (const token of REQUIRED_TOKENS) {
      expect(tokenValue(dark, token), token).toBeTruthy();
    }
  });

  it("defines every required token in the light theme", () => {
    const light = lightBlock();
    for (const token of REQUIRED_TOKENS) {
      expect(tokenValue(light, token), token).toBeTruthy();
    }
  });

  it("keeps the dark brand direction (deep green-black, off-white, electric lime)", () => {
    const dark = darkBlock();
    expect(tokenValue(dark, "--xb-background")).toBe("#0d1512");
    expect(tokenValue(dark, "--xb-text-primary")).toBe("#edebe1");
    expect(tokenValue(dark, "--xb-brand")).toBe("#c7f464");
  });

  it("keeps the brand accent distinct from semantic colors in both themes", () => {
    for (const block of [darkBlock(), lightBlock()]) {
      const brand = tokenValue(block, "--xb-brand");
      expect(brand).toBeTruthy();
      for (const token of ["--xb-success", "--xb-warning", "--xb-danger", "--xb-info"] as const) {
        expect(tokenValue(block, token)).not.toBe(brand);
      }
    }
  });

  it("changes theme in color only (shared type/spacing/radius/motion)", () => {
    const dark = darkBlock();
    const light = lightBlock();
    for (const token of [
      "--xb-text-display",
      "--xb-text-title",
      "--xb-text-lead",
      "--xb-space-md",
      "--xb-radius-md",
      "--xb-motion-base",
      "--xb-control-height",
    ] as const) {
      expect(tokenValue(light, token), token).toBe(tokenValue(dark, token));
    }
  });

  it("scatters no literal colors outside token blocks", () => {
    const withoutTokens = css
      .replace(/:root\s*,\s*:root\[data-theme="dark"\]\s*{[\s\S]*?}/, "")
      .replace(/:root\[data-theme="light"\]\s*{[\s\S]*?}/, "");
    expect(withoutTokens.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
  });

  it("introduces no gradients or glassmorphism", () => {
    expect(css).not.toMatch(/gradient\(/);
    expect(css).not.toMatch(/backdrop-filter/);
  });
});

/**
 * Phase 10.8A.1 readability contract.
 *
 * The canonical scale keeps a 16px body
 * baseline, 13px minimum micro-text, and
 * strong separated hierarchy (display >
 * title > section > card/lead > body >
 * small > meta). Both themes share it.
 */
describe("readable type scale", () => {
  /** Resolve a token to px (16px root), following clamp() to its max. */
  function tokenPx(block: string, name: string): number {
    const value = tokenValue(block, name);
    expect(value, name).toBeTruthy();
    const match =
      value!.match(/clamp\([^,]+,[^,]+,\s*([0-9.]+)rem\s*\)/) ?? value!.match(/^([0-9.]+)rem$/);
    expect(match, `${name}=${value}`).not.toBeNull();
    return parseFloat(match![1]) * 16;
  }

  it("meets the readable minimums with real hierarchy in both themes", () => {
    for (const block of [darkBlock(), lightBlock()]) {
      const display = tokenPx(block, "--xb-text-display");
      const title = tokenPx(block, "--xb-text-title");
      const section = tokenPx(block, "--xb-text-section");
      const card = tokenPx(block, "--xb-text-card");
      const lead = tokenPx(block, "--xb-text-lead");
      const body = tokenPx(block, "--xb-text-body");
      const small = tokenPx(block, "--xb-text-small");
      const meta = tokenPx(block, "--xb-text-meta");
      expect(display).toBeGreaterThanOrEqual(48);
      expect(title).toBeGreaterThanOrEqual(28);
      expect(section).toBeGreaterThanOrEqual(20);
      expect(card).toBeGreaterThanOrEqual(18);
      expect(lead).toBeGreaterThanOrEqual(17);
      expect(body).toBe(16);
      expect(small).toBeGreaterThanOrEqual(14);
      expect(meta).toBeGreaterThanOrEqual(13);
      expect([display, title, section, card, body, small, meta]).toEqual(
        [display, title, section, card, body, small, meta].sort((a, b) => b - a),
      );
    }
  });

  it("keeps the hero strong on small screens without new breakpoints", () => {
    const display = tokenValue(darkBlock(), "--xb-text-display");
    const floor = display!.match(/clamp\(\s*([0-9.]+)rem/);
    expect(floor).not.toBeNull();
    expect(parseFloat(floor![1]) * 16).toBeGreaterThanOrEqual(40);
  });

  it("keeps generous body leading", () => {
    for (const block of [darkBlock(), lightBlock()]) {
      expect(parseFloat(tokenValue(block, "--xb-leading-body")!)).toBeGreaterThanOrEqual(1.5);
    }
  });

  it("keeps muted text AA-readable on both themes (10.8J audit)", () => {
    /** WCAG relative luminance for a #rrggbb token. */
    function luminance(hex: string): number {
      const clean = hex.replace("#", "");
      const channels = [0, 2, 4].map((i) => {
        const channel = parseInt(clean.slice(i, i + 2), 16) / 255;
        return channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    }
    function ratio(foreground: string, background: string): number {
      const high = Math.max(luminance(foreground), luminance(background));
      const low = Math.min(luminance(foreground), luminance(background));
      return (high + 0.05) / (low + 0.05);
    }
    for (const [block, surfaces] of [
      [darkBlock(), ["--xb-background", "--xb-surface"]],
      [lightBlock(), ["--xb-background", "--xb-surface"]],
    ] as const) {
      const muted = tokenValue(block, "--xb-text-muted")!;
      for (const surface of surfaces) {
        expect(ratio(muted, tokenValue(block, surface)!), `${muted} on ${surface}`).toBeGreaterThanOrEqual(
          4.5,
        );
      }
    }
  });
});
