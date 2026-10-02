import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../../app/AuthContext";
import { WorkflowProvider } from "../../app/WorkflowContext";
import { ThemeProvider } from "../../theme/theme";
import { LandingPage } from "./LandingPage";

/**
 * Landing contract (approved redesign reference
 * `docs/design/xportra-ui-redesign.*`).
 *
 * Public nav offers only Sign In (real sign-in
 * route) and Get Started (real start route) — no
 * public "Start a Shipment" CTA anywhere. The
 * hero is one natural sentence. Logged-in
 * rendering seeds a real session + workflow
 * record to prove the public page never leaks
 * workspace navigation.
 */

function stubMatchMedia() {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

function renderLanding(signedIn = false) {
  stubMatchMedia();
  if (signedIn) {
    window.sessionStorage.setItem(
      "xportra.workflow-record.v1",
      JSON.stringify({
        id: "11111111-1111-1111-1111-111111111111",
        tenant_id: "22222222-2222-2222-2222-222222222222",
        case_id: "33333333-3333-3333-3333-333333333333",
        shipment_id: null,
        state: "evidence_pending",
        rounds: [],
        supplied_evidence_ids: [],
        open_requirements: [],
      }),
    );
  }
  render(
    <MemoryRouter initialEntries={["/"]}>
      <AuthProvider initial={signedIn ? { token: "test-token" } : {}}>
        <WorkflowProvider>
          <ThemeProvider>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/start" element={<div>Start screen</div>} />
              <Route path="/session" element={<div>Session screen</div>} />
            </Routes>
          </ThemeProvider>
        </WorkflowProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("LandingPage hero", () => {
  it("presents one natural-sentence heading with no forced breaks", () => {
    renderLanding();
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(
      "Xportra tells you exactly what your shipment needs to clear export compliance, and why.",
    );
    expect(headings[0].querySelector("br")).toBeNull();
    expect(
      screen.getByText(/works out the certificates, permits, and documentation required/i),
    ).toBeInTheDocument();
  });

  it("offers only Sign In and Get Started on real routes", () => {
    renderLanding();
    expect(screen.queryByText(/start a shipment/i)).toBeNull();
    const started = screen.getAllByRole("link", { name: "Get Started" });
    expect(started.length).toBeGreaterThan(0);
    for (const link of started) {
      expect(link.getAttribute("href")).toBe("/start");
    }
    const signins = screen.getAllByRole("link", { name: "Sign In" });
    expect(signins.length).toBeGreaterThan(0);
    for (const link of signins) {
      expect(link.getAttribute("href")).toBe("/session");
    }
    const nav = screen.getByRole("navigation", { name: "Public" });
    expect(within(nav).getAllByRole("link")).toHaveLength(2);
  });
});

describe("LandingPage header", () => {
  it("pairs the established brand mark with the wordmark in one home link", () => {
    renderLanding();
    const home = screen.getByRole("link", { name: "Xportra home" });
    expect(home.getAttribute("href")).toBe("/");
    expect(home).toHaveClass("xb-land-wordmark");
    // Reuses the BrandMark glyph slot: no new logo, no icon, no emoji.
    const glyph = home.querySelector(".brand-glyph");
    expect(glyph).not.toBeNull();
    expect(glyph).toHaveAttribute("aria-hidden", "true");
    expect(glyph?.textContent).toBe("X");
    expect(glyph?.querySelector("svg, path, img, canvas")).toBeNull();
    expect(home.textContent).toContain("Xportra.");
  });

  it("stays sticky and gains a quiet scrolled state without new navigation", async () => {
    Object.defineProperty(window, "scrollY", { configurable: true, writable: true, value: 0 });
    renderLanding();
    const header = screen.getByRole("banner");
    expect(header).toHaveClass("xb-land-nav");
    expect(header).not.toHaveClass("xb-land-nav--scrolled");
    Object.defineProperty(window, "scrollY", { configurable: true, writable: true, value: 120 });
    fireEvent.scroll(window);
    await waitFor(() => {
      expect(header).toHaveClass("xb-land-nav--scrolled");
    });
    expect(within(screen.getByRole("navigation", { name: "Public" })).getAllByRole("link")).toHaveLength(2);
    expect(screen.queryByText(/start a shipment/i)).toBeNull();
    Object.defineProperty(window, "scrollY", { configurable: true, writable: true, value: 0 });
    fireEvent.scroll(window);
    await waitFor(() => {
      expect(header).not.toHaveClass("xb-land-nav--scrolled");
    });
  });
});

describe("LandingPage motion", () => {
  it("marks the hero ready after first paint with staged blocks", async () => {
    renderLanding();
    const hero = document.querySelector(".xb-land-hero");
    expect(hero).not.toBeNull();
    await waitFor(() => {
      expect(hero).toHaveAttribute("data-ready", "true");
    });
    expect(hero!.querySelectorAll("[data-anim]")).toHaveLength(4);
  });

  it("reveals editorial columns where no observer exists", () => {
    renderLanding();
    expect(typeof IntersectionObserver).toBe("undefined");
    expect(document.querySelectorAll(".xb-land-col.xb-land-reveal.is-visible")).toHaveLength(3);
  });

  it("shows the workflow progression in product order", () => {
    renderLanding();
    expect(
      screen.getByRole("heading", { name: "How a shipment moves through Xportra." }),
    ).toBeInTheDocument();
    const steps = document.querySelector(".xb-land-flow__steps");
    expect(steps).not.toBeNull();
    const names = Array.from(steps!.querySelectorAll(".xb-land-flow__name")).map(
      (node) => node.textContent,
    );
    expect(names).toEqual(["Shipment", "Requirements", "Evidence", "Ready"]);
  });
});

describe("LandingPage sections", () => {
  it("shows the information strip and three text columns", () => {
    renderLanding();
    for (const label of ["Built for the paperwork", "Nothing is assumed", "One place per shipment"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { name: "Three things, per shipment." })).toBeInTheDocument();
    for (const step of ["Start with what you know", "A plain-English checklist", "Upload once, track always"]) {
      expect(screen.getByRole("heading", { name: step })).toBeInTheDocument();
    }
  });

  it("keeps a minimal footer with landmarks", () => {
    renderLanding();
    expect(screen.getByText("© 2026 Xportra AI")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Footer" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeInTheDocument();
  });
});

describe("LandingPage separation", () => {
  it("never leaks workspace navigation, signed in or not", () => {
    for (const signedIn of [false, true]) {
      renderLanding(signedIn);
      for (const name of [
        "Dashboard",
        "Your shipments",
        "View Shipments",
        "Documents",
        "Requirements",
        "Evidence",
        "Assessment",
      ]) {
        expect(screen.queryByRole("link", { name }), String(signedIn)).toBeNull();
      }
      expect(screen.queryByRole("complementary", { name: "Application" })).toBeNull();
      cleanup();
    }
  });
});

describe("LandingPage scope pins", () => {
  it("claims nothing unsupported and shows no fake product", () => {
    renderLanding();
    const main = within(screen.getByRole("main"));
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\d+\s*(customers|clients|countries|%|percent|trusted by)/i);
    expect(text).not.toMatch(/testimonial|leading platform|only .* platform|approved by|partner logo|money-back|risk-free|100%/i);
    expect(main.queryByRole("img")).toBeNull();
    expect(text).not.toMatch(/RAG|embedding|vector search|state machine|model names?|chatbot|analytics dashboard/i);
    expect(text).not.toMatch(/replaces .* (legal|professionals)|legal (certainty|guarantee)/i);
  });
});
