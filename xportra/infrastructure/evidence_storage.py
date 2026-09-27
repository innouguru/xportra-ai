"""Evidence object-storage implementations for Phase 10.4.

Two ``EvidenceObjectStore`` implementations behind the
domain protocol (``xportra.domain.evidence_storage``):

- ``InMemoryEvidenceObjectStore`` — deterministic,
  dependency-free store for unit tests and local
  development without credentials. Signed URLs are
  opaque unguessable tokens (no keys embedded); nothing
  here is a public URL.
- ``SupabaseEvidenceObjectStore`` — private Supabase
  Storage over plain HTTPS (``httpx``, already a
  declared dependency; no vendor SDK enters the
  codebase). Server-side puts, compensating deletes,
  and short-lived signed URLs. Configuration reads the
  canonical ``SUPABASE_URL`` plus ``SUPABASE_SERVICE_ROLE_KEY``
  (documented placeholders in ``.env.example``); missing
  configuration fails closed at composition time.

Neither implementation logs keys, URLs, bytes, or
credentials, and every failure raises
``EvidenceStorageError`` with a static message so the
Phase 10.1 error surface has nothing sensitive to
strip. Raw file bytes never leave this boundary except
toward the storage backend itself.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Mapping
from uuid import uuid4

import httpx

from xportra.domain.evidence_storage import (
    DEFAULT_DOWNLOAD_URL_TTL_SECONDS,
    EVIDENCE_STORAGE_BUCKET,
    EvidenceObjectStore,
    EvidenceStorageConfigurationError,
    EvidenceStorageError,
)


class InMemoryEvidenceObjectStore:
    """Deterministic in-memory object store (tests/dev only)."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}
        self._tokens: dict[str, tuple[str, float]] = {}

    @property
    def objects(self) -> dict[str, tuple[bytes, str]]:
        """Stored ``key -> (bytes, content_type)`` (test inspection)."""
        return dict(self._objects)

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        _require_key(key)
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise EvidenceStorageError("evidence object write failed")
        if not isinstance(content_type, str) or not content_type.strip():
            raise EvidenceStorageError("evidence object write failed")
        self._objects[key] = (bytes(content), content_type.strip().lower())

    def delete(self, key: str) -> None:
        _require_key(key)
        self._objects.pop(key, None)
        for token, (mapped, _) in list(self._tokens.items()):
            if mapped == key:
                del self._tokens[token]

    def create_signed_url(
        self,
        key: str,
        *,
        expires_in_seconds: int = DEFAULT_DOWNLOAD_URL_TTL_SECONDS,
    ) -> str:
        _require_key(key)
        _require_ttl(expires_in_seconds)
        if key not in self._objects:
            raise EvidenceStorageError("evidence download is unavailable")
        token = f"{uuid4().hex}{secrets.token_hex(8)}"
        self._tokens[token] = (key, time.monotonic() + expires_in_seconds)
        return f"inmemory://{EVIDENCE_STORAGE_BUCKET}/download/{token}"

    def resolve_token(self, token: str) -> bytes | None:
        """Resolve one issued token to its bytes (test/dev only)."""
        entry = self._tokens.get(token)
        if entry is None:
            return None
        key, expires_at = entry
        if time.monotonic() > expires_at:
            del self._tokens[token]
            return None
        stored = self._objects.get(key)
        return stored[0] if stored is not None else None


class SupabaseStorageSettings:
    """Connection settings for private Supabase Storage."""

    def __init__(self, *, base_url: str, service_role_key: str,
                 bucket: str = EVIDENCE_STORAGE_BUCKET) -> None:
        base = base_url.strip() if isinstance(base_url, str) else ""
        secret = (service_role_key.strip()
                  if isinstance(service_role_key, str) else "")
        name = bucket.strip() if isinstance(bucket, str) else ""
        if not base or not secret or not name:
            raise EvidenceStorageConfigurationError(
                "evidence object storage is not configured")
        self.base_url = base.rstrip("/")
        self.service_role_key = secret
        self.bucket = name

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "SupabaseStorageSettings":
        values = os.environ if environment is None else environment
        try:
            base_url = values.get("SUPABASE_URL", "")
            service_role_key = values.get("SUPABASE_SERVICE_ROLE_KEY", "")
            bucket = values.get("EVIDENCE_STORAGE_BUCKET", "")
        except AttributeError as cause:
            raise EvidenceStorageConfigurationError(
                "evidence object storage is not configured") from cause
        return cls(
            base_url=base_url,
            service_role_key=service_role_key,
            bucket=bucket or EVIDENCE_STORAGE_BUCKET,
        )


