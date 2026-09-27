"""Conversational domain contracts (Phase 10.2, R-10.2.1).

Frozen value objects for the conversational backend boundary.
This module decides nothing, persists nothing, retrieves
nothing, and calls no provider. It owns the vocabulary that
keeps conversation state separate from compliance truth:

```text
conversation identity
    != compliance case identity
    != workflow identity
    != assessment result identity
```

A conversation may *reference* a shipment/workflow context, but
it never becomes the compliance record: transcripts are
operational data, and every shipment claim in a response cites
the authoritative identifier it was quoted from.

Identity rules enforced here (shape only — tenancy and access
are enforced by the application boundary on every use):

- Exactly one mode per conversation: ``shipment_aware`` (one
  explicitly pinned workflow context) or ``knowledge`` (no
  shipment context, structurally forbidden).
- Exactly one workflow per shipment-aware context; knowledge
  contexts carry no workflow, shipment, or case identity.
- Messages belong to exactly one conversation; roles are
  ``user`` / ``assistant`` only.
- Responses are ``grounded`` (every claim sourced),
  ``partial`` (sourced claims plus an explicit limitation), or
  ``refused_unknown`` (nothing established — never fabricated).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

#: Approved conversational modes (ADR-0009 §3, R-10.2.2).
CONVERSATION_MODE_SHIPMENT_AWARE = "shipment_aware"
CONVERSATION_MODE_KNOWLEDGE = "knowledge"
CONVERSATION_MODES = frozenset({
    CONVERSATION_MODE_SHIPMENT_AWARE,
    CONVERSATION_MODE_KNOWLEDGE,
})

#: Read-only intents. The request carries exactly one of these;
#: intents are never parsed from prose and no mutating intent
#: exists in this phase (R-10.2.4).
INTENT_EXPLAIN_REQUIREMENT_STATE = "explain_requirement_state"
INTENT_EXPLAIN_EVIDENCE_GAPS = "explain_evidence_gaps"
INTENT_EXPLAIN_FINDING = "explain_finding"
INTENT_SUMMARIZE_SHIPMENT_STATE = "summarize_shipment_state"
INTENT_ANSWER_REGULATORY_QUESTION = "answer_regulatory_question"
CONVERSATION_INTENTS = frozenset({
    INTENT_EXPLAIN_REQUIREMENT_STATE,
    INTENT_EXPLAIN_EVIDENCE_GAPS,
    INTENT_EXPLAIN_FINDING,
    INTENT_SUMMARIZE_SHIPMENT_STATE,
    INTENT_ANSWER_REGULATORY_QUESTION,
})
#: Intents that read deterministic shipment state and therefore
#: require ``shipment_aware`` mode. The regulatory intent is
#: allowed in both modes (retrieval-second in shipment mode,
#: retrieval-only in knowledge mode).
SHIPMENT_INTENTS = frozenset({
    INTENT_EXPLAIN_REQUIREMENT_STATE,
    INTENT_EXPLAIN_EVIDENCE_GAPS,
    INTENT_EXPLAIN_FINDING,
    INTENT_SUMMARIZE_SHIPMENT_STATE,
})

#: Message roles. Only user questions and assistant answers
#: exist; no system/tool role is expressible.
MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"
MESSAGE_ROLES = frozenset({MESSAGE_ROLE_USER, MESSAGE_ROLE_ASSISTANT})

#: Message types. The contract carries text questions and
#: answers only.
MESSAGE_TYPE_TEXT = "text"
MESSAGE_TYPES = frozenset({MESSAGE_TYPE_TEXT})

#: Response statuses (R-10.2.5).
RESPONSE_STATUS_GROUNDED = "grounded"
RESPONSE_STATUS_PARTIAL = "partial"
RESPONSE_STATUS_REFUSED_UNKNOWN = "refused_unknown"
RESPONSE_STATUSES = frozenset({
    RESPONSE_STATUS_GROUNDED,
    RESPONSE_STATUS_PARTIAL,
    RESPONSE_STATUS_REFUSED_UNKNOWN,
})

#: Shipment reference kinds — identifier citations only, never
#: content. The workflow kind names the pinned context; the
#: others name the quoted object.
SHIPMENT_CITATION_KINDS = frozenset({
    "workflow",
    "requirement",
    "evidence",
    "report",
    "analysis",
    "trace",
})

#: Domain-layer bound on user message text. The API applies its
#: own bound; this keeps the value object self-validating.
MAX_USER_MESSAGE_CHARACTERS = 2000

#: Fixed refusal wording. Unknown remains unknown: the system
#: states the limit instead of completing the answer.
UNKNOWN_REFUSAL_TEXT = (
    "The answer could not be established from authoritative "
    "shipment state or validated regulatory retrieval, so no "
    "answer is given rather than an unverified one."
)


def _require_uuid(value: object, field_name: str) -> UUID:
    if not isinstance(value, UUID):
        raise TypeError(f"{field_name} must be a UUID")
    return value


def _require_non_blank_text(value: object, field_name: str,
                             max_characters: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    if len(value) > max_characters:
        raise ValueError(
            f"{field_name} must be at most {max_characters} characters")
    return value


@dataclass(frozen=True, slots=True)
class ConversationIdentity:
    """Correlation identity for one conversation.

    This is NOT a record key: Phase 10.2 persists nothing, so
    the identity is validated for shape, echoed for
    correlation, and never dereferenced. It must never be
    confused with a compliance case, workflow, or assessment
    result identity.
    """

    conversation_id: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.conversation_id, "conversation_id")


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """Tenant-scoped, allow-listed context for one conversation.

    ``workflow_id`` pins exactly one workflow for
    ``shipment_aware`` mode; ``shipment_id`` optionally names the
    bound shipment. Knowledge mode carries neither — the shape
    itself makes silent shipment context impossible. Tenant
    binding is enforced by the application boundary, which never
    accepts tenant identity from the client.
    """

    conversation_id: UUID
    mode: str
    workflow_id: UUID | None = None
    shipment_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.conversation_id, "conversation_id")
        if self.mode not in CONVERSATION_MODES:
            raise ValueError(
                f"mode must be one of {sorted(CONVERSATION_MODES)}")
        if self.mode == CONVERSATION_MODE_KNOWLEDGE:
            if self.workflow_id is not None or self.shipment_id is not None:
                raise ValueError(
                    "knowledge mode must not carry shipment context")
        else:
            _require_uuid(self.workflow_id, "workflow_id")
            if self.shipment_id is not None:
                _require_uuid(self.shipment_id, "shipment_id")

    @property
    def is_shipment_aware(self) -> bool:
        return self.mode == CONVERSATION_MODE_SHIPMENT_AWARE


@dataclass(frozen=True, slots=True)
class UserMessage:
    """One user turn: exactly one conversation, one intent, text."""

    conversation_id: UUID
    role: str = MESSAGE_ROLE_USER
    message_type: str = MESSAGE_TYPE_TEXT
    content: str = ""
    intent: str = INTENT_ANSWER_REGULATORY_QUESTION

    def __post_init__(self) -> None:
        _require_uuid(self.conversation_id, "conversation_id")
        if self.role != MESSAGE_ROLE_USER:
            raise ValueError("user message role must be 'user'")
        if self.message_type not in MESSAGE_TYPES:
            raise ValueError(
                f"message_type must be one of {sorted(MESSAGE_TYPES)}")
        _require_non_blank_text(
            self.content, "content", MAX_USER_MESSAGE_CHARACTERS)
        if self.intent not in CONVERSATION_INTENTS:
            raise ValueError(
                f"intent must be one of {sorted(CONVERSATION_INTENTS)}")


@dataclass(frozen=True, slots=True)
class ShipmentCitation:
    """Identifier citation for one shipment/compliance claim.

    Carries kind + identifier only — enough to trace the claim
    to authoritative Xportra state, never content, never a
    verdict.
    """

    kind: str
    identifier: UUID

    def __post_init__(self) -> None:
        if self.kind not in SHIPMENT_CITATION_KINDS:
            raise ValueError(
                "kind must be one of "
                f"{sorted(SHIPMENT_CITATION_KINDS)}")
        _require_uuid(self.identifier, "identifier")


@dataclass(frozen=True, slots=True)
class CitationReference:
    """Validated citation for one regulatory knowledge claim.

    Mirrors the validated ``[En]`` citation mapping (identifiers
    + source pointers only): no raw content, no scores, no
    embedding details, no provider internals.
    """

    label: str
    rank_position: int
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    source_id: str
    source_type: str
    content_fingerprint: str
    source_location: str | None = None
    document_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("label must be non-empty text")
        if not isinstance(self.rank_position, int) or isinstance(
                self.rank_position, bool):
            raise TypeError("rank_position must be an int")
        _require_uuid(self.chunk_id, "chunk_id")
        _require_uuid(self.document_id, "document_id")
        if not isinstance(self.chunk_index, int) or isinstance(
                self.chunk_index, bool):
            raise TypeError("chunk_index must be an int")
        for field_name in ("source_id", "source_type",
                           "content_fingerprint"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty text")


@dataclass(frozen=True, slots=True)
class AssistantResponse:
    """One grounded assistant turn (R-10.2.5).

    - ``grounded``: every claim is sourced (identifier and/or
      validated citations present).
    - ``partial``: sourced claims plus an explicit limitation
      stated in ``summary_text``.
    - ``refused_unknown``: nothing established; no claim is
      presented as fact (no references, reason required).
    """

    conversation_id: UUID
    mode: str
    intent: str
    status: str
    summary_text: str
    shipment_references: tuple[ShipmentCitation, ...] = ()
    citations: tuple[CitationReference, ...] = ()
    refusal_reason: str | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.conversation_id, "conversation_id")
        if self.mode not in CONVERSATION_MODES:
            raise ValueError(
                f"mode must be one of {sorted(CONVERSATION_MODES)}")
        if self.intent not in CONVERSATION_INTENTS:
            raise ValueError(
                f"intent must be one of {sorted(CONVERSATION_INTENTS)}")
        if self.status not in RESPONSE_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(RESPONSE_STATUSES)}")
        _require_non_blank_text(
            self.summary_text, "summary_text", 8000)
        refs = tuple(self.shipment_references)
        for ref in refs:
            if not isinstance(ref, ShipmentCitation):
                raise TypeError(
                    "shipment_references must be ShipmentCitation items")
        object.__setattr__(self, "shipment_references", refs)
        cites = tuple(self.citations)
        for cite in cites:
            if not isinstance(cite, CitationReference):
                raise TypeError(
                    "citations must be CitationReference items")
        object.__setattr__(self, "citations", cites)
        if self.status == RESPONSE_STATUS_REFUSED_UNKNOWN:
            if (not isinstance(self.refusal_reason, str)
                    or not self.refusal_reason.strip()):
                raise ValueError(
                    "refused_unknown requires a refusal_reason")
            if refs or cites:
                raise ValueError(
                    "refused_unknown must not present references as fact")
        else:
            if not refs and not cites:
                raise ValueError(
                    "grounded/partial responses require at least one "
                    "shipment reference or citation")


__all__ = [
    "CONVERSATION_INTENTS",
    "CONVERSATION_MODES",
    "CONVERSATION_MODE_KNOWLEDGE",
    "CONVERSATION_MODE_SHIPMENT_AWARE",
    "INTENT_ANSWER_REGULATORY_QUESTION",
    "INTENT_EXPLAIN_EVIDENCE_GAPS",
    "INTENT_EXPLAIN_FINDING",
    "INTENT_EXPLAIN_REQUIREMENT_STATE",
    "INTENT_SUMMARIZE_SHIPMENT_STATE",
    "MAX_USER_MESSAGE_CHARACTERS",
    "MESSAGE_ROLES",
    "MESSAGE_ROLE_ASSISTANT",
    "MESSAGE_ROLE_USER",
    "MESSAGE_TYPES",
    "MESSAGE_TYPE_TEXT",
    "RESPONSE_STATUSES",
    "RESPONSE_STATUS_GROUNDED",
    "RESPONSE_STATUS_PARTIAL",
    "RESPONSE_STATUS_REFUSED_UNKNOWN",
    "SHIPMENT_INTENTS",
    "SHIPMENT_CITATION_KINDS",
    "UNKNOWN_REFUSAL_TEXT",
    "AssistantResponse",
    "CitationReference",
    "ConversationContext",
    "ConversationIdentity",
    "ShipmentCitation",
    "UserMessage",
]
