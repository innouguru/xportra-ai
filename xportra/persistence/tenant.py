"""Explicit tenant context used by tenant-scoped persistence operations."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, UUID):
            raise TypeError("tenant_id must be a UUID")
