import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchEvidence,
  fetchEvidenceDownload,
  uploadEvidenceFile,
} from "../../api/evidence";
import { supplyEvidence } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import {
  EmptyState,
  ErrorNotice,
  Field,
  Identifier,
  LoadingState,
  StatusBadge,
  TerminalNotice,
} from "../../components/StatusBits";
import {
  MAX_UPLOAD_BYTES,
  SUPPORTED_UPLOAD_TEXT,
  UPLOAD_ACCEPT,
  describeUnsupportedFile,
  formatFileSize,
  processingStateLabel,
  processingStateNote,
  processingStateTone,
} from "../../lib/evidence";
import { isTerminalState } from "../../lib/workflow";
import { AskXportraButton } from "../conversation/AskXportraButton";
import type {
  EvidenceRecord,
  EvidenceUploadResult,
} from "../../types/api";

/**
 * Screen 4 — Evidence workspace with real file upload.
 *
 * Uploads go to `POST /compliance-evidence/uploads`
 * (base64 JSON transport, exactly the backend contract);
 * the backend stays authoritative on type/size/content
 * validation, processing, and associations. The UI only
 * presents the lifecycle honestly:
 *
 *   Selected → Uploading → Processing → Ready | Failed
 *
 * Uploading or processing a document never implies
 * compliance, and a ready document never implies a
 * satisfied requirement. Supplying evidence to the
 * workflow and running analysis stay separate, explicit
 * steps. Downloads use the authorized backend endpoint
 * and signed URLs are used immediately, never stored.
 */
