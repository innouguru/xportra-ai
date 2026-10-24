import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchEvidence,
  fetchEvidenceDownload,
  uploadEvidenceFile,
} from "../../api/evidence";
import { supplyEvidence } from "../../api/workflows";
import { userFacingErrorMessage } from "../../api/client";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { useAnalysis } from "../../app/AnalysisContext";
import { useEscapeKey, useFocusRestore } from "../../primitives/a11y";
import { ErrorState, LoadingState } from "../../primitives/feedback";
import { StatusIndicator } from "../../primitives/status";
import type { StatusTone } from "../../primitives/status";
import {
  MAX_UPLOAD_BYTES,
  SUPPORTED_UPLOAD_TEXT,
  UPLOAD_ACCEPT,
  describeUnsupportedFile,
  evidenceStatusLabel,
  processingStateLabel,
  processingStateNote,
} from "../../lib/evidence";
import { isTerminalState } from "../../lib/workflow";
import type { EvidenceRecord, EvidenceUploadResult } from "../../types/api";
import {
  findFindingForRequirement,
  missingLines,
  previewKind,
  verdictForAssessment,
} from "../verification/verification";

/**
 * Phase 10.8F document verification drawer.
 *
 * Requirement-scoped verification using only
 * existing boundaries: real upload
 * (`POST /compliance-evidence/uploads` with
 * backend-owned constraints), real linking
 * (`supply-evidence`, refreshing the
 * authoritative workflow record), verdicts
 * from recorded analysis findings (never
 * frontend judgment), and authorized preview
 * grants used immediately. Analysis itself
 * stays explicit on its own route — the
 * drawer links there instead of synthesizing
 * case views or re-running anything.
 */

export interface DrawerRequirement {
  id: string;
  title: string;
  statusLabel: string;
  tone: StatusTone;
  explanation: string | null;
  sources: Array<{ label: string; reference: string | null }>;
}

interface PreviewView {
  evidenceId: string;
  url: string;
  kind: "pdf" | "image";
}

function shortId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

