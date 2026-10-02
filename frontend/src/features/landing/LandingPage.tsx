import { Link } from "react-router-dom";
import type { CSSProperties, ReactNode } from "react";
import "./landing.css";
import { useHeroReady, useReveal, useScrolled } from "./landingMotion";

/**
 * Public landing page (approved redesign reference
 * `docs/design/xportra-ui-redesign.*`).
 *
 * Dedicated public chrome: no authenticated shell,
 * no workspace navigation, no session dependence —
 * the same page renders whether or not the visitor
 * is signed in. Navigation offers only Sign In (the
 * real sign-in route) and Get Started (the real
 * start route); there is no public "Start a
 * Shipment" CTA. The hero is one natural sentence
 * that wraps on its own — never manually broken.
 * Copy claims nothing beyond the implemented
 * product: no customers, statistics,
 * testimonials, or guarantees.
 *
 * Calm motion only: a sticky header with a quiet
 * scrolled state, a one-shot hero entrance, a
 * viewport reveal for the editorial columns, and
 * a slow editorial workflow diagram (Shipment →
 * Requirements → Evidence → Ready) that mirrors
 * the real product concept. Every animated
 * element is fully legible without animation,
 * and all decorative motion stops under
 * `prefers-reduced-motion` (see `landing.css`).
 */

const FLOW_STEPS = [
  {
    name: "Shipment",
    text: "What you’re exporting and where it’s going.",
  },
  {
    name: "Requirements",
    text: "What applies to this shipment, in plain English.",
  },
  {
    name: "Evidence",
    text: "Documents attached to the requirement they support.",
  },
  {
    name: "Ready",
    text: "A read-only record of what was checked.",
  },
] as const;

const DETAIL_COLS = [
  {
    num: "Product & destination",
    title: "Start with what you know",
    body: "Describe what you’re exporting and where it’s going. Xportra asks for more only when a specific requirement depends on it.",
  },
  {
    num: "Requirements",
    title: "A plain-English checklist",
    body: "Each requirement explains why it applies to your shipment and what evidence will satisfy it — no compliance jargon.",
  },
  {
    num: "Evidence",
    title: "Upload once, track always",
    body: "Attach the document for a requirement and see what it satisfies, what it’s missing, and what to do next.",
  },
] as const;

function RevealCol({ index, children }: { index: number; children: ReactNode }) {
  const { ref, visible } = useReveal<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={visible ? "xb-land-col xb-land-reveal is-visible" : "xb-land-col xb-land-reveal"}
      style={{ "--reveal-index": index } as CSSProperties}
    >
      {children}
    </div>
  );
}

export function LandingPage() {
  const scrolled = useScrolled();
  const heroReady = useHeroReady();
  return (
    <div className="xb-land">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className={scrolled ? "xb-land-nav xb-land-nav--scrolled" : "xb-land-nav"}>
        {/* Brand lockup: the glyph slot is the established
          * `components/BrandMark.tsx` mark (same class and
          * content), kept decorative here so the link keeps
          * its "Xportra home" name and "/" target. */}
        <Link to="/" className="xb-land-wordmark" aria-label="Xportra home">
          <span className="brand-glyph" aria-hidden="true">
            X
          </span>
          <span>
            Xportra<span className="xb-land-wordmark__dot" aria-hidden="true">.</span>
          </span>
        </Link>
        <nav className="xb-land-nav__links" aria-label="Public">
          <Link className="xb-land-signin" to="/session">
            Sign In
          </Link>
          <Link className="primary-button" to="/start">
            Get Started
          </Link>
        </nav>
      </header>
      <main id="main" className="xb-land-main">
        <section
          className="xb-land-hero"
          aria-labelledby="xb-land-title"
          data-ready={heroReady ? "true" : "false"}
        >
          <h1 className="xb-land-display" id="xb-land-title" data-anim="display">
            Xportra tells you exactly what your shipment needs to clear export compliance, and why.
          </h1>
          <p className="xb-land-lede" data-anim="lede">
            Tell us what you&rsquo;re shipping and where it&rsquo;s going. Xportra works out the
            certificates, permits, and documentation required, tracks what you&rsquo;ve provided,
            and flags what&rsquo;s still missing.
          </p>
          <div className="xb-land-ctas" data-anim="ctas">
            <Link className="primary-button xb-land-cta-primary" to="/start">
              Get Started
            </Link>
            <Link className="secondary-button" to="/session">
              Sign In
            </Link>
          </div>
          <div className="xb-land-strip" data-anim="strip">
            <div className="xb-land-strip__item">
              <p className="xb-land-strip__label">Built for the paperwork</p>
              <p className="xb-land-strip__text">
                Phytosanitary certificates, export licenses, certificates of origin — mapped to
                the product and destination you give us.
              </p>
            </div>
            <div className="xb-land-strip__item">
              <p className="xb-land-strip__label">Nothing is assumed</p>
              <p className="xb-land-strip__text">
                When a requirement can&rsquo;t be determined yet, Xportra says so — it
                doesn&rsquo;t guess and doesn&rsquo;t mark it satisfied.
              </p>
            </div>
            <div className="xb-land-strip__item">
              <p className="xb-land-strip__label">One place per shipment</p>
              <p className="xb-land-strip__text">
                Requirements, evidence, and verification live together, in the order
                you&rsquo;ll actually need them.
              </p>
            </div>
          </div>
        </section>

        <section className="xb-land-section" aria-labelledby="xb-land-three-title">
          <h2 id="xb-land-three-title">Three things, per shipment.</h2>
          <div className="xb-land-cols">
            {DETAIL_COLS.map((col, index) => (
              <RevealCol key={col.title} index={index}>
                <p className="xb-land-col__num">{col.num}</p>
                <h3>{col.title}</h3>
                <p>{col.body}</p>
              </RevealCol>
            ))}
          </div>
        </section>

        <section className="xb-land-section xb-land-flow" aria-labelledby="xb-land-flow-title">
          <h2 id="xb-land-flow-title">How a shipment moves through Xportra.</h2>
          <ol className="xb-land-flow__steps">
            {FLOW_STEPS.map((step, index) => (
              <li
                key={step.name}
                className="xb-land-flow__step"
                style={{ "--step-index": index } as CSSProperties}
              >
                <span className="xb-land-flow__dot" aria-hidden="true" />
                <p className="xb-land-flow__name">{step.name}</p>
                <p className="xb-land-flow__text">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>
      <footer className="xb-land-footer">
        <span>© 2026 Xportra AI</span>
        <nav aria-label="Footer">
          <a href="#">Privacy</a>
          <a href="#">Terms</a>
          <a href="#">Contact</a>
        </nav>
      </footer>
    </div>
  );
}
