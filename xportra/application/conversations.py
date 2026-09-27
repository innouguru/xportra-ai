"""Conversational application boundary (Phase 10.2, R-10.2.3).

Stateless, read-only use case over the frozen conversation
domain contracts::

```text
POST message
    -> authenticate actor (API builds ApplicationContext)
    -> resolve tenant (context tenant, never client-supplied)
    -> validate conversation identity/mode/intent
    -> validate conversation context (mode/context match)
    -> resolve authoritative Xportra context (per-request,
       revalidated: workflow record shape + tenant match)
    -> retrieve grounded knowledge when required (injected
       Phase 5 RAG chain, unchanged)
    -> generate structured response (deterministic rendering;
       NO new LLM invocation)
    -> validate response/citations (grounded/partial/refused)
    -> return response
```

The service owns no compliance truth: shipment answers quote
the revalidated workflow record with identifier citations;
regulatory answers carry the validated RAG answer through
unchanged. It duplicates no compliance engine, performs no
mutation (no upload/record/analysis/finalize/applicability or
state change exists anywhere in this module), persists
nothing, and imports no mutating application service.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.domain.compliance_workflow import (
    WORKFLOW_TERMINAL_STATES,
)
from xportra.domain.conversation import (
    CONVERSATION_INTENTS,
    CONVERSATION_MODES,
    CONVERSATION_MODE_KNOWLEDGE,
    CONVERSATION_MODE_SHIPMENT_AWARE,
    INTENT_ANSWER_REGULATORY_QUESTION,
    INTENT_EXPLAIN_EVIDENCE_GAPS,
    INTENT_EXPLAIN_FINDING,
    INTENT_EXPLAIN_REQUIREMENT_STATE,
    INTENT_SUMMARIZE_SHIPMENT_STATE,
    MAX_USER_MESSAGE_CHARACTERS,
    RESPONSE_STATUS_GROUNDED,
    RESPONSE_STATUS_PARTIAL,
    RESPONSE_STATUS_REFUSED_UNKNOWN,
    SHIPMENT_INTENTS,
    UNKNOWN_REFUSAL_TEXT,
    AssistantResponse,
    CitationReference,
    ConversationContext,
    ShipmentCitation,
    UserMessage,
)
from xportra.domain.evidence_context import EvidenceContextBudget

from . import _guards
from .context import ApplicationContext
from .errors import (
    ApplicationValidationError,
    InfrastructureError,
)

#: Retrieval budget default for conversational knowledge
#: answers. Owned by the domain (``EvidenceContextBudget``);
#: this default only applies when the caller supplies none.
DEFAULT_CONVERSATION_CONTEXT_CHARACTERS = 4000

#: Limitation notice carried by shipment answers that quote
#: workflow-level facts without a stored finding/report in
#: context. Detail beyond identifiers is never invented.
_DETAIL_LIMITATION = (
    " Detailed requirement findings are quoted only from a stored "
    "analysis report, which is not part of this conversation context;"
    " no assessment outcome is changed by this answer."
)

_NO_KNOWLEDGE_REASON = (
    "No validated regulatory retrieval was available for this question."
)


def _citations_from_validated(validated: Any) -> tuple[CitationReference, ...]:
    """Translate the validated citation mapping (identifiers only)."""
    citations = []
    for citation in validated.validated_citations:
        evidence = citation.selected.ranked.evidence
        citations.append(CitationReference(
            label=citation.label,
            rank_position=citation.rank_position,
            chunk_id=evidence.chunk_id,
            document_id=evidence.document_id,
            chunk_index=evidence.chunk_index,
            source_id=evidence.source_id,
            source_type=evidence.source_type,
            content_fingerprint=evidence.content_fingerprint,
            source_location=evidence.source_location,
            document_version=evidence.document_version,
        ))
    return tuple(citations)


class ConversationApplicationService:
    """Stateless read-only conversational use case.

    ``rag`` is the injected Phase 5 RAG application service
    (``RAGApplicationContract``) or ``None``. Shipment-only
    intents never touch it; knowledge intents fail closed with
    ``InfrastructureError`` when it is unwired — an unwired
    chain never becomes an empty successful answer.
    """

    def __init__(self, *, rag: Any | None = None) -> None:
        self._rag = rag

    def handle_message(
        self,
        ctx: ApplicationContext,
        *,
        conversation_id: UUID,
        mode: str,
        intent: str,
        user_text: str,
        workflow_record: dict[str, Any] | None = None,
        requirement_id: UUID | None = None,
        evidence_id: UUID | None = None,
        information_need: str | None = None,
        retrieval_mode: str = "hybrid",
        max_context_characters: int = (
            DEFAULT_CONVERSATION_CONTEXT_CHARACTERS),
        top_k: int | None = None,
    ) -> AssistantResponse:
        context = _guards.checked_context(ctx)
        _guards.checked_uuid(conversation_id, "conversation")
        if mode not in CONVERSATION_MODES:
            raise ApplicationValidationError(
                f"unknown conversation mode: {mode}")
        if intent not in CONVERSATION_INTENTS:
            raise ApplicationValidationError(
                f"unknown conversation intent: {intent}")
        if (not isinstance(user_text, str) or not user_text.strip()
                or len(user_text) > MAX_USER_MESSAGE_CHARACTERS):
            raise ApplicationValidationError(
                "a non-empty user message within the length bound "
                "is required")

        message = UserMessage(
            conversation_id=conversation_id,
            content=user_text,
            intent=intent,
        )

        if mode == CONVERSATION_MODE_KNOWLEDGE:
            if workflow_record is not None:
                raise ApplicationValidationError(
                    "knowledge mode must not carry shipment context")
            ConversationContext(
                conversation_id=conversation_id, mode=mode)
        else:
            if workflow_record is None:
                raise ApplicationValidationError(
                    "shipment-aware mode requires a workflow context")
            ConversationContext(
                conversation_id=conversation_id, mode=mode,
                workflow_id=_guards.parse_uuid(
                    workflow_record.get("id"), "workflow"),
                shipment_id=(
                    None if workflow_record.get("shipment_id") is None
                    else _guards.parse_uuid(
                        workflow_record.get("shipment_id"), "shipment")),
            )

        if intent in SHIPMENT_INTENTS and mode != (
                CONVERSATION_MODE_SHIPMENT_AWARE):
            raise ApplicationValidationError(
                f"intent {intent} requires shipment-aware mode")

        if intent == INTENT_ANSWER_REGULATORY_QUESTION:
            knowledge = self._answer_knowledge(
                context, message, information_need,
                retrieval_mode, max_context_characters, top_k)
            if mode == CONVERSATION_MODE_SHIPMENT_AWARE:
                workflow = _guards.workflow_from_record(workflow_record)
                _guards.ensure_tenant_match(
                    context, workflow.tenant_id, "workflow")
                refs = (ShipmentCitation(
                    kind="workflow", identifier=workflow.id),)
                if knowledge.status == RESPONSE_STATUS_REFUSED_UNKNOWN:
                    return knowledge
                return AssistantResponse(
                    conversation_id=conversation_id,
                    mode=mode,
                    intent=intent,
                    status=knowledge.status,
                    summary_text=knowledge.summary_text,
                    shipment_references=refs,
                    citations=knowledge.citations,
                )
            return knowledge

        return self._answer_shipment(
            context, message, workflow_record,
            requirement_id=requirement_id,
            evidence_id=evidence_id,
        )

    def _answer_shipment(
        self,
        context: ApplicationContext,
        message: UserMessage,
        workflow_record: dict[str, Any] | None,
        *,
        requirement_id: UUID | None,
        evidence_id: UUID | None,
    ) -> AssistantResponse:
        workflow = _guards.workflow_from_record(workflow_record)
        _guards.ensure_tenant_match(
            context, workflow.tenant_id, "workflow")
        refs: list[ShipmentCitation] = [ShipmentCitation(
            kind="workflow", identifier=workflow.id)]
        if requirement_id is not None:
            _guards.checked_uuid(requirement_id, "requirement")
            refs.append(ShipmentCitation(
                kind="requirement", identifier=requirement_id))
        if evidence_id is not None:
            _guards.checked_uuid(evidence_id, "evidence")
            refs.append(ShipmentCitation(
                kind="evidence", identifier=evidence_id))

        state = workflow.state
        terminal_note = (
            " (finalized; read-only)"
            if state in WORKFLOW_TERMINAL_STATES else "")
        rounds = len(workflow.rounds)
        supplied = len(workflow.supplied_evidence_ids)
        open_count = len(workflow.open_requirements)

        if message.intent == INTENT_SUMMARIZE_SHIPMENT_STATE:
            return AssistantResponse(
                conversation_id=message.conversation_id,
                mode=CONVERSATION_MODE_SHIPMENT_AWARE,
                intent=message.intent,
                status=RESPONSE_STATUS_GROUNDED,
                summary_text=(
                    f"Shipment workflow {workflow.id} is in state "
                    f"'{state}'{terminal_note} with {rounds} analysis "
                    f"round(s), {supplied} supplied evidence "
                    f"reference(s), and {open_count} open "
                    f"requirement(s)."),
                shipment_references=tuple(refs),
            )
        if message.intent == INTENT_EXPLAIN_EVIDENCE_GAPS:
            open_refs = ", ".join(
                str(item) for item in workflow.open_requirements)
            return AssistantResponse(
                conversation_id=message.conversation_id,
                mode=CONVERSATION_MODE_SHIPMENT_AWARE,
                intent=message.intent,
                status=RESPONSE_STATUS_GROUNDED,
                summary_text=(
                    f"Shipment workflow {workflow.id} (state "
                    f"'{state}'{terminal_note}) has {supplied} supplied "
                    f"evidence reference(s) and {open_count} open "
                    f"requirement(s)"
                    + (f": {open_refs}." if open_refs else ".")
                    + " Missing information remains missing information;"
                    " no assessment outcome is changed by this answer."),
                shipment_references=tuple(refs),
            )
        # INTENT_EXPLAIN_REQUIREMENT_STATE / INTENT_EXPLAIN_FINDING:
        # workflow-level facts are quoted; per-requirement finding
        # detail lives in stored reports outside this stateless
        # context, so the answer is explicitly partial.
        focus = refs[-1] if len(refs) > 1 else refs[0]
        return AssistantResponse(
            conversation_id=message.conversation_id,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=message.intent,
            status=RESPONSE_STATUS_PARTIAL,
            summary_text=(
                f"Requirement context {focus.identifier} was referenced "
                f"from shipment workflow {workflow.id} (state "
                f"'{state}'{terminal_note})." + _DETAIL_LIMITATION),
            shipment_references=tuple(refs),
        )

    def _answer_knowledge(
        self,
        context: ApplicationContext,
        message: UserMessage,
        information_need: str | None,
        retrieval_mode: str,
        max_context_characters: int,
        top_k: int | None,
    ) -> AssistantResponse:
        if (not isinstance(information_need, str)
                or not information_need.strip()):
            raise ApplicationValidationError(
                "a regulatory question requires an information need")
        if self._rag is None:
            raise InfrastructureError(
                "conversational knowledge answering is not configured "
                "for this deployment")
        query_kwargs: dict[str, Any] = {
            "tenant_id": context.tenant,
            "mode": retrieval_mode,
            "context_budget": EvidenceContextBudget(
                max_context_characters),
        }
        if top_k is not None:
            query_kwargs["top_k"] = top_k
        validated = self._rag.query(
            information_need, **query_kwargs)
        if validated.is_empty:
            return AssistantResponse(
                conversation_id=message.conversation_id,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=message.intent,
                status=RESPONSE_STATUS_REFUSED_UNKNOWN,
                summary_text=UNKNOWN_REFUSAL_TEXT,
                refusal_reason=_NO_KNOWLEDGE_REASON,
            )
        citations = _citations_from_validated(validated)
        status = (
            RESPONSE_STATUS_GROUNDED
            if getattr(validated, "status", "valid") == "valid"
            else RESPONSE_STATUS_PARTIAL)
        if status == RESPONSE_STATUS_PARTIAL and not citations:
            return AssistantResponse(
                conversation_id=message.conversation_id,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=message.intent,
                status=RESPONSE_STATUS_REFUSED_UNKNOWN,
                summary_text=UNKNOWN_REFUSAL_TEXT,
                refusal_reason=(
                    "The retrieved answer failed citation validation."),
            )
        return AssistantResponse(
            conversation_id=message.conversation_id,
            mode=CONVERSATION_MODE_KNOWLEDGE,
            intent=message.intent,
            status=status,
            summary_text=validated.answer_text,
            citations=citations,
        )


__all__ = [
    "ConversationApplicationService",
    "DEFAULT_CONVERSATION_CONTEXT_CHARACTERS",
]