export function EvidencePage() {
  const auth = useAuth();
  const { record, setRecord } = useWorkflow();
  const [uploads, setUploads] = useState<EvidenceUploadResult[]>([]);
  const [suppliedDetails, setSuppliedDetails] = useState<
    Record<string, EvidenceRecord | null>
  >({});
  const [loadingSupplied, setLoadingSupplied] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const suppliedIds = record?.supplied_evidence_ids ?? [];
  const suppliedKey = suppliedIds.join(",");

  useEffect(() => {
    if (!record || suppliedIds.length === 0) {
      return;
    }
    let cancelled = false;
    const missing = suppliedIds.filter((id) => !(id in suppliedDetails));
    if (missing.length === 0) {
      return;
    }
    setLoadingSupplied(true);
    void (async () => {
      const entries = await Promise.all(
        missing.map(async (id): Promise<[string, EvidenceRecord | null]> => {
          try {
            const row = await fetchEvidence(auth, id);
            return [id, row];
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
        setLoadingSupplied(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suppliedKey]);

  if (!record) {
    return (
      <EmptyState
        title="No active shipment"
        body="Open a compliance case first."
        action={
          <Link className="primary-button" to="/">
            Start a new shipment
          </Link>
        }
      />
    );
  }

  const closed = isTerminalState(record.state);
  const busy = uploading || pending !== null;
  const locked = busy || closed;
  const hasAnalysisRounds = record.rounds.length > 0;
  const supplied = new Set(record.supplied_evidence_ids);
  const uploadedById = new Map(uploads.map((item) => [item.evidence_id, item]));
  const unsuppliedUploads = uploads.filter((item) => !supplied.has(item.evidence_id));

  const chooseFile = (file: File | null) => {
    setSelectedFile(file);
    setUploadNotice(null);
    setFileError(file ? describeUnsupportedFile(file) : null);
  };

  const upload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (locked || uploading || !selectedFile) {
      return;
    }
    const blocker = describeUnsupportedFile(selectedFile);
    if (blocker) {
      setFileError(blocker);
      return;
    }
    setFileError(null);
    setError(null);
    setUploadNotice(null);
    setUploading(true);
    try {
      const result = await uploadEvidenceFile(auth, {
        file: selectedFile,
        workflow: record,
      });
      setUploads((current) => [result, ...current]);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setUploadNotice(
        result.processing_status === "ready"
          ? `“${result.original_filename ?? result.document_title ?? "Document"}” is ready as evidence. This does not mean any requirement is satisfied.`
          : result.processing_status === "failed"
            ? `“${result.original_filename ?? result.document_title ?? "Document"}” was received but processing failed, so it cannot be used as evidence.`
            : `“${result.original_filename ?? result.document_title ?? "Document"}” was received and is still processing.`,
      );
    } catch (err) {
      setError(err);
    } finally {
      setUploading(false);
    }
  };

  const supply = async (evidenceId: string) => {
    setError(null);
    setPending(`supply-${evidenceId}`);
    try {
      const response = await supplyEvidence(auth, record, evidenceId);
      setRecord(response.workflow);
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  const download = async (evidenceId: string) => {
    setError(null);
    setPending(`download-${evidenceId}`);
    try {
      const grant = await fetchEvidenceDownload(auth, evidenceId);
      window.open(grant.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  };

  return (
    <div>
      <header className="page-intro">
        <p className="page-kicker">Evidence workspace</p>
        <p className="lede">
          Upload the documents behind this shipment, see what Xportra is
          doing with each one, and supply evidence so analysis can consider
          it. Uploading a document never decides compliance — only a
          backend analysis round can weigh evidence.
        </p>
      </header>

      <section aria-label="Supplied evidence">
        <h2>Supplied to this workflow ({record.supplied_evidence_ids.length})</h2>
        {record.supplied_evidence_ids.length === 0 ? (
          <p className="muted">
            No evidence has been supplied to this workflow yet. Upload a
            document below, then supply it so analysis can consider it.
          </p>
        ) : (
          <ul className="reference-list">
            {record.supplied_evidence_ids.map((id) => {
              const uploaded = uploadedById.get(id);
              const fetched = suppliedDetails[id];
              const title =
                uploaded?.document_title ??
                uploaded?.original_filename ??
                fetched?.document_title ??
                null;
              const docType = uploaded?.document_type ?? fetched?.document_type ?? null;
              const reviewStatus = uploaded?.status ?? fetched?.status ?? null;
              const processing =
                uploaded?.processing_status ?? fetched?.processing_status ?? null;
              return (
                <li key={id}>
                  {title ? (
                    <p className="ledger-title">{title}</p>
                  ) : (
                    <p className="reference-id">
                      <Identifier value={id} />
                    </p>
                  )}
                  <dl className="field-grid">
                    {docType ? <Field label="Type">{docType}</Field> : null}
                    {reviewStatus ? (
                      <Field label="Evidence status">
                        <StatusBadge value={reviewStatus} tone="neutral" />
                      </Field>
                    ) : null}
                    {processing ? (
                      <Field label="Processing">
                        <StatusBadge
                          value={processingStateLabel(processing)}
                          tone={processingStateTone(processing)}
                        />{" "}
                        <span className="muted">{processingStateNote(processing)}</span>
                      </Field>
                    ) : null}
                    {title ? (
                      <Field label="Evidence ID">
                        <Identifier value={id} short={36} />
                      </Field>
                    ) : null}
                    <Field label="Document">
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={pending !== null}
                        onClick={() => void download(id)}
                      >
                        {pending === `download-${id}` ? "Preparing…" : "Download document"}
                      </button>
                    </Field>
                  </dl>
                </li>
              );
            })}
          </ul>
        )}
        {loadingSupplied ? <LoadingState text="Loading supplied evidence…" /> : null}
        {error ? <ErrorNotice error={error} /> : null}
      </section>

      <section aria-label="Needed evidence">
        <h2>Needed ({record.open_requirements.length})</h2>
        <p className="muted">
          Requirements flagged open on this workflow — information still
          needed, not non-compliance. Absence alone decides nothing.
        </p>
        {record.open_requirements.length === 0 ? (
          <p className="muted">No requirements are currently flagged open.</p>
        ) : (
          <ul className="reference-list">
            {record.open_requirements.map((id) => (
              <li key={id}>
                <p className="eyebrow">Information needed</p>
                <p className="reference-id">
                  <Identifier value={id} short={36} />
                </p>
              </li>
            ))}
          </ul>
        )}
        <div className="action-row">
          <Link className="secondary-button" to="../gaps">
            What information is missing
          </Link>
          <Link className="secondary-button" to="../additional-evidence">
            Supply requested evidence
          </Link>
        </div>
      </section>

      <section aria-label="Upload evidence">
        <h2>Upload evidence</h2>
        {closed ? (
          <TerminalNotice title="Upload is unavailable — this assessment has been finalized and can no longer be changed.">
            <p>
              The assessment package is final and the workflow is permanently
              closed. No new evidence can be uploaded and there is no way to
              reopen it. The stored package and its report stay readable.
            </p>
          </TerminalNotice>
        ) : (
          <>
            <p className="muted">
              Choose {SUPPORTED_UPLOAD_TEXT} (max 10 MB per file). Xportra
              checks the file, reads it, and indexes it as evidence — a
              ready document is available for analysis, not a satisfied
              requirement.
            </p>
            <form className="form" onSubmit={(event) => void upload(event)}>
              <div className="form-row">
                <label htmlFor="evidence-file">Choose a file to upload</label>
                <input
                  ref={fileInputRef}
                  id="evidence-file"
                  type="file"
                  accept={UPLOAD_ACCEPT}
                  disabled={locked}
                  aria-describedby="evidence-file-hint evidence-file-error"
                  onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
                />
                <p id="evidence-file-hint" className="form-hint">
                  Supported: {SUPPORTED_UPLOAD_TEXT}. Maximum{" "}
                  {formatFileSize(MAX_UPLOAD_BYTES)} per file.
                </p>
              </div>
              {selectedFile ? (
                <dl className="field-grid" aria-label="Selected file">
                  <Field label="File name">{selectedFile.name}</Field>
                  <Field label="File size">{formatFileSize(selectedFile.size)}</Field>
                </dl>
              ) : null}
              {fileError ? (
                <p id="evidence-file-error" className="form-error" role="alert">
                  {fileError}
                </p>
              ) : (
                <p id="evidence-file-error" className="form-hint">
                  {selectedFile ? "This file is ready to upload." : "No file selected yet."}
                </p>
              )}
              <div>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={locked || !selectedFile || fileError !== null}
                >
                  {uploading ? "Uploading…" : "Upload evidence"}
                </button>
              </div>
            </form>
            {uploading ? (
              <LoadingState text="Uploading — Xportra is receiving and processing the document…" />
            ) : null}
            {uploadNotice && !uploading ? (
              <p className="form-hint" role="status" aria-live="polite">
                {uploadNotice}
              </p>
            ) : null}
          </>
        )}
      </section>

      <section aria-label="Evidence attention">
        <h2>Attention</h2>
        {closed ? (
          <p className="muted">
            This workflow is finalized — the evidence record is read-only.
          </p>
        ) : (
          <ul className="attention-list">
            {record.state === "additional_evidence_requested" ? (
              <li className="attention-item attention-item--attention">
                <div>
                  <p className="attention-item__title">Additional evidence was requested</p>
                  <p className="muted">
                    Review what is open, upload a document above, and supply it.
                  </p>
                </div>
                <Link className="secondary-button" to="../additional-evidence">
                  Open request
                </Link>
              </li>
            ) : null}
            {hasAnalysisRounds && uploads.length > 0 ? (
              <li className="attention-item attention-item--attention">
                <div>
                  <p className="attention-item__title">
                    New evidence is available — analysis may need to be rerun
                  </p>
                  <p className="muted">
                    Recent uploads change nothing already assessed. Run analysis
                    again when you are ready; nothing runs automatically.
                  </p>
                </div>
                <Link className="secondary-button" to="../analysis">
                  Run analysis again
                </Link>
              </li>
            ) : null}
            {unsuppliedUploads.length > 0 ? (
              <li className="attention-item attention-item--attention">
                <div>
                  <p className="attention-item__title">
                    {unsuppliedUploads.length} uploaded, not yet supplied
                  </p>
                  <p className="muted">
                    These documents exist but analysis cannot consider them until supplied.
                  </p>
                </div>
                <a className="secondary-button" href="#uploaded-evidence">
                  Review list
                </a>
              </li>
            ) : null}
            {record.state !== "additional_evidence_requested" &&
            unsuppliedUploads.length === 0 &&
            !(hasAnalysisRounds && uploads.length > 0) ? (
              <li className="attention-item attention-item--neutral">
                <div>
                  <p className="attention-item__title">
                    {uploads.length === 0 ? "No uploads yet" : "Nothing needs attention"}
                  </p>
                  <p className="muted">
                    {uploads.length === 0
                      ? "Upload a document above to get started."
                      : "Every upload this session has been supplied."}
                  </p>
                </div>
              </li>
            ) : null}
          </ul>
        )}
      </section>

      <section aria-label="Uploaded evidence" id="uploaded-evidence">
        <h2>Uploaded this session ({uploads.length})</h2>
        {uploads.length === 0 ? (
          <p className="muted">No documents uploaded yet in this session.</p>
        ) : (
          <ul className="reference-list">
            {uploads.map((item) => (
              <li key={item.evidence_id}>
                <p className="ledger-title">
                  {item.document_title ?? item.original_filename ?? "Uploaded document"}
                </p>
                <dl className="field-grid">
                  {item.document_type ? <Field label="Type">{item.document_type}</Field> : null}
                  {item.original_filename ? (
                    <Field label="File name">{item.original_filename}</Field>
                  ) : null}
                  {item.mime_type ? <Field label="Format">{item.mime_type}</Field> : null}
                  <Field label="Processing">
                    <StatusBadge
                      value={processingStateLabel(item.processing_status)}
                      tone={processingStateTone(item.processing_status)}
                    />{" "}
                    <span className="muted">
                      {processingStateNote(item.processing_status)}
                    </span>
                  </Field>
                  {item.status ? (
                    <Field label="Evidence status">
                      <StatusBadge value={item.status} tone="neutral" />
                    </Field>
                  ) : null}
                  <Field label="Requirement association">
                    {item.linked_requirement_ids.length > 0 ? (
                      <span>
                        {item.linked_requirement_ids.map((id) => (
                          <Identifier key={id} value={id} short={36} />
                        ))}
                      </span>
                    ) : (
                      <span className="muted">
                        Requirement association will be determined from the compliance context.
                      </span>
                    )}
                  </Field>
                  {item.duplicate ? (
                    <Field label="Note">
                      <span className="muted">
                        This document was already uploaded — the existing record is shown.
                      </span>
                    </Field>
                  ) : null}
                  <Field label="Workflow status">
                    {supplied.has(item.evidence_id) ? (
                      <span>Supplied to this workflow</span>
                    ) : (
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={locked || item.processing_status === "failed"}
                        title={
                          item.processing_status === "failed"
                            ? "Failed documents cannot be supplied"
                            : undefined
                        }
                        onClick={() => void supply(item.evidence_id)}
                      >
                        {pending === `supply-${item.evidence_id}`
                          ? "Supplying…"
                          : "Supply to workflow"}
                      </button>
                    )}
                  </Field>
                  <Field label="Document">
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={pending !== null}
                      onClick={() => void download(item.evidence_id)}
                    >
                      {pending === `download-${item.evidence_id}`
                        ? "Preparing…"
                        : "Download document"}
                    </button>
                  </Field>
                </dl>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="action-row">
        <Link className="secondary-button" to="../gaps">
          Review evidence gaps
        </Link>
        <Link className="secondary-button" to="../analysis">
          {hasAnalysisRounds ? "Run analysis again" : "Continue to analysis"}
        </Link>
        <AskXportraButton
          seed={{ intent: "explain_evidence_gaps", focus: "evidence" }}
          label="Ask Xportra"
          className="secondary-button"
        />
      </div>
    </div>
  );
}
