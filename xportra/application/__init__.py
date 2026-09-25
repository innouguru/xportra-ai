"""Application/use-case layer for Xportra AI.

Architecture:

```text
UI → FastAPI API → application use cases → existing domain
```

This package orchestrates the completed domain services
and translates their results into allow-listed DTOs. It
owns no compliance truth, no workflow transitions, no
readiness or closure rules, no retrieval, no reasoning,
and no HTTP constructs. Result retention is delegated
to injected repositories through the result store —
never globals, sessions, or client state. Every use case
takes an ``ApplicationContext`` (built by the API from
server-resolved membership) and propagates its effective
tenant; use cases are stateless over workflow records,
with live result/package objects traveling in-session.
"""

from .analysis import AnalysisApplicationService
from .assessments import AssessmentApplicationService
from .context import ApplicationContext
from .dtos import (
    AnalysisReportDTO,
    AnalysisRoundDTO,
    ApplicabilityDTO,
    ApplicabilityResultDTO,
    CaseReadinessDTO,
    EvidenceRecordDTO,
    EvidenceReferenceDTO,
    FinalPackageDTO,
    HistoryDTO,
    HistoryEntryDTO,
    PackageReferenceDTO,
    ReadinessDTO,
    ReadinessGapDTO,
    RequirementFindingDTO,
    ShipmentDTO,
    WorkflowDTO,
)
from .errors import (
    ApplicationAuthenticationError,
    ApplicationAuthorizationError,
    ApplicationError,
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    InvalidTransitionError,
    StaleAnalysisError,
    TenantMismatchError,
    TerminalWorkflowError,
    WorkflowNotReadyError,
    sanitized_detail,
)
from .evidence import EvidenceApplicationService
from .result_store import (
    ComplianceResultStore,
    rebuild_analysis,
    rebuild_report,
    rebuild_result,
    rebuild_trace,
)
from .workflows import WorkflowApplicationService

__all__ = [
    "AnalysisApplicationService",
    "AnalysisReportDTO",
    "AnalysisRoundDTO",
    "ApplicabilityDTO",
    "ApplicabilityResultDTO",
    "ApplicationAuthenticationError",
    "ApplicationAuthorizationError",
    "ApplicationContext",
    "ApplicationError",
    "ApplicationNotFoundError",
    "ApplicationValidationError",
    "AssessmentApplicationService",
    "CaseReadinessDTO",
    "ComplianceResultStore",
    "EvidenceApplicationService",
    "EvidenceRecordDTO",
    "EvidenceReferenceDTO",
    "FinalPackageDTO",
    "HistoryDTO",
    "HistoryEntryDTO",
    "InfrastructureError",
    "InvalidTransitionError",
    "PackageReferenceDTO",
    "ReadinessDTO",
    "ReadinessGapDTO",
    "RequirementFindingDTO",
    "ShipmentDTO",
    "StaleAnalysisError",
    "TenantMismatchError",
    "TerminalWorkflowError",
    "WorkflowApplicationService",
    "WorkflowDTO",
    "WorkflowNotReadyError",
    "rebuild_analysis",
    "rebuild_report",
    "rebuild_result",
    "rebuild_trace",
    "sanitized_detail",
]
