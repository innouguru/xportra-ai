import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const css = readFileSync(join(process.cwd(), "src", "index.css"), "utf-8");

/**
 * Phase 10.7B visual system contract.
 *
 * Colors flow through centralized `:root` tokens only:
 * components reference variables, never literals. These
 * tests pin the token surface, the dark sidebar layout
 * structure, and the accessibility rules so the system
 * cannot silently regress to scattered values.
 */

const SEMANTIC_TOKENS = [
  "--background",
  "--surface",
  "--surface-elevated",
  "--border",
  "--text-primary",
  "--text-secondary",
  "--text-muted",
  "--brand",
  "--brand-hover",
  "--brand-foreground",
  "--success",
  "--warning",
  "--error",
  "--info",
] as const;

const LEGACY_ALIASES = [
  "--paper",
  "--surface-warm",
  "--ink",
  "--ink-soft",
  "--muted",
  "--line",
  "--line-strong",
  "--rule-dark",
  "--accent",
  "--accent-deep",
  "--accent-ink",
  "--accent-wash",
  "--info-wash",
  "--attention",
  "--attention-wash",
  "--error-wash",
  "--success",
  "--success-wash",
] as const;

function rootBlock(): string {
  const match = css.match(/:root\s*{([^}]*)}/);
  expect(match).not.toBeNull();
  return match![1];
}

function tokenValue(block: string, name: string): string | null {
  const match = block.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  return match ? match[1].trim() : null;
}

describe("design tokens", () => {
  it("defines every semantic token with a non-empty value", () => {
    const root = rootBlock();
    for (const token of SEMANTIC_TOKENS) {
      const value = tokenValue(root, token);
      expect(value, token).toBeTruthy();
    }
  });

  it("keeps every legacy alias defined for existing components", () => {
    const root = rootBlock();
    for (const token of LEGACY_ALIASES) {
      expect(tokenValue(root, token), token).toBeTruthy();
    }
  });

  it("keeps the brand accent distinct from compliance-state colors", () => {
    const root = rootBlock();
    const brand = tokenValue(root, "--brand");
    expect(brand).toBeTruthy();
    for (const token of ["--success", "--warning", "--error", "--info"] as const) {
      expect(tokenValue(root, token)).not.toBe(brand);
    }
  });

  it("uses a dark foundation with off-white primary text", () => {
    const root = rootBlock();
    expect(tokenValue(root, "--background")).toBe("#0b0e0c");
    expect(tokenValue(root, "--text-primary")).toBe("#f2f4ef");
  });

  it("scatters no literal colors outside :root", () => {
    const withoutRoot = css.replace(/:root\s*{[^}]*}/, "");
    const literals = withoutRoot.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [];
    expect(literals).toEqual([]);
  });
});

describe("visual-system structure", () => {
  it("lays the shell out as a sidebar on wide screens", () => {
    expect(css).toMatch(/@media\s*\(min-width:\s*1100px\)/);
    const sidebar = css.match(/@media\s*\(min-width:\s*1100px\)[\s\S]*?\.topbar\s*{([^}]*)}/);
    expect(sidebar).not.toBeNull();
    expect(sidebar![1]).toMatch(/flex-direction:\s*column/);
  });

  it("keeps the wrapping topbar behavior for narrow screens", () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*860px\)/);
  });

  it("keeps visible focus and reduced-motion rules", () => {
    expect(css).toMatch(/:focus-visible/);
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  });

  it("paints primary actions with the brand token", () => {
    const primary = css.match(/\.primary-button\s*{([^}]*)}/);
    expect(primary).not.toBeNull();
    expect(primary![1]).toMatch(/var\(--brand\)/);
    expect(primary![1]).toMatch(/var\(--brand-foreground\)/);
  });

  it("keeps the required component selectors", () => {
    for (const selector of [
      ".conversation-panel",
      ".conversation-overlay",
      ".landing-display",
      ".landing-meta",
      ".badge",
      ".chip",
      ".finding-card",
      ".terminal-banner",
      ".history-entry",
    ]) {
      expect(css, selector).toContain(selector);
    }
  });
});
