"""Thin conversational HTTP adapter (Phase 10.2).

One stateless, read-only endpoint::

    POST /conversations/messages

Every handler follows the established Phase 8.2 shape:

1. ``require_permission`` resolves the authorized
   ``MemberContext`` (existing Phase 1 boundary — tenant
   from server-side membership, never the request body).
2. The handler builds an ``ApplicationContext`` from that
   membership plus the ``get_request_actor`` subject.
3. Exactly one application use case
   (``ConversationApplicationService.handle_message``) is
   invoked with the optional RAG service from the container.
4. Its ``AssistantResponse`` is translated to DTO
   serialization (identifier + validated-citation mapping
   only — no prompts, content, scores, or internals).

Stored-conversation endpoints (start/resume/get) do not exist
here: Phase 10.2 persists nothing (ADR-0010), so there is no
record to create or fetch. Knowledge intents fail closed with
503 when the RAG chain is unwired for the environment, using
the same code/message as the RAG route.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from xportra.application.context import ApplicationContext
from xportra.application.conversations import (
    ConversationApplicationService,
)

from .auth import MemberContext
from .authorization import READ_TENANT_RESOURCE
from .dependencies import (
    ServicesDependency,
    get_request_actor,
    require_permission,
)
from .schemas import (
    ConversationMessageRequest,
    ConversationMessageResponse,
)

router = APIRouter(tags=["conversations"])


def _context(
    member: MemberContext, actor_id: UUID | None
) -> ApplicationContext:
    return ApplicationContext(
        actor_id=actor_id, tenant=member.tenant, role=member.role
    )


def _message_response(answer) -> dict[str, Any]:
    citations = []
    for citation in answer.citations:
        citations.append(
            {
                "label": citation.label,
                "rank_position": citation.rank_position,
                "evidence": {
                    "chunk_id": citation.chunk_id,
                    "document_id": citation.document_id,
                    "chunk_index": citation.chunk_index,
                    "source_id": citation.source_id,
                    "source_type": citation.source_type,
                    "source_location": citation.source_location,
                    "document_version": citation.document_version,
                    "content_fingerprint": citation.content_fingerprint,
                },
            }
        )
    return {
        "conversation_id": answer.conversation_id,
        "mode": answer.mode,
        "intent": answer.intent,
        "status": answer.status,
        "summary_text": answer.summary_text,
        "shipment_references": [
            {"kind": ref.kind, "id": ref.identifier}
            for ref in answer.shipment_references
        ],
        "citations": citations,
        "refusal_reason": answer.refusal_reason,
    }


@router.post(
    "/conversations/messages",
    response_model=ConversationMessageResponse,
)
def post_conversation_message(
    payload: ConversationMessageRequest,
    services: ServicesDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Answer one read-only conversation turn for this tenant.

    Tenant identity comes exclusively from the authenticated
    member context — the request body cannot supply or
    override it. The service revalidates the supplied
    workflow context per request; the server holds no
    conversation session and no transcript store.
    """
    rag = getattr(services, "rag", None)
    # No handler-owned branching: the use case validates
    # mode/context first and raises InfrastructureError when a
    # knowledge intent needs an unwired chain; the central
    # error mapping turns that into a static 503.
    service = ConversationApplicationService(rag=rag)
    answer = service.handle_message(
        _context(member, actor_id),
        conversation_id=payload.conversation_id,
        mode=payload.mode,
        intent=payload.intent,
        user_text=payload.user_text,
        workflow_record=(
            None if payload.workflow is None
            else dict(payload.workflow)),
        requirement_id=payload.requirement_id,
        evidence_id=payload.evidence_id,
        information_need=payload.information_need,
        retrieval_mode=payload.retrieval_mode,
        max_context_characters=payload.max_context_characters,
        top_k=payload.top_k,
    )
    return _message_response(answer)
