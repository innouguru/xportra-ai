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
  processingStateLabel,
  processingStateNote,
} from "../../lib/evidence";
import { isTerminalState } from "../../lib/workflow";
import type { EvidenceRecord, EvidenceUploadResult } from "../../types/api";
import {
  findFindingForRequirement,
  missingLines,
  previewKind,
  unverifiedVerdict,
  verdictForAssessment,
  type VerificationVerdict,
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
}

interface VerdictView {
  evidenceId: string;
  verdict: VerificationVerdict;
  missing: string[];
  fromRound: boolean;
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
  const [suppliedDetails, setSuppliedDetails] = useState<Record<string, EvidenceRecord | null>>({});
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<VerdictView | null>(null);
  const [preview, setPreview] = useState<PreviewView | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  const matchedReport = report && record && report.case_id === record.case_id ? report : null;
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
    setFileError(file ? describeUnsupportedFile(file) : null);
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
    setError(null);
    setNotice(null);
    setPending("upload");
    try {
      const result = await uploadEvidenceFile(auth, {
        file: selectedFile,
        requirement_ids: [requirement.id],
        workflow: record,
      });
      setUploads((current) => [result, ...current]);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      const name = result.original_filename ?? result.document_title ?? "Document";
      setNotice(
        result.processing_status === "ready"
          ? `“${name}” is ready as evidence. Ready never means satisfied — verify it below.`
          : result.processing_status === "failed"
            ? `“${name}” was received but processing failed, so it cannot be used as evidence.`
            : `“${name}” was received and is still processing.`,
      );
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const verify = async (evidenceId: string, alreadySupplied: boolean) => {
    if (closed || busy) {
      return;
    }
    setError(null);
    setNotice(null);
    setPending(`verify-${evidenceId}`);
    try {
      if (!alreadySupplied) {
        const response = await supplyEvidence(auth, record, evidenceId, requirement.id);
        setRecord(response.workflow);
      }
      const finding = findFindingForRequirement(matchedReport, requirement.id);
      if (finding) {
        setVerdict({
          evidenceId,
          verdict: verdictForAssessment(finding.assessment),
          missing: missingLines(finding),
          fromRound: true,
        });
      } else {
        setVerdict({ evidenceId, verdict: unverifiedVerdict(), missing: [], fromRound: false });
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
        aria-label={`Requirement: ${requirement.title}`}
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
        <p className="xb-doc-drawer__eyebrow">Requirement</p>
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
              </p>
            ) : null}
          </section>
        )}

        {unsuppliedUploads.length > 0 ? (
          <section aria-label="Uploaded, not yet supplied">
            <h3 className="xb-ws-section-title">Uploaded — link it to this requirement</h3>
            <ul className="xb-ws-missing">
              {unsuppliedUploads.map((item) => (
                <li key={item.evidence_id}>
                  {item.original_filename ?? item.document_title ?? shortId(item.evidence_id)}{" "}
                  <span className="xb-ws-muted">
                    ({processingStateLabel(item.processing_status)} —{" "}
                    {processingStateNote(item.processing_status)})
                  </span>
                  {item.processing_status === "ready" ? (
                    <DocActions
                      evidenceId={item.evidence_id}
                      mime={item.mime_type}
                      closed={closed}
                      busy={busy}
                      pending={pending}
                      onVerify={() => verify(item.evidence_id, false)}
                      onOpen={() => openDocument(item.evidence_id)}
                      onPreview={() => showPreview(item.evidence_id, item.mime_type)}
                    />
                  ) : null}
                </li>
              ))}
            </ul>
            <p className="xb-doc-drawer__body">
              Verifying links the document below and reads the recorded finding for this
              requirement.
            </p>
          </section>
        ) : null}

        <section aria-label="Documents for this requirement">
          <h3 className="xb-ws-section-title">Documents</h3>
          {linkedUploads.length === 0 && suppliedOnly.length === 0 ? (
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
                <DocActions
                  evidenceId={item.evidence_id}
                  mime={item.mime_type}
                  closed={closed}
                  busy={busy}
                  pending={pending}
                  onVerify={() => verify(item.evidence_id, true)}
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
                  <DocActions
                    evidenceId={id}
                    mime={detail?.mime_type ?? null}
                    closed={closed}
                    busy={busy}
                    pending={pending}
                    onVerify={() => verify(id, true)}
                    onOpen={() => openDocument(id)}
                    onPreview={() => showPreview(id, detail?.mime_type ?? null)}
                  />
                </li>
              );
            })}
          </ul>
        </section>

        {verdict ? (
          <section aria-label="Verification result" aria-live="polite">
            <h3 className="xb-ws-section-title">Result</h3>
            <p>
              <StatusIndicator tone={verdict.verdict.tone} label={verdict.verdict.label} />
            </p>
            <p className="xb-doc-drawer__body">{verdict.verdict.explanation}</p>
            {verdict.missing.length > 0 ? (
              <ul className="xb-ws-missing" aria-label="Still missing">
                {verdict.missing.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : null}
            {verdict.fromRound ? (
              <p className="xb-doc-drawer__body">From the latest recorded analysis round.</p>
            ) : (
              <p className="xb-doc-drawer__body">
                <Link to="/workspace/analysis">Open analysis</Link> to record a finding for this
                requirement.
              </p>
            )}
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
        {pending && pending !== "upload" && !pending.startsWith("verify-") ? (
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
  onVerify,
  onOpen,
  onPreview,
}: {
  evidenceId: string;
  mime: string | null;
  closed: boolean;
  busy: boolean;
  pending: string | null;
  onVerify: () => void;
  onOpen: () => void;
  onPreview: () => void;
}) {
  const verifying = pending === `verify-${evidenceId}`;
  const opening = pending === `open-${evidenceId}`;
  const previewing = pending === `preview-${evidenceId}`;
  return (
    <span className="xb-doc-drawer__actions">
      {!closed ? (
        <button type="button" className="xb-ws-link" disabled={busy} onClick={onVerify}>
          {verifying ? "Linking document…" : "Verify document"}
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
