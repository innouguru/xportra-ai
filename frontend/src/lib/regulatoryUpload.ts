/**
 * Presentation mirrors of the regulatory artifact upload contract
 * (POST /regulatory/sources/{source_id}/artifacts).
 *
 * The backend is authoritative: it independently validates content
 * type, size, base64 decoding, and authorization, and its answer is
 * final. These constants and helpers exist only for instant, honest
 * client-side feedback. They never claim unsupported content is valid
 * and never weaken a backend rejection.
 */

import { formatFileSize } from "./evidence";

/** Backend per-file limit for regulatory artifacts (decoded bytes). */
export const MAX_ARTIFACT_UPLOAD_BYTES = 10 * 1024 * 1024;

/** Native file-picker filter matching backend-supported artifact types. */
export const REGULATORY_ARTIFACT_ACCEPT = ".pdf,.txt,.md,.json";

/** Human list of the supported artifact formats. */
export const SUPPORTED_ARTIFACT_TEXT = "PDF, TXT, MD, or JSON";

/**
 * Content types the backend actually accepts
 * (ACCEPTED_ARTIFACT_CONTENT_TYPES in
 * xportra/application/regulatory_source_intake_service.py).
 */
const ALLOWED_ARTIFACT_MIMES = new Set([
  "application/pdf",
  "text/plain",
  "text/markdown",
  "application/json",
]);

/**
 * Extension → backend-accepted content type. Used when the browser
 * supplies no MIME type or a generic one, so such files still reach
 * the backend with a type it actually accepts.
 */
const ARTIFACT_MIME_BY_EXTENSION: Record<string, string> = {
  ".pdf": "application/pdf",
  ".txt": "text/plain",
  ".md": "text/markdown",
  ".json": "application/json",
};

/** Known artifact extension for a file name, or null. */
function artifactExtension(fileName: string): string | null {
  const lowered = fileName.toLowerCase();
  for (const extension of Object.keys(ARTIFACT_MIME_BY_EXTENSION)) {
    if (lowered.endsWith(extension)) {
      return extension;
    }
  }
  return null;
}

/**
 * A browser-supplied MIME type is trusted only when it names a
 * backend-accepted type. Empty and generic values cannot be trusted
 * and fall back to the file's extension instead.
 */
function isGenericMime(mime: string): boolean {
  return mime === "" || mime === "application/octet-stream";
}

/**
 * Instant client pre-check with an actionable message, or null when
 * the file looks acceptable. Advisory only: the backend revalidates
 * type, size, and content and its answer is final.
 */
export function describeUnsupportedArtifactFile(file: {
  name: string;
  size: number;
  type: string;
}): string | null {
  if (file.size === 0) {
    return `“${file.name}” is empty and cannot be uploaded. Choose a non-empty file.`;
  }
  if (file.size > MAX_ARTIFACT_UPLOAD_BYTES) {
    return `“${file.name}” is ${formatFileSize(file.size)}, over the 10 MB limit. Choose a smaller file.`;
  }
  const extension = artifactExtension(file.name);
  if (!extension) {
    return `“${file.name}” is not a supported artifact format. Choose ${SUPPORTED_ARTIFACT_TEXT} (max 10 MB).`;
  }
  const mime = (file.type ?? "").trim().toLowerCase();
  if (!isGenericMime(mime) && !ALLOWED_ARTIFACT_MIMES.has(mime)) {
    return `“${file.name}” reports an unsupported content type (${file.type}). Choose ${SUPPORTED_ARTIFACT_TEXT} (max 10 MB).`;
  }
  return null;
}

/**
 * Content type sent to the backend for a validated file. A specific,
 * backend-accepted MIME type the browser reported wins; an empty or
 * generic one maps to the extension-derived backend-accepted type, so
 * the request never carries a type the backend must reject.
 */
export function resolveArtifactContentType(file: {
  name: string;
  type: string;
}): string {
  const mime = (file.type ?? "").trim().toLowerCase();
  if (mime && ALLOWED_ARTIFACT_MIMES.has(mime)) {
    return mime;
  }
  const extension = artifactExtension(file.name);
  if (extension) {
    return ARTIFACT_MIME_BY_EXTENSION[extension];
  }
  return "application/octet-stream";
}
