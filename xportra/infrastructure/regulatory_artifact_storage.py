"""Regulatory source artifact storage adapter using existing Supabase Storage.

Reuses `SupabaseEvidenceObjectStore` and `SupabaseStorageSettings`
but with the dedicated private bucket (`regulatory-source-artifacts`)
rather than the tenant-evidence bucket. Configured from the same
`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (existing `.env`
placeholders); the bucket name can be overridden by
`REGULATORY_SOURCE_ARTIFACTS_BUCKET` (defaults to
`regulatory-source-artifacts`).

This adapter does NOT invent a new authorization mechanism; access
is mediated by the application layer (global staff authorization via
`GRANT_MANAGE`) before any mutation reaches this boundary.
"""
from __future__ import annotations

import os
from typing import Mapping

from xportra.domain.evidence_storage import (
    EvidenceStorageError,
    EvidenceStorageConfigurationError,
)
from xportra.infrastructure.evidence_storage import (
    SupabaseEvidenceObjectStore,
    SupabaseStorageSettings,
)
from xportra.domain.regulatory_artifact_storage import (
    REGULATORY_SOURCE_ARTIFACTS_BUCKET,
)


class RegulatorySourceStorageSettings(SupabaseStorageSettings):
    """Storage settings for the dedicated regulatory artifact bucket."""

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "RegulatorySourceStorageSettings":
        values = os.environ if environment is None else environment
        try:
            base_url = values.get("SUPABASE_URL", "")
            service_role_key = values.get("SUPABASE_SERVICE_ROLE_KEY", "")
            bucket = values.get("REGULATORY_SOURCE_ARTIFACTS_BUCKET", "")
        except AttributeError as cause:
            raise EvidenceStorageConfigurationError(
                "regulatory source artifact storage is not configured"
            ) from cause
        return cls(
            base_url=base_url,
            service_role_key=service_role_key,
            bucket=bucket or REGULATORY_SOURCE_ARTIFACTS_BUCKET,
        )


class RegulatorySourceStorageAdapter:
    """Private storage adapter for regulatory source artifacts."""

    def __init__(self, settings: RegulatorySourceStorageSettings | None = None) -> None:
        if settings is None:
            settings = RegulatorySourceStorageSettings.from_environment()
        self._store = SupabaseEvidenceObjectStore(settings)

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        return self._store.put(key, content, content_type=content_type)

    def delete(self, key: str) -> None:
        return self._store.delete(key)

    def create_signed_url(self, key: str, *, expires_in_seconds: int = 300) -> str:
        return self._store.create_signed_url(key, expires_in_seconds=expires_in_seconds)
