"""Conversational HTTP adapter (Phase 10.2, extended by Workstream 6).

Endpoints::

    POST /conversations                  Create a conversation
    GET  /conversations                  List the tenant's conversations
    GET  /conversations/{conversation_id}  Get a conversation with messages
    POST /conversations/messages         Send one turn (stateless logic + optional persistence)

Every handler follows the established Phase 8.2 shape:

1. ``require_permission`` resolves the authorized ``MemberContext``
   (existing Phase 1 boundary — tenant from server-side membership,
   never the request body).
2. The handler builds an ``ApplicationContext`` from that membership
   plus the ``get_request_actor`` subject.
3. Exactly one application use case
   (``ConversationApplicationService.handle_message`` or the new
   conversation lifecycle methods) is invoked with the optional RAG
   service and persistence repositories from the container.
4. The response is translated to DTO serialization (identifier +
   validated-citation mapping only — no prompts, content, scores,
   or internals).

When conversation repositories are wired, messages are persisted
and conversations can be reopened. When they are not wired, the
service remains stateless (the Phase 10.2 default).
"""

from typing import Annotated, Any
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from xportra.application.context import ApplicationContext
from xportra.application.conversations import (
    ConversationApplicationService,
)
from xportra.application.errors import ApplicationNotFoundError

from .auth import MemberContext
from .authorization import READ_TENANT_RESOURCE
from .dependencies import (
    ServicesDependency,
    get_request_actor,
    require_permission,
)
from .schemas import (
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListItem,
    ConversationListResponse,
    ConversationMessageItem,
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


def _service(services: ServicesDependency) -> ConversationApplicationService:
    """Build the conversational use case from the container.

    The RAG service (for knowledge answers) and the conversation
    / message repositories (for persistence) are both optional;
    the service degrades gracefully when either is absent.
    """
    rag = getattr(services, "rag", None)
    conversation_repo = getattr(services, "conversation_repository", None)
    message_repo = getattr(services, "conversation_message_repository", None)
    database = getattr(services, "database", None)
    return ConversationApplicationService(
        rag=rag,
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        database=database,
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
    "/conversations",
    response_model=ConversationCreateResponse,
)
def create_conversation(
    payload: ConversationCreateRequest,
    services: ServicesDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Create a new conversation for the authenticated tenant.

    Tenant identity comes exclusively from the authenticated member
    context. The conversation is persisted when conversation
    repositories are wired; otherwise the request still succeeds
    (the caller can use any client-generated conversation_id with
    ``POST /conversations/messages``).
    """
    service = _service(services)
    conversation_id = uuid.uuid4()
    result = service.create_conversation(
        _context(member, actor_id),
        conversation_id=conversation_id,
        mode=payload.mode,
    )
    return ConversationCreateResponse(
        id=result["id"],
        tenant_id=result["tenant_id"],
        mode=result["mode"],
    )


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
)
def list_conversations(
    services: ServicesDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """List the authenticated tenant's conversations, most recent first."""
    service = _service(services)
    conversations = service.list_conversations(_context(member, actor_id))
    return ConversationListResponse(
        conversations=[
            ConversationListItem(**c) for c in conversations
        ],
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def get_conversation(
    conversation_id: Annotated[UUID, Path()],
    services: ServicesDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Get one conversation with its full message transcript.

    Tenant isolation is enforced: conversations belonging to another
    tenant return 404.
    """
    service = _service(services)
    detail = service.get_conversation_with_messages(
        _context(member, actor_id), conversation_id=conversation_id)
    if detail is None:
        raise ApplicationNotFoundError(
            "conversation not found for the active tenant")
    return ConversationDetailResponse(
        id=detail["id"],
        tenant_id=detail["tenant_id"],
        mode=detail["mode"],
        created_at=detail["created_at"],
        updated_at=detail["updated_at"],
        messages=[
            ConversationMessageItem(**m) for m in detail["messages"]
        ],
    )


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
    workflow context per request; when persistence is wired,
    both the user message and the assistant response are stored
    so the conversation can be reopened and follow-up questions
    receive preceding context.
    """
    service = _service(services)
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
