"""Minimal regulatory-source acquisition and parsing foundation for Phase 2.x.

This layer stays intentionally narrow: it models the boundary between a source,
an acquired artifact, and the first processing step that turns accepted artifact
content into a normalized regulatory document representation without doing
retrieval, chunking, or compliance reasoning.
"""

from __future__ import annotations

import json
import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5


class AcquisitionValidationError(ValueError):
    """Raised when acquisition metadata is insufficient or invalid."""


class ArtifactParseError(ValueError):
    """Raised when a supported artifact cannot be parsed or yields empty content."""


class ArtifactNormalizationError(ValueError):
    """Raised when parsed content cannot be normalized safely."""


class RegulatoryMetadataExtractionError(ValueError):
    """Raised when a normalized document cannot provide a valid metadata record."""


class RegulatoryRequirementExtractionError(ValueError):
    """Raised when a normalized document cannot be inspected for requirements."""


class RegulatoryRequirementApplicabilityValidationError(ValueError):
    """Raised when applicability input is incomplete or structurally invalid."""


class RequirementAssessmentValidationError(ValueError):
    """Raised when evidence or applicability assessment input is invalid."""


class ComplianceCaseValidationError(ValueError):
    """Raised when a compliance case cannot be composed safely."""


class ComplianceSummaryValidationError(ValueError):
    """Raised when a compliance summary input is invalid or crosses tenants."""


@dataclass(frozen=True)
class ApplicabilityContext:
    """Minimal tenant-owned facts used by deterministic applicability rules."""

    tenant_id: UUID | None = None
    exporter_id: UUID | None = None
    exporter_name: str | None = None
    origin_country: str | None = None
    destination_country: str | None = None
    commodity: str | None = None
    product_category: str | None = None
    business_characteristics: dict[str, Any] | None = None
    actor_role: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, UUID):
            raise RegulatoryRequirementApplicabilityValidationError("tenant_id is required")