class SupabaseEvidenceObjectStore:
    """Private Supabase Storage over HTTPS (no vendor SDK)."""

    def __init__(
        self,
        settings: SupabaseStorageSettings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        if not isinstance(settings, SupabaseStorageSettings):
            raise EvidenceStorageConfigurationError(
                "evidence object storage is not configured")
        self._settings = settings
        self._client = client

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self._settings.base_url}{path}"
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {self._settings.service_role_key}"
        headers["apikey"] = self._settings.service_role_key
        client = self._client
        try:
            if client is not None:
                response = client.request(
                    method, url, headers=headers, **kwargs)
            else:
                with httpx.Client(timeout=30.0) as owned:
                    response = owned.request(
                        method, url, headers=headers, **kwargs)
        except httpx.HTTPError as cause:
            raise EvidenceStorageError(
                "evidence object storage is unavailable") from cause
        return response

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        _require_key(key)
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise EvidenceStorageError("evidence object write failed")
        if not isinstance(content_type, str) or not content_type.strip():
            raise EvidenceStorageError("evidence object write failed")
        response = self._request(
            "PUT",
            f"/storage/v1/object/{self._settings.bucket}/{key}",
            content=bytes(content),
            headers={
                "Content-Type": content_type.strip().lower(),
                "x-upsert": "true",
            },
        )
        if response.status_code not in (200, 201):
            raise EvidenceStorageError("evidence object write failed")

    def delete(self, key: str) -> None:
        _require_key(key)
        response = self._request(
            "DELETE",
            f"/storage/v1/object/{self._settings.bucket}/{key}",
        )
        if response.status_code not in (200, 204, 404):
            raise EvidenceStorageError("evidence object delete failed")

    def create_signed_url(
        self,
        key: str,
        *,
        expires_in_seconds: int = DEFAULT_DOWNLOAD_URL_TTL_SECONDS,
    ) -> str:
        _require_key(key)
        _require_ttl(expires_in_seconds)
        response = self._request(
            "POST",
            f"/storage/v1/object/sign/{self._settings.bucket}/{key}",
            json={"expiresIn": expires_in_seconds},
        )
        if response.status_code != 200:
            raise EvidenceStorageError("evidence download is unavailable")
        try:
            payload = response.json()
            signed_path = payload.get("signedURL")
        except (ValueError, AttributeError) as cause:
            raise EvidenceStorageError(
                "evidence download is unavailable") from cause
        if not isinstance(signed_path, str) or not signed_path.strip():
            raise EvidenceStorageError("evidence download is unavailable")
        path = signed_path.strip()
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._settings.base_url}{path}"


def _require_key(key: object) -> None:
    if not isinstance(key, str) or not key.strip():
        raise EvidenceStorageError("evidence object identity is malformed")
    if ".." in key.split("/") or key.startswith("/"):
        raise EvidenceStorageError("evidence object identity is malformed")


def _require_ttl(expires_in_seconds: object) -> None:
    if (isinstance(expires_in_seconds, bool)
            or not isinstance(expires_in_seconds, int)
            or expires_in_seconds <= 0
            or expires_in_seconds > 3600):
        raise EvidenceStorageError("download expiry is malformed")


# Static assertion: the in-memory implementation satisfies the protocol.
assert isinstance(InMemoryEvidenceObjectStore(), EvidenceObjectStore)


__all__ = [
    "InMemoryEvidenceObjectStore",
    "SupabaseEvidenceObjectStore",
    "SupabaseStorageSettings",
]
