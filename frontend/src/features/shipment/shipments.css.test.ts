import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const css = readFileSync(join(process.cwd(), "src", "features", "shipment", "shipments.css"), "utf-8");
const tokens = readFileSync(join(process.cwd(), "src", "theme", "tokens.css"), "utf-8");

/**
 * Archive stylesheet contract (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * Search + chip + grouped-worklist styles
 * consume canonical tokens only; the single
 * 860px breakpoint carries the mobile
 * transformation.
 */

const REQUIRED_SELECTORS = [
  ".xb-archive-toolbar",
  ".xb-archive-search",
  ".xb-archive-chips",
  ".xb-chip",
  ".xb-archive-group-label",
] as const;

describe("archive styles", () => {
  it("defines every required archive selector", () => {
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

  it("keeps the responsive and focus foundations", () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*860px\)/);
    expect(css).toMatch(/:focus-visible/);
  });

  it("wraps the toolbar and chips instead of overflowing on narrow widths", () => {
    expect(css).toMatch(/\.xb-archive-toolbar\s*{[^}]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/\.xb-archive-chips\s*{[^}]*flex-wrap:\s*wrap/);
    expect(css).not.toMatch(/\.xb-archive-table/);
    expect(css).not.toMatch(/\.xb-archive-cards/);
  });
});
