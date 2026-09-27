"""Private evidence object-storage boundary for Phase 10.4.

R-10.4 U4: one private bucket, server-composed keys,
server-authorized access via short-lived signed URLs.
The domain and application layers depend only on the
``EvidenceObjectStore`` protocol below — never on
Supabase SDK details (``xportra.infrastructure``
holds the implementations).

Rules enforced by construction:

- Object keys are composed server-side
  (``evidence_upload.compose_object_key``); the client
  can never supply an arbitrary key, path, or bucket.
- No public buckets, public object URLs, or
  unrestricted downloads exist in this boundary.
- Storage errors carry static operational messages
  only — never keys, URLs, file bytes, or credentials —
  so the existing Phase 10.1 error sanitization has
  nothing sensitive to strip.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .errors import DomainError

#: The single private bucket holding tenant evidence objects.
EVIDENCE_STORAGE_BUCKET = "tenant-evidence"

#: Lifetime of server-issued download URLs (5 minutes).
DEFAULT_DOWNLOAD_URL_TTL_SECONDS = 300


class EvidenceStorageError(DomainError):
    """An object-storage operation failed.

    Messages are static by convention — implementations
    must not embed keys, URLs, bytes, or credentials.
    """


class EvidenceStorageConfigurationError(DomainError):
    """Object storage is not configured for this deployment."""


@runtime_checkable
class EvidenceObjectStore(Protocol):
    """Server-mediated private object storage.

    ``put``/``delete``/``create_signed_url`` are the only
    storage mutations that exist. ``delete`` serves the
    single compensating case (registration failure after
    a put); there is no user-facing delete path (U3).
    Download authorization happens before this boundary
    is reached — implementations issue access, they never
    authorize it.
    """

    def put(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
    ) -> None:
        """Store bytes under a server-composed key."""
        ...  # pragma: no cover - protocol

    def delete(self, key: str) -> None:
        """Remove one object (compensating delete only)."""
        ...  # pragma: no cover - protocol

    def create_signed_url(
        self,
        key: str,
        *,
        expires_in_seconds: int = DEFAULT_DOWNLOAD_URL_TTL_SECONDS,
    ) -> str:
        """Issue a short-lived download URL for one key."""
        ...  # pragma: no cover - protocol


__all__ = [
    "DEFAULT_DOWNLOAD_URL_TTL_SECONDS",
    "EVIDENCE_STORAGE_BUCKET",
    "EvidenceObjectStore",
    "EvidenceStorageConfigurationError",
    "EvidenceStorageError",
]
