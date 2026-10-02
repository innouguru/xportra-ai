import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const css = readFileSync(join(process.cwd(), "src", "primitives", "primitives.css"), "utf-8");
const tokens = readFileSync(join(process.cwd(), "src", "theme", "tokens.css"), "utf-8");

/**
 * Phase 10.8A primitive stylesheet contract.
 *
 * Primitive styles consume canonical tokens only:
 * no literal colors, no gradients, no glass.
 * Every referenced `--xb-*` token must exist in
 * the canonical token file, and the responsive /
 * reduced-motion / focus foundations must hold.
 */

const REQUIRED_SELECTORS = [
  ".xb-workspace",
  ".xb-page-header",
  ".xb-breadcrumbs",
  ".xb-back",
  ".xb-topbar",
  ".xb-sidebar",
  ".xb-status",
  ".xb-badge",
  ".xb-metric",
  ".xb-attention",
  ".xb-empty",
  ".xb-loading",
  ".xb-spinner",
  ".xb-error",
  ".xb-card-grid",
  ".xb-card",
  ".xb-row",
  ".xb-ledger-row",
  ".xb-summary",
  ".xb-req-card",
  ".xb-theme-control",
  ".xb-form",
  ".xb-form-section",
  ".xb-field",
  ".xb-input",
  ".xb-field__error",
  ".xb-check",
] as const;

describe("primitive styles", () => {
  it("defines every required primitive selector", () => {
    for (const selector of REQUIRED_SELECTORS) {
      expect(css, selector).toContain(selector);
    }
  });

  it("carries no literal colors (tokens only)", () => {
    expect(css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
  });

  it("introduces no gradients or glassmorphism", () => {
    expect(css).not.toMatch(/gradient\(/);
    expect(css).not.toMatch(/backdrop-filter/);
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

  it("keeps the responsive, focus, and reduced-motion foundations", () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*860px\)/);
    expect(css).toMatch(/@media\s*\(max-width:\s*640px\)/);
    expect(css).toMatch(/:focus-visible/);
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  });

  it("stacks card grids to one column on mobile", () => {
    const mobile = css.match(/@media\s*\(max-width:\s*860px\)([\s\S]*)$/);
    expect(mobile).not.toBeNull();
    expect(mobile![1]).toMatch(/\.xb-card-grid\s*{[^}]*grid-template-columns:\s*1fr/);
  });

  it("sets page descriptions from the readable lead token", () => {
    const description = css.match(/\.xb-page-header__description\s*{([^}]*)}/);
    expect(description).not.toBeNull();
    expect(description![1]).toMatch(/var\(--xb-text-lead\)/);
  });
});
