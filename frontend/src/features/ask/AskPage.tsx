import React, { useState } from "react";
import { Link } from "react-router-dom";
import "./ask.css";

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/rag/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ information_need: question, mode: "hybrid" }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const msg = body.error || `Request failed (${res.status})`;
        setError(msg);
        setResult({ status: "error" });
      } else {
        const data = await res.json();
        setResult(data);
      }
    } catch (exc: any) {
      setError(exc.message || "Network error");
      setResult({ status: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="xb-ask">
      <header className="xb-ask-header">
        <Link to="/" className="xb-land-wordmark" aria-label="Xportra home">
          <span className="brand-glyph" aria-hidden="true">X</span>
          <span>
            Xportra<span className="xb-land-wordmark__dot" aria-hidden="true">.</span>
          </span>
        </Link>
      </header>
      <main id="main" className="xb-ask-main">
        <h1>Ask Xportra</h1>
        <form onSubmit={handleSubmit} className="xb-ask-form">
          <label htmlFor="xb-ask-input" className="xb-ask-label">
            Your regulatory question
          </label>
          <textarea
            id="xb-ask-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about requirements, evidence, or compliance for this shipment..."
            rows={4}
            maxLength={4000}
          />
          <button type="submit" className="primary-button" disabled={loading || !question.trim()}>
            {loading ? "Asking..." : "Ask"}
          </button>
        </form>
        {result && (
          <section className="xb-ask-result" aria-live="polite">
            {result.status === "valid" && (
              <>
                <h2>Answer</h2>
                <p className="xb-ask-answer">{result.answer_text}</p>
                {result.is_empty && <p className="xb-ask-empty">No substantive answer produced.</p>}
                {result.citations && result.citations.length > 0 && (
                  <>
                    <h3>Citations</h3>
                    <ul className="xb-ask-citations">
                      {result.citations.map((c: any, idx: number) => (
                        <li key={idx}>
                          <strong>[{c.label}]</strong> — Source: {c.evidence?.source_id || "unknown"}
                          {c.evidence?.document_version ? ` (v${c.evidence.document_version})` : ""}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
            {result.status === "invalid_citations" && (
              <>
                <h2>Answer</h2>
                <p className="xb-ask-answer">{result.answer_text}</p>
                <p className="xb-ask-empty">Some citations could not be validated — please review carefully.</p>
                {result.invalid_references && result.invalid_references.length > 0 && (
                  <p className="xb-ask-empty">Invalid references: {result.invalid_references.join(", ")}</p>
                )}
              </>
            )}
            {result.status === "empty" && (
              <p className="xb-ask-empty">No regulatory evidence found — please refine your question.</p>
            )}
            {result.status === "insufficient_evidence" && (
              <p className="xb-ask-empty">No regulatory evidence found — please refine your question.</p>
            )}
            {result.status === "error" && (
              <p className="xb-ask-error">An error occurred while processing your request.</p>
            )}
            {error && <p className="xb-ask-error">Error: {error}</p>}
          </section>
        )}
      </main>
    </div>
  );
}
