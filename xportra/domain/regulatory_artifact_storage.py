"""Private regulatory-source artifact storage boundary (Task — Storage Technology Review).

Seperate from tenant evidence (`tenant-evidence` bucket). Uses the same
protocol (`EvidenceObjectStore`) but with a dedicated bucket name
(`regulatory-source-artifacts`) and separate access control. The
implementation follows the technology baseline (`docs/architecture/technology-baseline.md`): private Supabase Storage, HTTPS, server-composed keys, no public access, signed URLs only.

This boundary does NOT invent a new authorization mechanism; access
is mediated by the application layer (global staff authorization via
`GRANT_MANAGE`) before any storage mutation reaches this boundary.
"""
from __future__ import annotations

from xportra.domain.evidence_storage import (
    EvidenceObjectStore,
    EvidenceStorageError,
    EvidenceStorageConfigurationError,
    DEFAULT_DOWNLOAD_URL_TTL_SECONDS,
)

#: Dedicated private bucket for global regulatory source artifacts.
#: Must remain separate from tenant-evidence (`EVIDENCE_STORAGE_BUCKET`).
REGULATORY_SOURCE_ARTIFACTS_BUCKET = "regulatory-source-artifacts"

__all__ = [
    "REGULATORY_SOURCE_ARTIFACTS_BUCKET",
    "DEFAULT_DOWNLOAD_URL_TTL_SECONDS",
    "EvidenceObjectStore",
    "EvidenceStorageError",
    "EvidenceStorageConfigurationError",
]
