"""Provider-independent identity helpers for published regulatory evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def regulatory_publication_fingerprint(row: Mapping[str, Any]) -> str:
    """Fingerprint the exact publication fields represented in the index."""
    record = {
        "requirement_text": row.get("requirement_text"),
        "source_id": str(row.get("source_id")),
        "normalized_document_id": str(
            row.get("normalized_document_id")),
        "source_location": row.get("source_location"),
        "position": row.get("position"),
        "parser_version": row.get("parser_version"),
        "source_title": row.get("source_title"),
        "source_jurisdiction": row.get("source_jurisdiction"),
        "source_version": row.get("source_version"),
    }
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
