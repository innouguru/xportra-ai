/**
 * Pure presentation helpers for evidence state.
 *
 * Backend vocabularies render verbatim; tones only aid
 * scanning and never carry verdict meaning. In particular:
 * missing/insufficient/unknown/contradictory evidence is
 * NEVER mapped to non-compliant, failed, scores, or
 * percentages — no such mapping exists here.
 */

/** Evidence sufficiency states (evidence_sufficiency). */
export function sufficiencyTone(value: string): "info" | "muted" | "attention" | "neutral" {
  if (value === "supported") return "info";
  if (value === "unknown") return "attention";
  if (value === "missing" || value === "insufficient") return "attention";
  return "neutral";
}

/** Readiness states (readiness_state). Informational only. */
export function readinessTone(value: string): "info" | "muted" | "attention" | "neutral" {
  if (value === "ready") return "info";
  if (value === "partially_ready") return "attention";
  if (value === "not_ready") return "attention";
  return "neutral";
}

/** Gap kinds render verbatim — the backend owns their meaning. */
export function gapKindLabel(kind: string): string {
  return kind;
}

/** Contradiction states render verbatim; presence is shown, never resolved. */
export function contradictionTone(value: string): "attention" | "neutral" | "muted" {
  if (value === "present") return "attention";
  if (value === "none") return "muted";
  return "neutral";
}

/**
 * Upload constants (presentation mirrors of the backend
 * contract — the backend remains authoritative on every
 * rule below; these exist only for instant, honest
 * client feedback and labeling).
 */

/** Backend per-file limit (R-10.4 U2). */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

/** Native file-picker filter for the MVP types (R-10.4 U1). */
export const UPLOAD_ACCEPT = ".pdf,.docx,.jpg,.jpeg,.png";

/** Human list of the supported formats. */
export const SUPPORTED_UPLOAD_TEXT = "PDF, Word (.docx), JPEG, or PNG";

/** Advisory MIME allow-list for instant feedback (never a verdict). */
const SUPPORTED_UPLOAD_MIMES: Record<string, string[]> = {
  ".pdf": ["application/pdf"],
  ".docx": [
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ],
  ".jpg": ["image/jpeg"],
  ".jpeg": ["image/jpeg"],
  ".png": ["image/png"],
};

/** Human file size ("10 MB", "512 KB"). */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "unknown size";
  if (bytes < 1024) return `${bytes} B`;
  const kilobytes = bytes / 1024;
  if (kilobytes < 1024) {
    const rounded = Math.round(kilobytes * 10) / 10;
    return `${Number.isInteger(rounded) ? rounded.toFixed(0) : String(rounded)} KB`;
  }
  const megabytes = kilobytes / 1024;
  const rounded = Math.round(megabytes * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : String(rounded)} MB`;
}

/**
 * Instant client pre-check with an actionable message, or
 * null when the file looks acceptable. Advisory only:
 * the backend revalidates type, size, and content and its
 * answer is final.
 */
export function describeUnsupportedFile(file: { name: string; size: number; type: string }): string | null {
  if (file.size > MAX_UPLOAD_BYTES) {
    return `“${file.name}” is ${formatFileSize(file.size)}, over the 10 MB limit. Choose a smaller file.`;
  }
  const lowered = file.name.toLowerCase();
  const extension = Object.keys(SUPPORTED_UPLOAD_MIMES).find((ext) => lowered.endsWith(ext));
  if (!extension) {
    return `“${file.name}” is not a supported format. Choose ${SUPPORTED_UPLOAD_TEXT} (max 10 MB).`;
  }
  if (file.type && !SUPPORTED_UPLOAD_MIMES[extension].includes(file.type.toLowerCase())) {
    return `“${file.name}” does not look like a ${extension} file. Choose ${SUPPORTED_UPLOAD_TEXT} (max 10 MB).`;
  }
  return null;
}

/** Upload processing states render verbatim. */
export function processingStateLabel(state: string | null | undefined): string {
  if (state === "uploaded") return "Uploaded";
  if (state === "processing") return "Processing";
  if (state === "ready") return "Ready";
  if (state === "failed") return "Failed";
  return state ?? "Unknown";
}

/** Processing tones aid scanning; only `failed` draws attention. */
export function processingStateTone(state: string | null | undefined): "info" | "muted" | "attention" | "neutral" {
  if (state === "ready" || state === "processing") return "info";
  if (state === "failed") return "attention";
  if (state === "uploaded") return "neutral";
  return "muted";
}

/**
 * Honest one-line explanation per processing state.
 * Ready never implies satisfied; failed never reads as usable.
 */
export function processingStateNote(state: string | null | undefined): string {
  if (state === "processing") {
    return "Xportra is reading and indexing this document. It is not usable as evidence yet.";
  }
  if (state === "ready") {
    return "Processed and available as evidence. This does not mean any requirement is satisfied.";
  }
  if (state === "failed") {
    return "Processing failed, so this document cannot be used as evidence. Upload it again or choose another file.";
  }
  return "Received. Processing has not finished.";
}