export function DocumentDrawer({
  requirement,
  onClose,
}: {
  requirement: DrawerRequirement;
  onClose: () => void;
}) {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const { report } = useAnalysis();
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  useEscapeKey(onClose);
  useFocusRestore();

  const [uploads, setUploads] = useState<EvidenceUploadResult[]>([]);
  const [retryFiles, setRetryFiles] = useState<Record<string, File>>({});
  const [suppliedDetails, setSuppliedDetails] = useState<Record<string, EvidenceRecord | null>>({});
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showAnalysisAction, setShowAnalysisAction] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewView | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  const latestReportId = record?.rounds[record.rounds.length - 1]?.report_id ?? null;
  const matchedReport =
    report && record && report.case_id === record.case_id && report.report_id === latestReportId
      ? report
      : null;
  const supplied = new Set(record?.supplied_evidence_ids ?? []);
  const closed = record ? isTerminalState(record.state) : false;
  const busy = pending !== null;

  // Titles for shipment-supplied documents (same pattern as the evidence workspace).
  useEffect(() => {
    if (!record) {
      return;
    }
    let cancelled = false;
    const missing = record.supplied_evidence_ids.filter((id) => !(id in suppliedDetails));
    if (missing.length === 0) {
      return;
    }
    void (async () => {
      const entries = await Promise.all(
        missing.map(async (id): Promise<[string, EvidenceRecord | null]> => {
          try {
            return [id, await fetchEvidence(auth, id)];
          } catch {
            return [id, null];
          }
        }),
      );
      if (!cancelled) {
        setSuppliedDetails((current) => {
          const next = { ...current };
          for (const [id, row] of entries) {
            next[id] = row;
          }
          return next;
        });
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record?.supplied_evidence_ids.join(",")]);

  const trapTab = (event: React.KeyboardEvent) => {
    if (event.key !== "Tab") {
      return;
    }
    const items = Array.from(
      panelRef.current?.querySelectorAll<HTMLElement>(
        "a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])",
      ) ?? [],
    );
    if (items.length === 0) {
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!record) {
    return (
      <>
        <button type="button" className="xb-doc-scrim" aria-label="Dismiss document panel" onClick={onClose} />
        <aside
          ref={panelRef}
          className="xb-doc-drawer"
          role="dialog"
          aria-modal="true"
          aria-label="Documents"
          onKeyDown={trapTab}
        >
          <p>No active shipment. Close this panel and open a shipment first.</p>
          <button type="button" className="secondary-button" onClick={onClose}>
            Close
          </button>
        </aside>
      </>
    );
  }

  const chooseFile = (file: File | null) => {
    setSelectedFile(file);
    setNotice(null);
    setShowAnalysisAction(false);
    setError(null);
    setFileError(file ? describeUnsupportedFile(file) : null);
  };

  const sendFile = async (file: File): Promise<boolean> => {
    setError(null);
    setNotice(null);
    setShowAnalysisAction(false);
    setPending("upload");
    try {
      const result = await uploadEvidenceFile(auth, {
        file,
        requirement_ids: [requirement.id],
        workflow: record,
      });
      setUploads((current) => [result, ...current.filter((item) => item.evidence_id !== result.evidence_id)]);
      const name = result.original_filename ?? result.document_title ?? "Document";
      if (result.processing_status !== "ready") {
        setRetryFiles((current) => ({ ...current, [result.evidence_id]: file }));
      } else {
        setRetryFiles((current) => {
          const next = { ...current };
          delete next[result.evidence_id];
          return next;
        });
      }
      setNotice(
        result.processing_status === "ready"
          ? `“${name}” is ready to use. It has not been supplied to the shipment or assessed yet.`
          : result.processing_status === "failed"
            ? `“${name}” was received, but processing failed. It was not supplied; retry processing below or choose another file.`
            : `“${name}” was received and is still processing.`,
      );
      return true;
    } catch (err) {
      setError(err);
      return false;
    } finally {
      setPending(null);
    }
  };

  const upload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (closed || busy || !selectedFile) {
      return;
    }
    const blocker = describeUnsupportedFile(selectedFile);
    if (blocker) {
      setFileError(blocker);
      return;
    }
    setFileError(null);
    const sent = await sendFile(selectedFile);
    if (sent) {
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const retryProcessing = async (evidenceId: string) => {
    const file = retryFiles[evidenceId];
    if (closed || busy || !file) {
      return;
    }
    await sendFile(file);
  };

  const supply = async (evidenceId: string) => {
    if (closed || busy) {
      return;
    }
    setError(null);
    setNotice(null);
    setPending(`supply-${evidenceId}`);
    try {
      const response = await supplyEvidence(auth, record, evidenceId, requirement.id);
      setRecord(response.workflow);
      setNotice("Document supplied to this shipment. This does not update its assessment. Run analysis explicitly when you are ready.");
      setShowAnalysisAction(true);
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const latestFinding = findFindingForRequirement(matchedReport, requirement.id);

  const refreshProcessing = async (evidenceId: string) => {
    if (busy) {
      return;
    }
    setError(null);
    setPending(`refresh-${evidenceId}`);
    try {
      const latest = await fetchEvidence(auth, evidenceId);
      setSuppliedDetails((current) => ({ ...current, [evidenceId]: latest }));
      setUploads((current) =>
        current.map((item) =>
          item.evidence_id === evidenceId
            ? { ...item, status: latest.status, processing_status: latest.processing_status ?? null }
            : item,
        ),
      );
      if (latest.processing_status === "ready") {
        setRetryFiles((current) => {
          const next = { ...current };
          delete next[evidenceId];
          return next;
        });
      }
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const openDocument = async (evidenceId: string) => {
    if (busy) {
      return;
    }
    setError(null);
    setPending(`open-${evidenceId}`);
    try {
      const grant = await fetchEvidenceDownload(auth, evidenceId);
      window.open(grant.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const showPreview = async (evidenceId: string, mime: string | null) => {
    if (busy) {
      return;
    }
    setError(null);
    setPending(`preview-${evidenceId}`);
    try {
      const grant = await fetchEvidenceDownload(auth, evidenceId);
      const kind = previewKind(mime);
      if (kind === "unsupported") {
        setNotice("Preview isn’t available for this file type — use Open document instead.");
        return;
      }
      setPreview({ evidenceId, url: grant.download_url, kind });
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const unsuppliedUploads = uploads.filter((item) => !supplied.has(item.evidence_id));
  const linkedUploads = uploads.filter((item) => supplied.has(item.evidence_id));
  const suppliedOnly = record.supplied_evidence_ids.filter(
    (id) => !uploads.some((item) => item.evidence_id === id),
  );

  return (
    <>
      <button type="button" className="xb-doc-scrim" aria-label="Dismiss document panel" onClick={onClose} />
      <aside
        ref={panelRef}
        className="xb-doc-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`Record details: ${requirement.title}`}
        onKeyDown={trapTab}
      >
        <button
          ref={closeRef}
          type="button"
          className="xb-doc-drawer__back"
          onClick={onClose}
        >
          <span aria-hidden="true">← </span>Back to shipment
        </button>
        <p className="xb-doc-drawer__eyebrow">Shipment record</p>
        <h2 className="xb-doc-drawer__title">{requirement.title}</h2>
        <p>
          <StatusIndicator tone={requirement.tone} label={requirement.statusLabel} />
        </p>
        {requirement.explanation ? (
          <div>
            <p className="xb-doc-drawer__body">
              <strong>What this requirement needs.</strong>
            </p>
            <p className="xb-doc-drawer__body">{requirement.explanation}</p>
          </div>
        ) : null}
        {requirement.sources.length > 0 ? (
          <details className="xb-doc-drawer__body">
            <summary>Source information ({requirement.sources.length})</summary>
            <ul>
              {requirement.sources.map((source, index) => (
                <li key={`${source.label}-${source.reference ?? index}`}>
                  {source.label}{source.reference ? `: ${source.reference}` : ""}
                </li>
              ))}
            </ul>
            <p>These are references returned with the latest analysis; they are not a complete export checklist.</p>
          </details>
        ) : null}

        {closed ? (
          <p className="xb-ws-readonly">
            <strong>Historical record — read-only.</strong> Documents stay readable; nothing here
            can change them.
          </p>
        ) : (
          <section aria-label="Upload a document">
            <h3 className="xb-ws-section-title">Upload a document</h3>
            <p className="xb-doc-drawer__body">
              {SUPPORTED_UPLOAD_TEXT} (max {Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB). The
              backend checks every file — unsupported files are rejected, never stored.
            </p>
            <form onSubmit={upload}>
              <div className="xb-field">
                <label className="xb-field__label" htmlFor="xb-doc-file">
                  Choose a file
                </label>
                <input
                  ref={fileInputRef}
                  id="xb-doc-file"
                  className="xb-input"
                  type="file"
                  accept={UPLOAD_ACCEPT}
                  disabled={busy}
                  onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
                />
                {fileError ? <p className="xb-field__error">{fileError}</p> : null}
              </div>
              <div className="xb-doc-drawer__actions">
                <button type="submit" className="secondary-button" disabled={busy || !selectedFile}>
                  {pending === "upload" ? "Uploading…" : "Upload document"}
                </button>
              </div>
            </form>
            {notice ? (
              <p className="xb-doc-drawer__body" role="status">
                {notice}
                {showAnalysisAction ? <>{" "}<Link to="/workspace/analysis">Open analysis</Link></> : null}
              </p>
            ) : null}
          </section>
        )}

        {unsuppliedUploads.length > 0 ? (
          <section aria-label="Uploaded, not yet supplied">
            <h3 className="xb-ws-section-title">Uploaded, not yet supplied</h3>
            <ul className="xb-ws-missing">
              {unsuppliedUploads.map((item) => (
                <li key={item.evidence_id}>
                  <p><strong>{item.original_filename ?? item.document_title ?? shortId(item.evidence_id)}</strong></p>
                  <dl className="field-grid">
                    <div>
                      <dt>File processing</dt>
                      <dd>
                        <StatusIndicator
                          tone={
                            item.processing_status === "ready"
                              ? "success"
                              : item.processing_status === "failed"
                                ? "danger"
                                : item.processing_status === "processing"
                                  ? "info"
                                  : "neutral"
                          }
                          label={processingStateLabel(item.processing_status)}
                        />{" "}
                        <span className="xb-ws-muted">{processingStateNote(item.processing_status)}</span>
                      </dd>
                    </div>
                    <div><dt>Evidence review</dt><dd>{evidenceStatusLabel(item.status)}</dd></div>
                    <div><dt>Shipment use</dt><dd>Not supplied</dd></div>
                  </dl>
                  {item.duplicate ? <p className="xb-ws-muted">This file matches an existing evidence record.</p> : null}
                  {item.processing_status === "failed" && retryFiles[item.evidence_id] ? (
                    <button type="button" className="secondary-button" disabled={busy || closed} onClick={() => void retryProcessing(item.evidence_id)}>
                      {pending === "upload" ? "Retrying processing…" : "Retry processing"}
                    </button>
                  ) : null}
                  {item.processing_status === "uploaded" || item.processing_status === "processing" ? (
                    <button type="button" className="secondary-button" disabled={busy} onClick={() => void refreshProcessing(item.evidence_id)}>
                      {pending === `refresh-${item.evidence_id}` ? "Checking…" : "Refresh processing status"}
                    </button>
                  ) : null}
                  <DocActions
                    evidenceId={item.evidence_id}
                    mime={item.mime_type}
                    closed={closed}
                    busy={busy}
                    pending={pending}
                    onSupply={item.processing_status === "ready" ? () => void supply(item.evidence_id) : undefined}
                    onOpen={() => openDocument(item.evidence_id)}
                    onPreview={() => showPreview(item.evidence_id, item.mime_type)}
                  />
                </li>
              ))}
            </ul>
            <p className="xb-doc-drawer__body">
              A ready file can be supplied to this requirement. Supplying it does not run analysis
              or change an existing assessment.
            </p>
          </section>
        ) : null}

        <section aria-label="Documents for this requirement">
          <h3 className="xb-ws-section-title">Documents</h3>
          {linkedUploads.length === 0 && suppliedOnly.length === 0 && unsuppliedUploads.length === 0 ? (
            <p className="xb-doc-drawer__body">
              No document here yet. Upload one above, or supply an existing shipment document
              from the documents workspace.
            </p>
          ) : null}
          <ul className="xb-ws-missing">
            {linkedUploads.map((item) => (
              <li key={item.evidence_id}>
                {item.original_filename ?? item.document_title ?? shortId(item.evidence_id)}{" "}
                <span className="xb-ws-muted">(supplied for this requirement)</span>
                <dl className="field-grid">
                  <div><dt>File processing</dt><dd>{processingStateLabel(item.processing_status)}</dd></div>
                  <div><dt>Evidence review</dt><dd>{evidenceStatusLabel(item.status)}</dd></div>
                </dl>
                <DocActions
                  evidenceId={item.evidence_id}
                  mime={item.mime_type}
                  closed={closed}
                  busy={busy}
                  pending={pending}
                  onOpen={() => openDocument(item.evidence_id)}
                  onPreview={() => showPreview(item.evidence_id, item.mime_type)}
                />
              </li>
            ))}
            {suppliedOnly.map((id) => {
              const detail = suppliedDetails[id];
              return (
                <li key={id}>
                  {detail?.document_title ?? shortId(id)}{" "}
                  <span className="xb-ws-muted">(supplied to this shipment)</span>
                  {detail ? (
                    <dl className="field-grid">
                      <div><dt>File processing</dt><dd>{processingStateLabel(detail.processing_status)}</dd></div>
                      <div><dt>Evidence review</dt><dd>{evidenceStatusLabel(detail.status)}</dd></div>
                    </dl>
                  ) : null}
                  <DocActions
                    evidenceId={id}
                    mime={detail?.mime_type ?? null}
                    closed={closed}
                    busy={busy}
                    pending={pending}
                    onOpen={() => openDocument(id)}
                    onPreview={() => showPreview(id, detail?.mime_type ?? null)}
                  />
                </li>
              );
            })}
          </ul>
        </section>

        {latestFinding ? (
          <section aria-label="Verification result" aria-live="polite">
            <h3 className="xb-ws-section-title">Latest recorded assessment</h3>
            <p>
              <StatusIndicator
                tone={verdictForAssessment(latestFinding.assessment).tone}
                label={verdictForAssessment(latestFinding.assessment).label}
              />
            </p>
            <p className="xb-doc-drawer__body">
              {verdictForAssessment(latestFinding.assessment).explanation} This is a requirement-level
              result, not a verdict on one file. Newly supplied documents are only considered by a
              later analysis round.
            </p>
            {missingLines(latestFinding).length > 0 ? (
              <ul className="xb-ws-missing" aria-label="Still missing">
                {missingLines(latestFinding).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : null}
            <p className="xb-doc-drawer__body">From the latest recorded analysis round.</p>
            <Link to="/workspace/analysis">Open analysis</Link>
          </section>
        ) : null}

        {preview ? (
          <section aria-label="Document preview">
            <h3 className="xb-ws-section-title">Preview</h3>
            {preview.kind === "pdf" ? (
              <iframe title={`Preview of document ${shortId(preview.evidenceId)}`} src={preview.url} width="100%" height="420" />
            ) : (
              <img alt={`Preview of document ${shortId(preview.evidenceId)}`} src={preview.url} style={{ maxWidth: "100%" }} />
            )}
            <p className="xb-doc-drawer__body">
              <a href={preview.url} target="_blank" rel="noreferrer">
                Open in a new tab
              </a>
            </p>
          </section>
        ) : null}

        {error ? (
          <ErrorState title="Something went wrong." message={userFacingErrorMessage(error)} />
        ) : null}
        {pending && pending !== "upload" && !pending.startsWith("supply-") && !pending.startsWith("refresh-") ? (
          <LoadingState text="Working…" />
        ) : null}
      </aside>
    </>
  );
}

function DocActions({
  evidenceId,
  mime,
  closed,
  busy,
  pending,
  onSupply,
  onOpen,
  onPreview,
}: {
  evidenceId: string;
  mime: string | null;
  closed: boolean;
  busy: boolean;
  pending: string | null;
  onSupply?: () => void;
  onOpen: () => void;
  onPreview: () => void;
}) {
  const supplying = pending === `supply-${evidenceId}`;
  const opening = pending === `open-${evidenceId}`;
  const previewing = pending === `preview-${evidenceId}`;
  return (
    <span className="xb-doc-drawer__actions">
      {!closed && onSupply ? (
        <button type="button" className="xb-ws-link" disabled={busy} onClick={onSupply}>
          {supplying ? "Supplying…" : "Supply to requirement"}
        </button>
      ) : null}
      <button type="button" className="xb-ws-link" disabled={busy} onClick={onOpen}>
        {opening ? "Opening…" : "Open document"}
      </button>
      {previewKind(mime) !== "unsupported" ? (
        <button type="button" className="xb-ws-link" disabled={busy} onClick={onPreview}>
          {previewing ? "Loading preview…" : "Show preview"}
        </button>
      ) : null}
    </span>
  );
}