class ArtifactParsingService:
    """Parse supported regulatory artifacts into a stable document representation."""

    SUPPORTED_CONTENT_TYPES = {
        "text/plain",
        "text/markdown",
        "application/json",
    }

    def parse(self, *, artifact_id: UUID, content_type: str, raw_content: str | bytes) -> dict[str, Any]:
        mime_type = (content_type or "").strip().lower()
        if mime_type not in self.SUPPORTED_CONTENT_TYPES:
            raise ArtifactParseError(f"unsupported artifact content type: {content_type}")

        text = self._decode(raw_content)
        if not text or not text.strip():
            raise ArtifactParseError("artifact content is empty or unreadable")

        if mime_type == "application/json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:  # pragma: no branch - explicit parse failure
                raise ArtifactParseError("malformed JSON artifact") from exc

            blocks = self._extract_json_blocks(payload)
            if not blocks:
                raise ArtifactParseError("JSON artifact produced no usable text content")

            normalized_text = "\n\n".join(blocks)
            title = self._extract_title(payload, blocks)
            structure = self._json_structure(payload)
        else:
            if mime_type == "text/markdown":
                structure = self._markdown_structure(text)
            else:
                structure = self._plain_text_structure(text)

            title = self._extract_title_from_text(text)
            normalized_text = self._collapse_structure(structure)

        if not normalized_text or not normalized_text.strip():
            raise ArtifactParseError("artifact produced empty normalized text")

        if title is None or not title.strip():
            title = self._fallback_title_from_text(normalized_text)

        return {
            "artifact_id": artifact_id,
            "document_title": title.strip(),
            "normalized_text": normalized_text.strip(),
            "normalized_content": {
                "mime_type": mime_type,
                "structure": structure,
            },
            "parser_name": "explicit_text_parser",
            "status": "parsed",
            "parsed_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def _decode(raw_content: str | bytes) -> str:
        if isinstance(raw_content, bytes):
            try:
                return raw_content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ArtifactParseError("artifact is not valid UTF-8 text") from exc
        if not isinstance(raw_content, str):
            raise ArtifactParseError("artifact payload must be text or bytes")
        return raw_content

    @staticmethod
    def _extract_title(payload: Any, blocks: list[str]) -> str:
        if isinstance(payload, dict):
            for key in ("title", "document_title", "name", "heading"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ArtifactParsingService._fallback_title_from_text("\n\n".join(blocks))

    @staticmethod
    def _fallback_title_from_text(text: str) -> str:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "Untitled Regulatory Document")
        return first_line.strip() or "Untitled Regulatory Document"

    @staticmethod
    def _extract_title_from_text(text: str) -> str | None:
        for line in text.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            if candidate.startswith("#"):
                return candidate.lstrip("#").strip()
            return candidate
        return None

    @staticmethod
    def _extract_json_blocks(payload: Any) -> list[str]:
        if isinstance(payload, dict):
            blocks: list[str] = []
            for key, value in payload.items():
                if key in {"title", "document_title", "name", "heading"}:
                    if isinstance(value, str) and value.strip():
                        blocks.append(value.strip())
                elif isinstance(value, str) and value.strip():
                    blocks.append(value.strip())
                elif isinstance(value, list):
                    blocks.extend(ArtifactParsingService._extract_json_blocks(value))
                elif isinstance(value, dict):
                    blocks.extend(ArtifactParsingService._extract_json_blocks(value))
            return blocks

        if isinstance(payload, list):
            blocks: list[str] = []
            for value in payload:
                blocks.extend(ArtifactParsingService._extract_json_blocks(value))
            return blocks

        if isinstance(payload, str) and payload.strip():
            return [payload.strip()]

        return []

    @staticmethod
    def _json_structure(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            structure: list[dict[str, Any]] = []
            for key, value in payload.items():
                if key in {"title", "document_title", "name"} and isinstance(value, str):
                    structure.append({"kind": "heading", "text": value.strip()})
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            heading = item.get("heading") or item.get("title") or key
                            body = item.get("body") or item.get("text") or item.get("content")
                            if isinstance(heading, str) and heading.strip():
                                structure.append({"kind": "heading", "text": heading.strip()})
                            if isinstance(body, str) and body.strip():
                                structure.append({"kind": "section", "text": body.strip()})
                elif isinstance(value, str) and value.strip():
                    structure.append({"kind": "section", "text": value.strip()})
            return structure or [{"kind": "section", "text": json.dumps(payload, ensure_ascii=False)}]

        if isinstance(payload, list):
            return [{"kind": "section", "text": str(item)} for item in payload if str(item).strip()]

        return [{"kind": "section", "text": str(payload).strip()}]

    @staticmethod
    def _plain_text_structure(text: str) -> list[dict[str, Any]]:
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
        return [{"kind": "section", "text": block} for block in blocks]

    @staticmethod
    def _markdown_structure(text: str) -> list[dict[str, Any]]:
        structure: list[dict[str, Any]] = []
        current_heading: str | None = None
        current_section: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("#"):
                if current_heading is not None and current_section:
                    structure.append({"kind": "section", "text": "\n".join(current_section).strip()})
                heading = stripped.lstrip("#").strip()
                current_heading = heading
                structure.append({"kind": "heading", "text": heading})
                current_section = []
                continue

            if current_heading is not None:
                current_section.append(stripped)

        if current_section:
            structure.append({"kind": "section", "text": "\n".join(current_section).strip()})

        if not structure:
            return [{"kind": "section", "text": text.strip()}]
        return structure

    @staticmethod
    def _collapse_structure(structure: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for item in structure:
            text_value = str(item.get("text") or "").strip()
            if text_value:
                parts.append(text_value)
        return "\n\n".join(parts)


class ArtifactNormalizationService:
    """Normalize parsed artifacts into a stable document record."""

    def __init__(self, repository: Any, parser_service: ArtifactParsingService | None = None) -> None:
        self._repository = repository
        self._parser_service = parser_service or ArtifactParsingService()

    def normalize(
        self,
        *,
        artifact_id: UUID,
        source_id: UUID,
        content_type: str,
        raw_content: str | bytes,
        parser_name: str | None = None,
        normalized_at: datetime | None = None,
    ) -> dict[str, Any]:
        existing = self._repository.get_by_artifact(artifact_id)
        if existing is not None:
            return existing

        parsed = self._parser_service.parse(
            artifact_id=artifact_id,
            content_type=content_type,
            raw_content=raw_content,
        )

        normalized_text = parsed["normalized_text"].strip()
        if not normalized_text:
            raise ArtifactNormalizationError("normalized text is empty after parsing")

        record_id = uuid5(NAMESPACE_URL, f"{artifact_id}:{source_id}:{normalized_text}")
        now = normalized_at or datetime.now(timezone.utc)

        row = self._repository.create(
            id=record_id,
            artifact_id=artifact_id,
            source_id=source_id,
            document_title=parsed["document_title"],
            normalized_text=normalized_text,
            normalized_content=parsed["normalized_content"],
            content_type=content_type,
            parser_name=parser_name or parsed["parser_name"],
            status="normalized",
            normalized_at=now,
            created_at=now,
            updated_at=now,
        )
        return row


class RegulatoryMetadataExtractionService:
    """Extract explicit regulatory document metadata without semantic inference."""

    CLASSIFICATIONS = {"regulation", "standard", "guideline", "procedure", "notice", "form"}
    METADATA_KEYS = {
        "title": "document_title",
        "document_title": "document_title",
        "authority": "authority_name",
        "authority_name": "authority_name",
        "document_type": "document_type",
        "category": "document_type",
        "publication_date": "publication_date",
        "effective_date": "effective_date",
        "reference": "reference_identifier",
        "reference_identifier": "reference_identifier",
        "version": "version",
        "jurisdiction": "jurisdiction",
        "language": "language",
    }

    def __init__(self, repository: Any | None = None) -> None:
        self._repository = repository

    def extract(self, normalized_document: dict[str, Any]) -> dict[str, Any]:
        document_id = normalized_document.get("id")
        artifact_id = normalized_document.get("artifact_id")
        source_id = normalized_document.get("source_id")
        if document_id is None or artifact_id is None or source_id is None:
            raise RegulatoryMetadataExtractionError(
                "normalized document must include id, artifact_id, and source_id"
            )

        content = normalized_document.get("normalized_content")
        if not isinstance(content, dict):
            raise RegulatoryMetadataExtractionError("normalized_content must be an object")

        metadata = self._metadata_values(normalized_document, content)
        structure = content.get("structure")
        if not isinstance(structure, list):
            structure = []

        document_title = metadata["document_title"]
        if not document_title:
            document_title = self._title_from_structure(structure)

        sections = self._sections(structure, document_title)
        raw_document_type = metadata["document_type"]
        if isinstance(raw_document_type, str):
            raw_document_type = raw_document_type.lower()
        classification = (
            raw_document_type.lower()
            if isinstance(raw_document_type, str) and raw_document_type.lower() in self.CLASSIFICATIONS
            else "unknown"
        )

        return {
            "normalized_document_id": document_id,
            "artifact_id": artifact_id,
            "source_id": source_id,
            "document_title": document_title,
            "authority_name": metadata["authority_name"],
            "document_type": raw_document_type,
            "classification": classification,
            "publication_date": self._date_value(metadata["publication_date"], "publication_date"),
            "effective_date": self._date_value(metadata["effective_date"], "effective_date"),
            "reference_identifier": metadata["reference_identifier"],
            "version": metadata["version"],
            "jurisdiction": metadata["jurisdiction"],
            "language": metadata["language"],
            "sections": sections,
            "status": "extracted",
        }

    def process(self, normalized_document: dict[str, Any]) -> dict[str, Any]:
        extracted = self.extract(normalized_document)
        if self._repository is None:
            return extracted

        existing = self._repository.get_by_document(extracted["normalized_document_id"])
        if existing is not None:
            return existing

        return self._repository.create(**extracted)

    @classmethod
    def _metadata_values(cls, document: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
        values = {field: None for field in set(cls.METADATA_KEYS.values())}
        source_metadata = document.get("source_metadata")
        if not isinstance(source_metadata, dict):
            source_metadata = {}
        for key, field in cls.METADATA_KEYS.items():
            value = content.get(key)
            if value is None:
                value = document.get(key)
            if value is None:
                value = source_metadata.get(key)
            if isinstance(value, str):
                value = value.strip() or None
            if value is not None:
                values[field] = value
        return values

    @staticmethod
    def _title_from_structure(structure: list[Any]) -> str | None:
        for item in structure:
            if isinstance(item, dict) and item.get("kind") == "heading":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        return None

    @classmethod
    def _sections(cls, structure: list[Any], document_title: str | None) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        stack: list[tuple[int, int]] = []
        current: dict[str, Any] | None = None

        def flush() -> None:
            if current is not None:
                current["text"] = "\n".join(current.pop("_text_parts", [])).strip() or None

        for item in structure:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind")
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            text = text.strip()

            if kind == "heading":
                flush()
                level = item.get("level", 1)
                level = level if isinstance(level, int) and level > 0 else 1
                if not sections and document_title and text == document_title and level == 1:
                    stack = []
                    current = None
                    continue
                while stack and stack[-1][0] >= level:
                    stack.pop()
                parent_index = stack[-1][1] if stack else None
                section = {
                    "order": len(sections),
                    "heading": text,
                    "level": level,
                    "parent_index": parent_index,
                    "text": None,
                    "_text_parts": [],
                }
                sections.append(section)
                stack.append((level, section["order"]))
                current = section
            elif kind in {"section", "paragraph"}:
                if current is None:
                    section = {
                        "order": len(sections),
                        "heading": None,
                        "level": None,
                        "parent_index": None,
                        "text": text,
                        "_text_parts": [],
                    }
                    sections.append(section)
                else:
                    current.setdefault("_text_parts", []).append(text)

        flush()
        for section in sections:
            section.pop("_text_parts", None)
        return sections

    @staticmethod
    def _date_value(value: Any, field_name: str) -> Any:
        if value is None or isinstance(value, date):
            return value
        if not isinstance(value, str):
            raise RegulatoryMetadataExtractionError(f"{field_name} must be an ISO date")
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise RegulatoryMetadataExtractionError(f"{field_name} must be an ISO date") from exc


class RegulatoryRequirementExtractionService:
    """Extract explicit normative statements without determining applicability."""

    REQUIREMENT_TYPES = {
        "obligation",
        "prohibition",
        "documentation",
        "procedure",
        "threshold",
        "inspection",
        "certification",
        "labeling",
        "recordkeeping",
        "notification",
        "unknown",
    }
    NORMATIVE_PATTERN = re.compile(
        r"\b(?:shall(?:\s+not)?|must(?:\s+not)?|may\s+not|"
        r"may\s+(?:inspect|examine)|(?:is|are)\s+required\s+to|"
        r"(?:is|are)\s+prohibited\s+from)\b",
        re.IGNORECASE,
    )
    SENTENCE_PATTERN = re.compile(r"[^.!?]+(?:[.!?]|$)")
    THRESHOLD_PATTERN = re.compile(
        r"\b(?:at\s+least|at\s+most|no\s+more\s+than|no\s+less\s+than|"
        r"not\s+less\s+than|not\s+more\s+than|less\s+than|greater\s+than|"
        r"exceed(?:s|ing)?|equal\s+to)\s+[^,.;]+|[<>]=?\s*\d+(?:\.\d+)?\s*\w*",
        re.IGNORECASE,
    )
    CONDITION_PATTERN = re.compile(
        r"\b(?:if|when|unless|provided\s+that|where)\b\s+[^.;]+",
        re.IGNORECASE,
    )
    ACTOR_PATTERN = re.compile(
        r"^(?P<actor>.+?)\s+(?:shall\s+not|must\s+not|may\s+not|shall|must|"
        r"(?:is|are)\s+required\s+to|(?:is|are)\s+prohibited\s+from)\b",
        re.IGNORECASE,
    )

    def __init__(self, repository: Any | None = None) -> None:
        self._repository = repository

    def extract(self, normalized_document: dict[str, Any]) -> list[dict[str, Any]]:
        document_id = normalized_document.get("id")
        artifact_id = normalized_document.get("artifact_id")
        source_id = normalized_document.get("source_id")
        if document_id is None or artifact_id is None or source_id is None:
            raise RegulatoryRequirementExtractionError(
                "normalized document must include id, artifact_id, and source_id"
            )

        content = normalized_document.get("normalized_content")
        if not isinstance(content, dict):
            raise RegulatoryRequirementExtractionError("normalized_content must be an object")
        structure = content.get("structure")
        if not isinstance(structure, list):
            raise RegulatoryRequirementExtractionError("normalized_content.structure must be a list")

        records: list[dict[str, Any]] = []
        position = 0
        for section_index, section in enumerate(structure):
            if not isinstance(section, dict):
                continue
            text = section.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            heading = section.get("heading")
            for sentence in self.SENTENCE_PATTERN.findall(text):
                candidate = sentence.strip()
                if not self.NORMATIVE_PATTERN.search(candidate):
                    continue

                record = self._build_record(
                    document_id=document_id,
                    artifact_id=artifact_id,
                    source_id=source_id,
                    requirement_text=candidate,
                    source_location={
                        "section_order": section.get("order", section_index),
                        "heading": heading if isinstance(heading, str) else None,
                    },
                    position=position,
                )
                records.append(record)
                position += 1
        return records

    def process(self, normalized_document: dict[str, Any]) -> list[dict[str, Any]]:
        records = self.extract(normalized_document)
        if self._repository is None:
            return records

        existing = self._repository.list_for_document(normalized_document["id"])
        if existing:
            return existing
        return [self._repository.create(**record) for record in records]

    @classmethod
    def _build_record(
        cls,
        *,
        document_id: UUID,
        artifact_id: UUID,
        source_id: UUID,
        requirement_text: str,
        source_location: dict[str, Any],
        position: int,
    ) -> dict[str, Any]:
        lower_text = requirement_text.lower()
        requirement_type = cls._classify(lower_text)
        actor_match = cls.ACTOR_PATTERN.search(requirement_text)
        actor = actor_match.group("actor").strip() if actor_match else None
        condition_metadata: dict[str, str] = {}
        threshold_match = cls.THRESHOLD_PATTERN.search(requirement_text)
        if threshold_match:
            condition_metadata["threshold"] = threshold_match.group(0).strip()
        condition_match = cls.CONDITION_PATTERN.search(requirement_text)
        if condition_match:
            condition_metadata["condition"] = condition_match.group(0).strip()

        identity = f"{document_id}:{position}:{requirement_text.strip()}"
        return {
            "id": uuid5(NAMESPACE_URL, identity),
            "normalized_document_id": document_id,
            "artifact_id": artifact_id,
            "source_id": source_id,
            "requirement_text": requirement_text.strip(),
            "requirement_type": requirement_type,
            "source_location": source_location,
            "position": position,
            "actor": actor,
            "condition_metadata": condition_metadata or None,
            "status": "extracted",
        }

    @classmethod
    def _classify(cls, text: str) -> str:
        if re.search(r"\b(?:shall\s+not|must\s+not|may\s+not|prohibited)\b", text):
            return "prohibition"
        if re.search(r"\b(?:follow|perform|complete|carry\s+out|process|handle)\b", text):
            return "procedure"
        if re.search(r"\b(?:inspect|inspection|examine|examined)\b", text):
            return "inspection"
        if re.search(r"\b(?:notify|notifies|notification|inform|report)\b", text):
            return "notification"
        if re.search(r"\b(?:label|labeling|mark|marked)\b", text):
            return "labeling"
        if re.search(r"\b(?:keep|maintain|retain)\b.*\b(?:record|records|log|logs|document)\b", text):
            return "recordkeeping"
        if cls.THRESHOLD_PATTERN.search(text):
            return "threshold"
        if re.search(r"\b(?:submit|file|provide|present|produce|document)\w*\b", text):
            return "documentation"
        if re.search(r"\b(?:certif|certificate|certification)\w*\b", text):
            return "certification"
        if cls.NORMATIVE_PATTERN.search(text):
            return "obligation"
        return "unknown"


class RegulatoryRequirementApplicabilityService:
    """Evaluate explicit requirement facts against a tenant-owned context."""

    COUNTRY_ALIASES = {
        "nigeria": "ng",
        "ghana": "gh",
        "kenya": "ke",
        "south africa": "za",
        "united kingdom": "gb",
        "uk": "gb",
        "united states": "us",
        "usa": "us",
    }
    COUNTRY_PATTERN = re.compile(
        r"\b(?:nigeria|ghana|kenya|south\s+africa|united\s+kingdom|uk|"
        r"united\s+states|usa|ng|gh|ke|za|gb|us)\b",
        re.IGNORECASE,
    )
    COMMODITY_PATTERN = re.compile(
        r"\b(?:cocoa|coffee|maize|rice|sesame|seed|seeds|soybean|wheat|"
        r"cashew|cotton|palm\s+oil)\b",
        re.IGNORECASE,
    )
    THRESHOLD_PATTERN = re.compile(
        r"\b(at\s+least|at\s+most|no\s+more\s+than|no\s+less\s+than|"
        r"not\s+less\s+than|not\s+more\s+than|less\s+than|greater\s+than)\s+"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>tonnes?|kilograms?|kg|t)\b",
        re.IGNORECASE,
    )

    def __init__(self, repository: Any | None = None) -> None:
        self._repository = repository

    def evaluate(
        self,
        requirement: dict[str, Any],
        context: ApplicabilityContext,
    ) -> dict[str, Any]:
        self._validate_requirement(requirement)
        fingerprint = self.context_fingerprint(context)
        text = str(requirement["requirement_text"])
        reasons: list[str] = []
        unknown = False
        mismatch = False

        destinations = self._explicit_destinations(text, requirement)
        if destinations:
            destination = self._country(context.destination_country)
            if destination is None:
                unknown = True
                reasons.append("destination information insufficient")
            elif destination in destinations:
                reasons.append("matched destination")
            else:
                mismatch = True
                reasons.append("destination mismatch")

        commodities = self._explicit_commodities(text)
        if commodities:
            if not context.commodity:
                unknown = True
                reasons.append("commodity information insufficient")
            elif self._normalize_value(context.commodity) in commodities:
                reasons.append("matched commodity")
            else:
                mismatch = True
                reasons.append("commodity mismatch")

        actor = str(requirement.get("actor") or "").strip().lower()
        if actor:
            actor_role = self._normalize_value(context.actor_role)
            if "export" in actor:
                if actor_role == "exporter":
                    reasons.append("explicit actor match")
                else:
                    unknown = True
                    reasons.append("actor information insufficient")
            elif actor_role and actor_role in actor:
                reasons.append("explicit actor match")
            else:
                unknown = True
                reasons.append("actor information insufficient")

        threshold = self._explicit_threshold(requirement, text)
        if threshold is not None:
            quantity = self._context_quantity(context, threshold["unit"])
            if quantity is None:
                unknown = True
                reasons.append("threshold information insufficient")
            elif not self._threshold_satisfied(threshold["operator"], quantity, threshold["value"]):
                mismatch = True
                reasons.append("threshold not met")
            else:
                reasons.append("matched threshold")

        if unknown and not mismatch and not any(reason.startswith("matched ") for reason in reasons):
            reasons.append("insufficient context")
        if not reasons:
            unknown = True
            reasons.append("insufficient context")

        outcome = "not_applicable" if mismatch else "unknown" if unknown else "applicable"
        return {
            "id": uuid5(NAMESPACE_URL, f"{context.tenant_id}:{requirement['id']}:{fingerprint}"),
            "tenant_id": context.tenant_id,
            "requirement_id": requirement["id"],
            "context_fingerprint": fingerprint,
            "outcome": outcome,
            "reason": "; ".join(reasons),
            "context": self._context_payload(context),
            "status": "evaluated",
        }

    def evaluate_and_persist(
        self,
        requirement: dict[str, Any],
        context: ApplicabilityContext,
    ) -> dict[str, Any]:
        result = self.evaluate(requirement, context)
        if self._repository is None:
            return result
        existing = self._repository.get_by_identity(
            context.tenant_id,
            requirement["id"],
            result["context_fingerprint"],
        )
        return existing if existing is not None else self._repository.create(**result)

    @staticmethod
    def _validate_requirement(requirement: dict[str, Any]) -> None:
        if not isinstance(requirement, dict) or not requirement.get("id"):
            raise RegulatoryRequirementApplicabilityValidationError(
                "requirement with id is required"
            )
        if not isinstance(requirement.get("requirement_text"), str) or not requirement["requirement_text"].strip():
            raise RegulatoryRequirementApplicabilityValidationError(
                "requirement_text is required"
            )

    @classmethod
    def context_fingerprint(cls, context: ApplicabilityContext) -> str:
        payload = cls._context_payload(context)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _context_payload(context: ApplicabilityContext) -> dict[str, Any]:
        return asdict(context)

    @classmethod
    def _explicit_destinations(cls, text: str, requirement: dict[str, Any]) -> set[str]:
        values = {cls._country(match.group(0)) for match in cls.COUNTRY_PATTERN.finditer(text)}
        condition = requirement.get("condition_metadata") or {}
        if isinstance(condition, dict):
            values.update(
                cls._country(match.group(0))
                for match in cls.COUNTRY_PATTERN.finditer(str(condition.get("condition") or ""))
            )
        return {value for value in values if value}

    @classmethod
    def _explicit_commodities(cls, text: str) -> set[str]:
        return {cls._normalize_value(match.group(0)) for match in cls.COMMODITY_PATTERN.finditer(text)}

    @classmethod
    def _explicit_threshold(cls, requirement: dict[str, Any], text: str) -> dict[str, Any] | None:
        metadata = requirement.get("condition_metadata") or {}
        candidate = metadata.get("threshold") if isinstance(metadata, dict) else None
        match = cls.THRESHOLD_PATTERN.search(str(candidate or text))
        if match is None:
            return None
        operator = match.group(1).lower().replace("  ", " ")
        return {
            "operator": operator,
            "value": float(match.group("value")),
            "unit": match.group("unit").lower(),
        }

    @staticmethod
    def _context_quantity(context: ApplicabilityContext, unit: str) -> float | None:
        characteristics = context.business_characteristics or {}
        value = characteristics.get("shipment_quantity_tonnes") if unit.startswith("ton") or unit == "t" else characteristics.get("shipment_quantity_kg")
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _threshold_satisfied(operator: str, actual: float, expected: float) -> bool:
        if operator in {"at least", "no less than", "not less than", "greater than"}:
            return actual >= expected if operator != "greater than" else actual > expected
        if operator in {"at most", "no more than", "not more than", "less than"}:
            return actual <= expected if operator != "less than" else actual < expected
        return False

    @classmethod
    def _country(cls, value: str | None) -> str | None:
        normalized = cls._normalize_value(value)
        return cls.COUNTRY_ALIASES.get(normalized, normalized if len(normalized) == 2 else None)

    @staticmethod
    def _normalize_value(value: str | None) -> str:
        return " ".join(str(value or "").strip().lower().split())


@dataclass(frozen=True)
class EvidenceRecord:
    """Tenant-owned evidence reference reused by the assessment boundary."""

    tenant_id: UUID
    evidence_id: UUID
    evidence_type: str
    reference: str
    requirement_id: UUID | None = None
    status: str = "uploaded"
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, UUID) or not isinstance(self.evidence_id, UUID):
            raise RequirementAssessmentValidationError("evidence tenant_id and evidence_id are required")
        if not self.evidence_type.strip() or not self.reference.strip():
            raise RequirementAssessmentValidationError("evidence type and reference are required")


class RequirementAssessmentService:
    """Assess an applicable requirement against explicit tenant evidence only."""

    ACCEPTED_STATUSES = {"accepted", "reviewed"}

    def __init__(self, repository: Any | None = None) -> None:
        self._repository = repository

    def assess(
        self,
        applicability_result: dict[str, Any],
        evidence: list[EvidenceRecord],
    ) -> dict[str, Any]:
        self._validate_applicability(applicability_result)
        tenant_id = applicability_result["tenant_id"]
        requirement_id = applicability_result["requirement_id"]
        for record in evidence:
            if not isinstance(record, EvidenceRecord):
                raise RequirementAssessmentValidationError("evidence must contain EvidenceRecord values")
            if record.tenant_id != tenant_id:
                raise RequirementAssessmentValidationError("evidence belongs to a different tenant")

        evidence_fingerprint = self.evidence_fingerprint(evidence)
        linked = [record for record in evidence if record.requirement_id == requirement_id]
        supporting = [
            record for record in linked
            if record.status in self.ACCEPTED_STATUSES
            and bool((record.metadata or {}).get("supports_requirement"))
        ]
        rejected = [record for record in linked if record.status in {"rejected", "archived"}]

        if applicability_result["outcome"] != "applicable":
            outcome = "unknown"
            reason = "requirement cannot yet be assessed"
            selected = None
        elif supporting:
            outcome = "satisfied"
            reason = "required evidence present"
            selected = supporting[0]
        elif rejected:
            outcome = "not_satisfied"
            reason = "evidence rejected"
            selected = rejected[0]
        elif linked:
            outcome = "unknown"
            reason = "evidence insufficient"
            selected = linked[0]
        elif evidence:
            outcome = "unknown"
            reason = "evidence insufficient"
            selected = evidence[0]
        else:
            outcome = "unknown"
            reason = "required evidence absent"
            selected = None

        return {
            "id": uuid5(
                NAMESPACE_URL,
                f"{tenant_id}:{requirement_id}:{applicability_result['id']}:{evidence_fingerprint}",
            ),
            "tenant_id": tenant_id,
            "requirement_id": requirement_id,
            "applicability_result_id": applicability_result["id"],
            "evidence_fingerprint": evidence_fingerprint,
            "evidence_id": selected.evidence_id if selected else None,
            "evidence_ids": [record.evidence_id for record in linked],
            "outcome": outcome,
            "reason": reason,
            "status": "assessed",
        }

    def assess_and_persist(
        self,
        applicability_result: dict[str, Any],
        evidence: list[EvidenceRecord],
    ) -> dict[str, Any]:
        result = self.assess(applicability_result, evidence)
        if self._repository is None:
            return result
        existing = self._repository.get_by_identity(
            result["tenant_id"],
            result["requirement_id"],
            result["applicability_result_id"],
            result["evidence_fingerprint"],
        )
        return existing if existing is not None else self._repository.create(**result)

    @staticmethod
    def _validate_applicability(result: dict[str, Any]) -> None:
        required = ("id", "tenant_id", "requirement_id", "outcome")
        if not isinstance(result, dict) or any(not result.get(field) for field in required):
            raise RequirementAssessmentValidationError(
                "applicability result must include id, tenant_id, requirement_id, and outcome"
            )
        if not isinstance(result["tenant_id"], UUID) or not isinstance(result["requirement_id"], UUID):
            raise RequirementAssessmentValidationError("applicability identifiers must be UUID values")
        if result["outcome"] not in {"applicable", "not_applicable", "unknown"}:
            raise RequirementAssessmentValidationError("invalid applicability outcome")

    @staticmethod
    def evidence_fingerprint(evidence: list[EvidenceRecord]) -> str:
        payload = [
            {
                "evidence_id": record.evidence_id,
                "requirement_id": record.requirement_id,
                "status": record.status,
                "metadata": record.metadata or {},
            }
            for record in sorted(evidence, key=lambda value: str(value.evidence_id))
        ]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ComplianceCaseService:
    """Compose existing tenant-scoped applicability, assessment, and evidence records."""

    def build(
        self,
        applicability_result: dict[str, Any],
        requirement: dict[str, Any],
        assessment: dict[str, Any] | None,
        evidence: list[EvidenceRecord],
        *,
        regulatory_source: dict[str, Any] | None = None,
        document_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_applicability(applicability_result)
        requirement_id = requirement.get("id") if isinstance(requirement, dict) else None
        if not requirement_id or requirement_id != applicability_result["requirement_id"]:
            raise ComplianceCaseValidationError("requirement does not match applicability result")
        if not isinstance(requirement.get("requirement_text"), str) or not requirement["requirement_text"].strip():
            raise ComplianceCaseValidationError("requirement_text is required")

        tenant_id = applicability_result["tenant_id"]
        self._validate_assessment(assessment, tenant_id, requirement_id, applicability_result["id"])
        linked_evidence: list[dict[str, Any]] = []
        for record in evidence:
            if not isinstance(record, EvidenceRecord):
                raise ComplianceCaseValidationError("evidence must contain EvidenceRecord values")
            if record.tenant_id != tenant_id:
                raise ComplianceCaseValidationError("evidence belongs to a different tenant")
            if record.requirement_id == requirement_id:
                linked_evidence.append(self._evidence_view(record))

        applicability_view = {
            "id": applicability_result["id"],
            "outcome": applicability_result["outcome"],
            "reason": applicability_result.get("reason"),
            "context_fingerprint": applicability_result.get("context_fingerprint"),
            "context": applicability_result.get("context"),
            "status": applicability_result.get("status"),
        }
        if applicability_result["outcome"] == "applicable" and assessment is not None:
            assessment_view = self._assessment_view(assessment)
        else:
            assessment_view = {
                "id": assessment.get("id") if assessment else None,
                "outcome": "unknown",
                "reason": "requirement cannot yet be assessed",
                "evidence_id": None,
                "evidence_ids": [],
                "status": assessment.get("status") if assessment else None,
            }

        source_view = regulatory_source or requirement.get("regulatory_source") or {
            "id": requirement.get("source_id")
        }
        document_view = document_metadata or requirement.get("document_metadata") or {
            "id": requirement.get("normalized_document_id")
        }
        evidence_ids = [record["evidence_id"] for record in linked_evidence]
        case_identity = (
            f"{tenant_id}:{applicability_result['id']}:{assessment_view['id']}:{evidence_ids}"
        )
        return {
            "id": uuid5(NAMESPACE_URL, case_identity),
            "tenant_id": tenant_id,
            "context": applicability_result.get("context"),
            "context_fingerprint": applicability_result.get("context_fingerprint"),
            "requirement": {
                "id": requirement_id,
                "text": requirement["requirement_text"],
                "type": requirement.get("requirement_type"),
                "source_location": requirement.get("source_location"),
            },
            "applicability": applicability_view,
            "assessment": assessment_view,
            "evidence": linked_evidence,
            "regulatory_source": source_view,
            "document_metadata": document_view,
            "provenance": {
                "assessment_id": assessment_view["id"],
                "applicability_result_id": applicability_result["id"],
                "requirement_id": requirement_id,
                "normalized_document_id": requirement.get("normalized_document_id"),
                "artifact_id": requirement.get("artifact_id"),
                "source_id": requirement.get("source_id"),
            },
            "created_at": (assessment or {}).get("created_at") or applicability_result.get("created_at"),
            "status": "read_only",
        }

    @staticmethod
    def _validate_applicability(result: dict[str, Any]) -> None:
        required = ("id", "tenant_id", "requirement_id", "outcome")
        if not isinstance(result, dict) or any(not result.get(field) for field in required):
            raise ComplianceCaseValidationError("invalid applicability result")
        if result["outcome"] not in {"applicable", "not_applicable", "unknown"}:
            raise ComplianceCaseValidationError("invalid applicability outcome")

    @staticmethod
    def _validate_assessment(
        assessment: dict[str, Any] | None,
        tenant_id: UUID,
        requirement_id: UUID,
        applicability_id: UUID,
    ) -> None:
        if assessment is None:
            return
        if (
            assessment.get("tenant_id") != tenant_id
            or assessment.get("requirement_id") != requirement_id
            or assessment.get("applicability_result_id") != applicability_id
        ):
            raise ComplianceCaseValidationError("assessment does not match tenant case context")
        if assessment.get("outcome") not in {"satisfied", "not_satisfied", "unknown"}:
            raise ComplianceCaseValidationError("invalid assessment outcome")

    @staticmethod
    def _assessment_view(assessment: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": assessment.get("id"),
            "outcome": assessment["outcome"],
            "reason": assessment.get("reason"),
            "evidence_id": assessment.get("evidence_id"),
            "evidence_ids": assessment.get("evidence_ids", []),
            "status": assessment.get("status"),
        }

    @staticmethod
    def _evidence_view(record: EvidenceRecord) -> dict[str, Any]:
        return {
            "evidence_id": record.evidence_id,
            "evidence_type": record.evidence_type,
            "reference": record.reference,
            "status": record.status,
            "metadata": record.metadata or {},
        }


class ComplianceSummaryService:
    """Summarize existing compliance cases without adding a verdict or ranking."""

    def summarize(
        self,
        cases: list[dict[str, Any]],
        *,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        validated = [self._validate_case(case, tenant_id) for case in cases]
        ordered = sorted(validated, key=lambda case: str(case["requirement"]["id"]))
        applicable = [case for case in ordered if case["applicability"]["outcome"] == "applicable"]
        satisfied = [case for case in applicable if case["assessment"]["outcome"] == "satisfied"]
        not_satisfied = [case for case in applicable if case["assessment"]["outcome"] == "not_satisfied"]
        unknown_applicability = [case for case in ordered if case["applicability"]["outcome"] == "unknown"]
        unknown_assessment = [case for case in applicable if case["assessment"]["outcome"] == "unknown"]
        review_cases = unknown_applicability + unknown_assessment
        missing_evidence = [
            case for case in unknown_assessment
            if case["assessment"].get("reason") == "required evidence absent"
            or not case.get("evidence")
        ]

        affected = sorted(
            [*not_satisfied, *review_cases],
            key=lambda case: str(case["requirement"]["id"]),
        )
        return {
            "tenant_id": tenant_id,
            "total_cases": len(ordered),
            "total_applicable_requirements": len(applicable),
            "satisfied_requirements": len(satisfied),
            "not_satisfied_requirements": len(not_satisfied),
            "unknown_requirements": len(review_cases),
            "requirements_missing_evidence": len(missing_evidence),
            "requirements_requiring_review": len(review_cases),
            "affected_requirements": [self._affected_view(case) for case in affected],
            "missing_evidence_requirements": [self._affected_view(case) for case in missing_evidence],
            "status": "summary",
        }

    @staticmethod
    def _validate_case(case: dict[str, Any], tenant_id: UUID) -> dict[str, Any]:
        if not isinstance(case, dict) or case.get("tenant_id") != tenant_id:
            raise ComplianceSummaryValidationError("case belongs to a different tenant or is invalid")
        requirement = case.get("requirement")
        applicability = case.get("applicability")
        assessment = case.get("assessment")
        if not isinstance(requirement, dict) or not requirement.get("id"):
            raise ComplianceSummaryValidationError("case requirement is required")
        if not isinstance(applicability, dict) or applicability.get("outcome") not in {
            "applicable", "not_applicable", "unknown",
        }:
            raise ComplianceSummaryValidationError("case applicability is invalid")
        if not isinstance(assessment, dict) or assessment.get("outcome") not in {
            "satisfied", "not_satisfied", "unknown",
        }:
            raise ComplianceSummaryValidationError("case assessment is invalid")
        return case

    @staticmethod
    def _affected_view(case: dict[str, Any]) -> dict[str, Any]:
        applicability = case["applicability"]
        assessment = case["assessment"]
        if applicability["outcome"] == "unknown":
            state = "unknown"
            reason = applicability.get("reason")
        else:
            state = assessment["outcome"]
            reason = assessment.get("reason")
        return {
            "requirement_id": case["requirement"]["id"],
            "requirement_text": case["requirement"].get("text"),
            "state": state,
            "reason": reason,
            "regulatory_source": case.get("regulatory_source"),
            "document_metadata": case.get("document_metadata"),
            "provenance": case.get("provenance"),
        }


class ComplianceApplicabilityService:
    """Deterministic batch applicability determination for an export case.

    Evaluates a set of compliance requirements against a single
    ApplicabilityContext and produces a structured report that preserves
    the distinction between applicable, not_applicable, and unknown.
    """

    def __init__(
        self,
        applicability_service: RegulatoryRequirementApplicabilityService | None = None,
    ) -> None:
        self._applicability = (
            applicability_service or RegulatoryRequirementApplicabilityService()
        )

    def determine(
        self,
        requirements: list[dict[str, Any]],
        context: ApplicabilityContext,
    ) -> dict[str, Any]:
        if not requirements:
            raise ComplianceSummaryValidationError("requirements list is required")
        if not isinstance(context, ApplicabilityContext):
            raise ComplianceSummaryValidationError("ApplicabilityContext is required")

        results = [
            self._applicability.evaluate(requirement, context)
            for requirement in requirements
        ]

        applicable = [r for r in results if r["outcome"] == "applicable"]
        not_applicable = [r for r in results if r["outcome"] == "not_applicable"]
        unknown = [r for r in results if r["outcome"] == "unknown"]

        return {
            "tenant_id": context.tenant_id,
            "context_fingerprint": context_fingerprint(context),
            "total_requirements": len(requirements),
            "applicable_count": len(applicable),
            "not_applicable_count": len(not_applicable),
            "unknown_count": len(unknown),
            "results": results,
            "status": "determined",
        }


class ApplicabilityContextBuilder:
    """Build an ApplicabilityContext from existing Xportra domain data.

    Translates exporter, product, and destination facts into the minimal
    tenant-owned context required by deterministic applicability rules.

    Missing facts are left as None rather than invented. The resulting
    ApplicabilityContext preserves the distinction between known and unknown.
    """

    def build(
        self,
        *,
        tenant_id: UUID,
        exporter: dict[str, Any] | None = None,
        product: dict[str, Any] | None = None,
        destination: dict[str, Any] | None = None,
        actor_role: str | None = None,
        business_characteristics: dict[str, Any] | None = None,
    ) -> ApplicabilityContext:
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        return ApplicabilityContext(
            tenant_id=tenant_id,
            exporter_id=self._uuid(exporter, "id"),
            exporter_name=self._exporter_name(exporter),
            origin_country=self._value(exporter, "country_of_registration"),
            destination_country=self._value(destination, "country_code"),
            commodity=self._value(product, "commodity_code"),
            product_category=self._value(product, "description"),
            business_characteristics=business_characteristics,
            actor_role=actor_role or "exporter",
        )

    @staticmethod
    def _value(data: dict[str, Any] | None, key: str) -> str | None:
        if not isinstance(data, dict):
            return None
        value = data.get(key)
        return str(value).strip() if value is not None and str(value).strip() else None

    @staticmethod
    def _uuid(data: dict[str, Any] | None, key: str) -> UUID | None:
        if not isinstance(data, dict):
            return None
        value = data.get(key)
        if isinstance(value, UUID):
            return value
        return None

    @staticmethod
    def _exporter_name(exporter: dict[str, Any] | None) -> str | None:
        if not isinstance(exporter, dict):
            return None
        name = exporter.get("legal_name") or exporter.get("trading_name")
        return str(name).strip() if name is not None and str(name).strip() else None


def context_fingerprint(context: ApplicabilityContext) -> str:
    """Compute a deterministic fingerprint for an ApplicabilityContext."""
    payload = RegulatoryRequirementApplicabilityService._context_payload(context)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ApplicabilityToRiskIntegration:
    """Deterministic boundary between applicability reports and risk classification.

    Converts an applicability report produced by ComplianceApplicabilityService
    into the case format expected by ComplianceRiskService, preserving all
    applicability outcomes and tenant identity.

    Unknown applicability is preserved as unknown — it is never silently treated
    as applicable or not_applicable. Not-applicable requirements are excluded
    from risk classification per existing risk-service semantics.
    """

    def __init__(self, risk_service: ComplianceRiskService | None = None) -> None:
        self._risk_service = risk_service or ComplianceRiskService()

    def classify_from_applicability(
        self,
        applicability_report: dict[str, Any],
        *,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        if not isinstance(applicability_report, dict):
            raise ComplianceSummaryValidationError("applicability_report is required")
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        report_tenant = applicability_report.get("tenant_id")
        if report_tenant != tenant_id:
            raise ComplianceSummaryValidationError(
                "applicability report belongs to a different tenant"
            )

        cases = self._build_cases(applicability_report, tenant_id)
        return self._risk_service.classify(cases, tenant_id=tenant_id)

    def _build_cases(
        self,
        report: dict[str, Any],
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        results = report.get("results", [])
        cases = []
        for result in results:
            outcome = result.get("outcome")
            if outcome not in {"applicable", "not_applicable", "unknown"}:
                continue

            requirement = result.get("requirement")
            requirement = requirement if isinstance(requirement, dict) else {}
            req_id = result.get("requirement_id") or requirement.get("id")
            if not req_id:
                continue

            case = {
                "tenant_id": tenant_id,
                "requirement": {
                    "id": req_id,
                    "text": requirement.get("text"),
                    "type": requirement.get("type"),
                },
                "applicability": {
                    "outcome": outcome,
                    "reason": result.get("reason", "determined"),
                },
                "assessment": {
                    "outcome": "unknown",
                    "reason": "assessment not yet performed",
                },
                "evidence": [],
                "context_fingerprint": report.get("context_fingerprint"),
            }
            cases.append(case)
        return cases



class ComplianceRiskService:
    """Deterministic risk/priority layer over existing compliance cases.

    Classifies applicable requirements into attention levels based only on
    existing case state. Does not change underlying regulatory, applicability,
    or assessment outcomes.
    """

    def classify(
        self,
        cases: list[dict[str, Any]],
        *,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        validated = [self._validate_case(case, tenant_id) for case in cases]
        applicable = [
            case for case in validated
            if case["applicability"]["outcome"] == "applicable"
        ]
        reviewed = self._classify_applicable(applicable)
        return reviewed

    @staticmethod
    def _is_missing_evidence(case: dict[str, Any]) -> bool:
        assessment = case.get("assessment", {})
        evidence = case.get("evidence")
        reason = assessment.get("reason", "")
        return (
            reason == "required evidence absent"
            or not evidence
        )

    def _classify_applicable(self, applicable_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        reviewed = []
        for case in applicable_cases:
            outcome = case["assessment"]["outcome"]
            reason = case["assessment"].get("reason", "")
            missing = self._is_missing_evidence(case)

            if outcome == "not_satisfied":
                state = "high"
                explanation = "not_satisfied assessment"
            elif outcome == "satisfied":
                state = "low"
                explanation = "satisfied assessment"
            elif outcome == "unknown":
                if missing:
                    state = "medium"
                    explanation = "unknown with missing required evidence"
                else:
                    state = "unknown"
                    explanation = "unknown without sufficient evidence"
            else:
                continue  # not_applicable or other - exclude

            reviewed.append({
                "requirement_id": case["requirement"]["id"],
                "requirement_text": case["requirement"].get("text"),
                "state": state,
                "explanation": explanation,
                "regulatory_source": case.get("regulatory_source"),
                "document_metadata": case.get("document_metadata"),
                "provenance": case.get("provenance"),
            })
        return reviewed

    @staticmethod
    def _validate_case(case: dict[str, Any], tenant_id: UUID) -> dict[str, Any]:
        if not isinstance(case, dict) or case.get("tenant_id") != tenant_id:
            raise ComplianceSummaryValidationError(
                "case belongs to a different tenant or is invalid"
            )
        requirement = case.get("requirement")
        applicability = case.get("applicability")
        assessment = case.get("assessment")
        if not isinstance(requirement, dict) or not requirement.get("id"):
            raise ComplianceSummaryValidationError("case requirement is required")
        if not isinstance(applicability, dict) or applicability.get("outcome") not in {
            "applicable", "not_applicable", "unknown",
        }:
            raise ComplianceSummaryValidationError("case applicability is invalid")
        if not isinstance(assessment, dict) or assessment.get("outcome") not in {
            "satisfied", "not_satisfied", "unknown",
        }:
            raise ComplianceSummaryValidationError("case assessment is invalid")
        return case


class ComplianceActionRecommendationService:
    """Recommend deterministic exporter next actions from existing case state."""

    def __init__(self, risk_service: ComplianceRiskService | None = None) -> None:
        self._risk_service = risk_service or ComplianceRiskService()

    def recommend(
        self,
        cases: list[dict[str, Any]],
        *,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        ordered = sorted(
            [ComplianceRiskService._validate_case(case, tenant_id) for case in cases],
            key=lambda case: str(case["requirement"]["id"]),
        )
        recommendations: list[dict[str, Any]] = []
        for case in ordered:
            applicability = case["applicability"]["outcome"]
            assessment = case["assessment"]["outcome"]

            if applicability == "not_applicable":
                continue

            if assessment == "not_satisfied":
                action_type = "address_requirement"
                explanation = "assessment not_satisfied; address requirement"
            elif assessment == "satisfied":
                action_type = "no_action_required"
                explanation = "assessment satisfied; no action required"
            elif applicability == "unknown":
                action_type = "review_requirement"
                explanation = "applicability unknown; review requirement"
            elif self._is_missing_evidence(case):
                action_type = "provide_missing_evidence"
                explanation = (
                    "assessment unknown with missing required evidence; provide missing evidence"
                )
            else:
                action_type = "review_requirement"
                explanation = "assessment unknown without sufficient evidence; review requirement"

            recommendations.append(
                {
                    "tenant_id": case["tenant_id"],
                    "context": case.get("context"),
                    "context_fingerprint": case.get("context_fingerprint"),
                    "requirement_id": case["requirement"]["id"],
                    "requirement_text": case["requirement"].get("text"),
                    "action_type": action_type,
                    "explanation": explanation,
                    "risk_state": self._risk_state(case, tenant_id),
                    "regulatory_source": case.get("regulatory_source"),
                    "document_metadata": case.get("document_metadata"),
                    "provenance": case.get("provenance"),
                    "status": "recommendation",
                }
            )
        return recommendations

    def _risk_state(self, case: dict[str, Any], tenant_id: UUID) -> str | None:
        classified = self._risk_service.classify([case], tenant_id=tenant_id)
        return classified[0]["state"] if classified else None

    @staticmethod
    def _is_missing_evidence(case: dict[str, Any]) -> bool:
        assessment = case.get("assessment", {})
        return assessment.get("reason") == "required evidence absent" or not case.get("evidence")


class RiskToActionIntegration:
    """Deterministic boundary between risk classification and action recommendations.

    Connects the risk classification output from Phase 3.3 to the action
    recommendation service from Phase 3.0, completing the end-to-end domain pipeline:

    Applicability → Risk → Action

    This integration preserves all risk state information and delegates
    all action recommendation logic to ComplianceActionRecommendationService.
    Unknown/insufficient states are preserved — never silently converted.
    """

    def __init__(
        self,
        action_service: ComplianceActionRecommendationService | None = None,
    ) -> None:
        self._action_service = action_service or ComplianceActionRecommendationService()

    def recommend_from_risk(
        self,
        risk_classified_cases: list[dict[str, Any]],
        *,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """Convert risk-classified results to action recommendations.

        Args:
            risk_classified_cases: Output from ApplicabilityToRiskIntegration or
                                  ComplianceRiskService.classify()
            tenant_id: Tenant identity for isolation

        Returns:
            List of action recommendations from ComplianceActionRecommendationService

        Raises:
            ComplianceSummaryValidationError: If inputs are invalid
        """
        if not isinstance(risk_classified_cases, list):
            raise ComplianceSummaryValidationError(
                "risk_classified_cases must be a list"
            )
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        return self._action_service.recommend(
            risk_classified_cases, tenant_id=tenant_id
        )

    def full_pipeline(
        self,
        applicability_report: dict[str, Any],
        *,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Execute complete Applicability → Risk → Action pipeline.

        Convenience method that runs the entire deterministic domain flow
        in a single call, returning both intermediate and final results.

        Args:
            applicability_report: Output from ComplianceApplicabilityService.determine()
            tenant_id: Tenant identity for isolation

        Returns:
            Dictionary containing:
            - risk_results: From ApplicabilityToRiskIntegration
            - action_recommendations: From ComplianceActionRecommendationService
            - pipeline_metadata: Tenant ID, counts, status
        """
        from xportra.domain.ingestion import ApplicabilityToRiskIntegration

        if not isinstance(applicability_report, dict):
            raise ComplianceSummaryValidationError("applicability_report is required")
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        # Phase 3.3: Applicability → Risk
        risk_integration = ApplicabilityToRiskIntegration()
        risk_results = risk_integration.classify_from_applicability(
            applicability_report, tenant_id=tenant_id
        )

        # Phase 3.4: Risk → Action
        # Rebuild cases from risk results for action service
        cases_for_action = self._rebuild_cases_from_risk(
            risk_results, applicability_report, tenant_id
        )
        action_recommendations = self.recommend_from_risk(
            cases_for_action, tenant_id=tenant_id
        )

        return {
            "risk_results": risk_results,
            "action_recommendations": action_recommendations,
            "pipeline_metadata": {
                "tenant_id": tenant_id,
                "total_risk_classified": len(risk_results),
                "total_actions": len(action_recommendations),
                "status": "complete",
            },
        }

    def _rebuild_cases_from_risk(
        self,
        risk_results: list[dict[str, Any]],
        original_report: dict[str, Any],
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """Reconstruct full cases from risk results for action service input.

        The action service needs the full case structure (applicability, assessment,
        evidence), but risk results only contain summary fields. This method
        reconstructs cases by merging risk results with original report data.
        """
        # Build lookup from requirement ID to original result
        original_results = original_report.get("results", [])
        result_lookup = {}
        for result in original_results:
            requirement = result.get("requirement")
            requirement = requirement if isinstance(requirement, dict) else {}
            req_id = result.get("requirement_id") or requirement.get("id")
            if req_id:
                result_lookup[req_id] = result

        cases = []
        for risk_result in risk_results:
            req_id = risk_result.get("requirement_id")
            if not req_id:
                continue

            # Find original result for this requirement
            original = result_lookup.get(req_id, {})
            requirement = original.get("requirement")
            requirement = requirement if isinstance(requirement, dict) else {}

            case = {
                "tenant_id": tenant_id,
                "context": original.get("context", {}),
                "context_fingerprint": original_report.get("context_fingerprint"),
                "requirement": {
                    "id": req_id,
                    "text": requirement.get("text"),
                    "type": requirement.get("type"),
                },
                "applicability": {
                    "outcome": original.get("outcome", "applicable"),
                    "reason": original.get("reason", "determined"),
                },
                "assessment": {
                    "outcome": "unknown",
                    "reason": "assessment not yet performed",
                },
                "evidence": [],
                "regulatory_source": original.get("regulatory_source"),
                "document_metadata": original.get("document_metadata"),
                "provenance": original.get("provenance"),
            }
            cases.append(case)

        return cases
    

class ComplianceDecisionSummaryService:
    """Deterministic representation boundary for the compliance decision summary.

    Condenses the existing Applicability -> Risk -> Action outputs into a single
    structured, tenant-scoped representation for future application/API layers:

    Applicability -> Risk -> Action -> Summary

    This boundary decides nothing. Applicability determination, risk
    classification, and action recommendation remain owned by their existing
    services; this service only joins what those services already produced,
    preserves unknown/insufficient states explicitly, and orders every section
    deterministically. It performs no persistence, no external calls, and no
    retrieval, RAG, LLM, embedding, or vector work.
    """

    def __init__(
        self,
        risk_service: ComplianceRiskService | None = None,
        risk_to_action: RiskToActionIntegration | None = None,
    ) -> None:
        self._risk_service = risk_service or ComplianceRiskService()
        self._risk_to_action = risk_to_action or RiskToActionIntegration()

    def summarize(
        self,
        cases: list[dict[str, Any]],
        *,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Summarize existing compliance cases into a decision summary.

        Args:
            cases: Existing compliance cases (applicability, assessment,
                   evidence), as consumed by ComplianceRiskService
            tenant_id: Tenant identity for isolation

        Returns:
            Structured decision summary derived only from existing service outputs

        Raises:
            ComplianceSummaryValidationError: If inputs are invalid or cross tenants
        """
        if not isinstance(cases, list):
            raise ComplianceSummaryValidationError("cases must be a list")
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        risk_results = self._risk_service.classify(cases, tenant_id=tenant_id)
        actions = self._risk_to_action.recommend_from_risk(cases, tenant_id=tenant_id)
        ordered_cases = sorted(cases, key=lambda case: str(case["requirement"]["id"]))
        views = [self._view_from_case(case) for case in ordered_cases]

        return self._compose(
            tenant_id=tenant_id,
            context_fingerprint=self._first_fingerprint(ordered_cases),
            applicability=self._applicability_section(
                [
                    {
                        "requirement_id": view["requirement_id"],
                        "requirement_text": view["requirement_text"],
                        "outcome": view["applicability_outcome"],
                        "reason": view["applicability_reason"],
                    }
                    for view in views
                ]
            ),
            requirement_views=views,
            risk_results=risk_results,
            actions=actions,
        )

    def summarize_from_applicability(
        self,
        applicability_report: dict[str, Any],
        *,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Summarize an applicability report by running the existing pipeline.

        Args:
            applicability_report: Output of ComplianceApplicabilityService.determine()
            tenant_id: Tenant identity for isolation

        Returns:
            Structured decision summary; risk and action sections come from the
            existing Phase 3.3/3.4 pipeline and applicability from the report
            itself. A report carries no assessment or evidence, so those fields
            stay None rather than being assumed.

        Raises:
            ComplianceSummaryValidationError: If inputs are invalid or cross tenants
        """
        if not isinstance(applicability_report, dict):
            raise ComplianceSummaryValidationError("applicability_report is required")
        if not isinstance(tenant_id, UUID):
            raise ComplianceSummaryValidationError("tenant_id is required")

        pipeline = self._risk_to_action.full_pipeline(
            applicability_report, tenant_id=tenant_id
        )
        applicability_results = self._applicability_results_from_report(
            applicability_report
        )
        views = [
            {
                "requirement_id": result["requirement_id"],
                "requirement_text": result["requirement_text"],
                "applicability_outcome": result["outcome"],
                "applicability_reason": result["reason"],
                "assessment_outcome": None,
                "assessment_reason": None,
                "evidence_present": None,
            }
            for result in applicability_results
        ]

        return self._compose(
            tenant_id=tenant_id,
            context_fingerprint=applicability_report.get("context_fingerprint"),
            applicability=self._applicability_section(applicability_results),
            requirement_views=views,
            risk_results=pipeline["risk_results"],
            actions=pipeline["action_recommendations"],
        )

    @staticmethod
    def _view_from_case(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "requirement_id": case["requirement"]["id"],
            "requirement_text": case["requirement"].get("text"),
            "applicability_outcome": case["applicability"]["outcome"],
            "applicability_reason": case["applicability"].get("reason"),
            "assessment_outcome": case["assessment"]["outcome"],
            "assessment_reason": case["assessment"].get("reason"),
            "evidence_present": bool(case.get("evidence")),
        }

    @staticmethod
    def _first_fingerprint(ordered_cases: list[dict[str, Any]]) -> str | None:
        for case in ordered_cases:
            fingerprint = case.get("context_fingerprint")
            if fingerprint:
                return fingerprint
        return None

    @staticmethod
    def _applicability_results_from_report(
        applicability_report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        results = []
        for result in applicability_report.get("results", []):
            if not isinstance(result, dict):
                continue
            requirement = result.get("requirement")
            requirement = requirement if isinstance(requirement, dict) else {}
            requirement_id = result.get("requirement_id") or requirement.get("id")
            outcome = result.get("outcome")
            if not requirement_id:
                continue
            if outcome not in {"applicable", "not_applicable", "unknown"}:
                continue
            results.append(
                {
                    "requirement_id": requirement_id,
                    "requirement_text": result.get("requirement_text")
                    or requirement.get("text"),
                    "outcome": outcome,
                    "reason": result.get("reason"),
                }
            )
        return results

    @classmethod
    def _applicability_section(cls, results: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(results, key=lambda result: str(result["requirement_id"]))
        counts = cls._counts([result["outcome"] for result in ordered])
        return {
            "total_requirements": len(ordered),
            "applicable_count": counts.get("applicable", 0),
            "not_applicable_count": counts.get("not_applicable", 0),
            "unknown_count": counts.get("unknown", 0),
            "results": ordered,
        }

    @staticmethod
    def _counts(values: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return {key: counts[key] for key in sorted(counts)}

    @classmethod
    def _compose(
        cls,
        *,
        tenant_id: UUID,
        context_fingerprint: str | None,
        applicability: dict[str, Any],
        requirement_views: list[dict[str, Any]],
        risk_results: list[dict[str, Any]],
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ordered_risk = sorted(
            risk_results, key=lambda result: str(result["requirement_id"])
        )
        ordered_actions = sorted(
            actions, key=lambda action: str(action["requirement_id"])
        )
        risk_by_requirement = {
            str(result["requirement_id"]): result for result in ordered_risk
        }
        action_by_requirement = {
            str(action["requirement_id"]): action for action in ordered_actions
        }

        views = []
        for view in sorted(
            requirement_views, key=lambda view: str(view["requirement_id"])
        ):
            key = str(view["requirement_id"])
            risk = risk_by_requirement.get(key)
            action = action_by_requirement.get(key)
            views.append(
                {
                    "requirement_id": view["requirement_id"],
                    "requirement_text": view["requirement_text"],
                    "applicability_outcome": view["applicability_outcome"],
                    "applicability_reason": view["applicability_reason"],
                    "assessment_outcome": view.get("assessment_outcome"),
                    "assessment_reason": view.get("assessment_reason"),
                    "evidence_present": view.get("evidence_present"),
                    "risk_state": risk["state"] if risk else None,
                    "action_type": action["action_type"] if action else None,
                }
            )

        return {
            "tenant_id": tenant_id,
            "context_fingerprint": context_fingerprint,
            "status": "decision_summary",
            "applicability": applicability,
            "risk": {
                "classified_count": len(ordered_risk),
                "by_state": cls._counts([result["state"] for result in ordered_risk]),
                "results": ordered_risk,
            },
            "actions": {
                "recommendation_count": len(ordered_actions),
                "by_type": cls._counts(
                    [action["action_type"] for action in ordered_actions]
                ),
                "results": ordered_actions,
            },
            "unknown_states": cls._unknown_states(views, risk_by_requirement),
            "requirements": views,
        }

    @staticmethod
    def _unknown_states(
        views: list[dict[str, Any]],
        risk_by_requirement: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """List every uncertainty observable from the supplied input.

        Kinds are descriptive labels for existing states only; they never change
        a decision. A source that carries no assessment or evidence (such as a
        pure applicability report) cannot produce those kinds.
        """
        unknown: list[dict[str, Any]] = []
        for view in views:
            requirement_id = view["requirement_id"]
            applicable = view["applicability_outcome"] == "applicable"
            assessment_unknown = view["assessment_outcome"] == "unknown"

            if view["applicability_outcome"] == "unknown":
                unknown.append(
                    {
                        "requirement_id": requirement_id,
                        "kind": "applicability_unknown",
                        "reason": view["applicability_reason"],
                    }
                )
            if applicable and assessment_unknown:
                unknown.append(
                    {
                        "requirement_id": requirement_id,
                        "kind": "assessment_unknown",
                        "reason": view["assessment_reason"],
                    }
                )
            # Mirror the existing services' missing-evidence semantics exactly:
            # empty evidence or the "required evidence absent" assessment reason.
            missing_evidence = view["evidence_present"] is False or (
                view["assessment_reason"] == "required evidence absent"
            )
            if applicable and assessment_unknown and missing_evidence:
                unknown.append(
                    {
                        "requirement_id": requirement_id,
                        "kind": "missing_evidence",
                        "reason": view["assessment_reason"],
                    }
                )
            risk = risk_by_requirement.get(str(requirement_id))
            if risk is not None and risk["state"] == "unknown":
                unknown.append(
                    {
                        "requirement_id": requirement_id,
                        "kind": "risk_unknown",
                        "reason": risk["explanation"],
                    }
                )
        return sorted(
            unknown, key=lambda item: (str(item["requirement_id"]), item["kind"])
        )



class SourceAcquisitionService:
    """Persist a registry-backed source artifact without allowing silent replacement.

    The source itself remains distinct from the acquired artifact; later phases can
    decide whether the artifact should be parsed, chunked, normalized, or indexed.
    """

    def __init__(self, source_repository: Any, artifact_repository: Any) -> None:
        self._sources = source_repository
        self._artifacts = artifact_repository

    def register_acquisition(
        self,
        *,
        source_id: UUID,
        artifact_uri: str,
        acquisition_channel: str,
        source_version: str | None = None,
        content_hash: str | None = None,
        content_length: int | None = None,
        content_type: str | None = None,
        acquired_by: str | None = None,
        validation_notes: str | None = None,
        status: str = "validated",
        acquired_at: datetime | None = None,
    ) -> dict[str, Any]:
        self._validate_source(source_id)
        self._validate_acquisition_payload(
            artifact_uri=artifact_uri,
            acquisition_channel=acquisition_channel,
            source_version=source_version,
            content_hash=content_hash,
            content_length=content_length,
            content_type=content_type,
            acquired_by=acquired_by,
        )

        hash_algorithm = self._hash_algorithm(content_hash)
        acquired = self._artifacts.create(
            source_id=source_id,
            artifact_uri=artifact_uri.strip(),
            content_hash=content_hash,
            hash_algorithm=hash_algorithm,
            content_type=content_type.strip() if content_type else None,
            content_length=content_length,
            acquisition_channel=acquisition_channel.strip(),
            acquired_at=acquired_at or datetime.now(timezone.utc),
            acquired_by=acquired_by.strip() if acquired_by else None,
            status=status,
            source_version=source_version.strip() if source_version else None,
            validation_notes=validation_notes.strip() if validation_notes else None,
        )
        return acquired

    def _validate_source(self, source_id: UUID) -> None:
        source = self._sources.get(source_id)
        if source is None:
            raise AcquisitionValidationError("source_id does not resolve to a known regulatory source")

    @staticmethod
    def _validate_acquisition_payload(
        *,
        artifact_uri: str,
        acquisition_channel: str,
        source_version: str | None,
        content_hash: str | None,
        content_length: int | None,
        content_type: str | None,
        acquired_by: str | None,
    ) -> None:
        if not artifact_uri or not artifact_uri.strip():
            raise AcquisitionValidationError("artifact_uri is required")
        if not acquisition_channel or not acquisition_channel.strip():
            raise AcquisitionValidationError("acquisition_channel is required")
        if not source_version or not source_version.strip():
            raise AcquisitionValidationError("source_version is required")
        if not content_hash or not content_hash.strip():
            raise AcquisitionValidationError("content_hash is required")
        if content_length is None or content_length <= 0:
            raise AcquisitionValidationError("content_length must be a positive integer")
        if not content_type or not content_type.strip():
            raise AcquisitionValidationError("content_type is required")
        if acquired_by is not None and not acquired_by.strip():
            raise AcquisitionValidationError("acquired_by cannot be blank")

    @staticmethod
    def _hash_algorithm(content_hash: str | None) -> str:
        if content_hash is None or not content_hash.strip():
            raise AcquisitionValidationError("content_hash is required")
        if content_hash.lower().startswith("sha256:"):
            return "sha256"
        return "sha256"