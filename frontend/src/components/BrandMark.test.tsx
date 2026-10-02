import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { BrandMark } from "./BrandMark";

describe("BrandMark", () => {
  it("renders the wordmark home link with its tagline", () => {
    render(
      <MemoryRouter>
        <BrandMark />
      </MemoryRouter>,
    );
    const home = screen.getByRole("link", { name: "Xportra AI home" });
    expect(home.getAttribute("href")).toBe("/");
    expect(home).toHaveTextContent("Xportra");
    expect(screen.getByText("Export Compliance Intelligence")).toBeInTheDocument();
  });

  it("keeps the glyph slot free of fabricated artwork", () => {
    const { container } = render(
      <MemoryRouter>
        <BrandMark />
      </MemoryRouter>,
    );
    const glyph = container.querySelector(".brand-glyph");
    expect(glyph).not.toBeNull();
    expect(glyph).toHaveAttribute("aria-hidden", "true");
    // No invented logo geometry: no SVG, paths, images, or canvas.
    expect(glyph?.querySelector("svg, path, img, canvas")).toBeNull();
  });
});
