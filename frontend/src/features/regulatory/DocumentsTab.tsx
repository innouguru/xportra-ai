import { useCallback, useState } from "react";
import { userFacingErrorMessage } from "../../api/client";
import { uploadRegulatoryArtifact } from "../../api/regulatory";
import { StatusBadge } from "../../components/StatusBits";
import {
  REGULATORY_ARTIFACT_ACCEPT,
  SUPPORTED_ARTIFACT_TEXT,
  describeUnsupportedArtifactFile,
  resolveArtifactContentType,
} from "../../lib/regulatoryUpload";
import { useSourceContext } from "./SourceContext";
import { createdAt, tone } from "./regulatoryUi";

/** Uploaded originals, and the upload form (the primary action here). */
export function DocumentsTab() {
  const { auth, sourceId, source, artifacts, loading, reload } = useSourceContext();
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const handleUpload = useCallback(
    async (file: File) => {
      const fileRejection = describeUnsupportedArtifactFile(file);
      if (fileRejection) {
        setUploadError(fileRejection);
        return;
      }
      setUploadPending(true);
      setUploadError(null);
      setUploadSuccess(null);
      try {
        const content_base64 = await file.arrayBuffer().then((buf) => {
          const bytes = new Uint8Array(buf);
          const chunkSize = 0x8000;
          let binary = "";
          for (let offset = 0; offset < bytes.length; offset += chunkSize) {
            const chunk = bytes.subarray(offset, offset + chunkSize);
            binary += String.fromCharCode(...chunk);
          }
          return btoa(binary);
        });
        const result = await uploadRegulatoryArtifact(auth, sourceId, {
          content_base64,
          content_type: resolveArtifactContentType(file),
          source_version: source.version ?? null,
        });
        setUploadSuccess(
          `Artifact “${file.name}” uploaded (${result.content_length} bytes, ${result.content_type}).`,
        );
        setUploadFile(null);
        await reload();
      } catch (caught) {
        setUploadError(userFacingErrorMessage(caught));
      } finally {
        setUploadPending(false);
      }
    },
    [auth, sourceId, source.version, reload],
  );

  return (
    <div>
      <section aria-label="Upload artifact">
        <h2>Upload original regulatory document</h2>
        <p className="muted">
          Supported: {SUPPORTED_ARTIFACT_TEXT} (max 10 MB). The backend
          validates every file; unsupported or oversized files are rejected.
        </p>
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault();
            if (uploadFile) {
              void handleUpload(uploadFile);
            }
          }}
        >
          <fieldset>
            <div className="form-row reg-dropzone">
              <label htmlFor="artifact-file">Choose file</label>
              <input
                id="artifact-file"
                type="file"
                accept={REGULATORY_ARTIFACT_ACCEPT}
                disabled={uploadPending || loading}
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  if (!file) {
                    setUploadFile(null);
                    return;
                  }
                  const fileRejection = describeUnsupportedArtifactFile(file);
                  if (fileRejection) {
                    // Unsupported files are never stored as the
                    // selection, so the submit path cannot send them.
                    setUploadFile(null);
                    setUploadError(fileRejection);
                    setUploadSuccess(null);
                    event.target.value = "";
                    return;
                  }
                  setUploadError(null);
                  setUploadFile(file);
                }}
              />
            </div>
            {uploadFile ? (
              <div className="form-row">
                <p className="hint">
                  Selected: {uploadFile.name} ({Math.round(uploadFile.size / 1024)} KB,{" "}
                  {uploadFile.type || "unknown type"})
                </p>
              </div>
            ) : null}
          </fieldset>
          <div className="form-row">
            <button
              type="submit"
              className="primary-button"
              disabled={uploadPending || loading || !uploadFile}
            >
              {uploadPending ? "Uploading…" : "Upload document"}
            </button>
          </div>
        </form>
        {uploadError ? (
          <p role="alert" className="ledger-reason">{uploadError}</p>
        ) : null}
        {uploadSuccess ? (
          <p className="success-message" role="status">{uploadSuccess}</p>
        ) : null}
      </section>

      <h2>Artifacts</h2>
      {artifacts.length === 0 ? (
        <p className="muted">No artifacts uploaded for this source.</p>
      ) : (
        <ol className="ledger">
          {artifacts.map((artifact) => (
            <li key={artifact.id} className="ledger-row">
              <dl className="ledger-status">
                <div>
                  <dt>Content type</dt>
                  <dd>{artifact.content_type}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>
                    <StatusBadge value={artifact.status} tone={tone(artifact.status)} />
                  </dd>
                </div>
                <div>
                  <dt>Acquired at</dt>
                  <dd>{createdAt(artifact.acquired_at)}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
