"""Tenant-role authorization policy for the API boundary."""

from .auth import MemberContext
from .errors import PermissionDeniedError

OWNER_ROLE = "owner"
MEMBER_ROLE = "member"

READ_TENANT_RESOURCE = "read_tenant_resource"
CREATE_EXPORTER = "create_exporter"
CREATE_PRODUCT = "create_product"
CREATE_DESTINATION_MARKET = "create_destination_market"
CREATE_COMPLIANCE_EVIDENCE = "create_compliance_evidence"
ASSOCIATE_EVIDENCE_REQUIREMENT = "associate_evidence_requirement"
CREATE_CERTIFICATION = "create_certification"

_MEMBER_PERMISSIONS = frozenset(
    {
        READ_TENANT_RESOURCE,
        CREATE_COMPLIANCE_EVIDENCE,
        ASSOCIATE_EVIDENCE_REQUIREMENT,
    }
)


def authorize(member: MemberContext, permission: str) -> MemberContext:
    if member.role == OWNER_ROLE:
        return member
    if member.role == MEMBER_ROLE and permission in _MEMBER_PERMISSIONS:
        return member
    raise PermissionDeniedError()


def require_permission(permission: str):
    def dependency(member: MemberContext) -> MemberContext:
        authorize(member, permission)
        return member

    return dependency
