import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const css = readFileSync(join(process.cwd(), "src", "shell", "shell.css"), "utf-8");
const tokens = readFileSync(join(process.cwd(), "src", "theme", "tokens.css"), "utf-8");

/**
 * Phase 10.8B shell stylesheet contract.
 *
 * Shell styles consume canonical tokens only and
 * keep the responsive / focus / reduced-motion
 * foundations for the sidebar + drawer behavior.
 */

const REQUIRED_SELECTORS = [
  ".xb-app",
  ".xb-app-sidebar",
  ".xb-app-main",
  ".xb-app-contextbar",
  ".xb-hamburger",
  ".xb-app-nav-link",
  ".xb-app-nav-label",
  ".xb-app-drawer",
  ".xb-app-scrim",
  ".xb-app-account-btn",
  ".xb-avatar",
  ".xb-menu",
  ".xb-icon-btn",
  ".xb-popover",
  ".xb-footer-row",
] as const;

describe("shell styles", () => {
  it("defines every required shell selector", () => {
    for (const selector of REQUIRED_SELECTORS) {
      expect(css, selector).toContain(selector);
    }
  });

  it("sizes the sidebar at approximately 240px", () => {
    const sidebar = css.match(/\.xb-app-sidebar\s*{([^}]*)}/);
    expect(sidebar).not.toBeNull();
    expect(sidebar![1]).toMatch(/width:\s*240px/);
  });

  it("marks selected navigation with more than color", () => {
    const active = css.match(/\.xb-app-nav-link\.active\s*{([^}]*)}/);
    expect(active).not.toBeNull();
    expect(active![1]).toMatch(/box-shadow/);
    expect(active![1]).toMatch(/font-weight/);
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

  it("keeps the drawer, focus, and reduced-motion foundations", () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*860px\)/);
    expect(css).toMatch(/:focus-visible/);
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  });

  it("wraps the contextual bar and sizes to the dynamic viewport", () => {
    const bar = css.match(/\.xb-app-contextbar\s*{([^}]*)}/);
    expect(bar).not.toBeNull();
    expect(bar![1]).toMatch(/flex-wrap:\s*wrap/);
    expect(css).toMatch(/100dvh/);
  });
});
