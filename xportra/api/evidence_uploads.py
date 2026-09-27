"""Thin evidence file-upload HTTP adapter (Phase 10.4).

Two endpoints over the upload use case::

    POST /compliance-evidence/uploads
    GET  /compliance-evidence/{evidence_id}/download

Every handler follows the established Phase 8.2 shape:

1. ``require_permission`` resolves the authorized
   ``MemberContext`` (existing Phase 1 boundary — tenant
   from server-side membership, never the request body).
2. The handler builds an ``ApplicationContext`` from that
   membership plus the ``get_request_actor`` subject.
3. Exactly one application use case is invoked.
4. Its DTO result is returned for serialization
   (identifiers + lifecycle state only — never file
   bytes, document text, storage keys, or provider
   internals; the download grant alone carries its
   short-lived signed URL by purpose).

Upload permission follows evidence recording
(member-allowed); download requires owning-tenant
membership (member-readable); analysis stays
owner-only elsewhere. Deliberately absent: bulk
export, public/permanent URLs, client-addressed
object retrieval, raw-content responses, user delete,
and workflow-scoped listing.
"""

import base64
import binascii
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from xportra.application.context import ApplicationContext

from .auth import MemberContext
from .authorization import (
    CREATE_COMPLIANCE_EVIDENCE,
    READ_TENANT_RESOURCE,
)
from .dependencies import (
    EvidenceUploadServiceDependency,
    get_request_actor,
    require_permission,
)
from .errors import APIError
from .schemas import (
    EvidenceDownloadResponse,
    EvidenceUploadRequest,
    EvidenceUploadResponse,
)

router = APIRouter(tags=["compliance-evidence"])


def _context(
    member: MemberContext, actor_id: UUID | None
) -> ApplicationContext:
    return ApplicationContext(
        actor_id=actor_id, tenant=member.tenant, role=member.role
    )


def _decode_content(content_base64: str) -> bytes:
    try:
        return base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as cause:
        raise APIError(
            422,
            "malformed_upload_content",
            "Evidence file content must be valid base64",
        ) from cause


@router.post(
    "/compliance-evidence/uploads",
    response_model=EvidenceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_compliance_evidence(
    payload: EvidenceUploadRequest,
    service: EvidenceUploadServiceDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(CREATE_COMPLIANCE_EVIDENCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Upload, register, and process one evidence file.

    Tenant identity comes exclusively from the
    authenticated member context — the request body
    cannot supply tenants, object keys, or storage
    references. A terminal workflow association is
    rejected before any storage or database mutation.
    """
    dto = service.upload_evidence(
        _context(member, actor_id),
        filename=payload.filename,
        content_type=payload.content_type,
        content=_decode_content(payload.content_base64),
        document_title=payload.document_title,
        document_type=payload.document_type,
        requirement_ids=list(payload.requirement_ids),
        workflow_record=(
            None if payload.workflow is None
            else payload.workflow.model_dump(mode="json")),
    )
    return _upload_response(dto.to_dict())


@router.get(
    "/compliance-evidence/{evidence_id}/download",
    response_model=EvidenceDownloadResponse,
)
def download_compliance_evidence(
    evidence_id: UUID,
    service: EvidenceUploadServiceDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Issue a short-lived download URL for owned evidence.

    The use case verifies the requesting actor's tenant
    and the evidence ownership before any URL is issued;
    cross-tenant lookups fail closed without revealing
    existence.
    """
    dto = service.get_download(_context(member, actor_id), evidence_id)
    return dto.to_dict()


def _upload_response(result: dict[str, Any]) -> dict[str, Any]:
    linked = result.get("linked_requirement_ids") or []
    return {
        "evidence_id": result.get("evidence_id"),
        "tenant_id": result.get("tenant_id"),
        "document_title": result.get("document_title"),
        "document_type": result.get("document_type"),
        "status": result.get("status"),
        "processing_status": result.get("processing_status"),
        "processing_step": result.get("processing_step"),
        "processing_error": result.get("processing_error"),
        "content_hash": result.get("content_hash"),
        "original_filename": result.get("original_filename"),
        "mime_type": result.get("mime_type"),
        "duplicate": result.get("duplicate", False),
        "linked_requirement_ids": list(linked),
    }
