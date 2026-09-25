"""Phase 8.1 — Application boundary & use-case contract tests.

Covers ``xportra.application``: HTTP independence, trusted
tenant propagation, domain authority preservation,
allow-listed DTOs without internals leakage, categorized
error propagation, terminal closure enforcement, and
verdict-free orchestration.

Only the RAG/provider boundary and the persistence-backed
evidence service are faked/doubled. All domain services
are real. No Phase 1–7 test is modified.
"""

import ast
import json
import unittest
from uuid import UUID

from xportra.application import (
    AnalysisApplicationService,
    AssessmentApplicationService,
    EvidenceApplicationService,
    WorkflowApplicationService,
)
from xportra.application.context import ApplicationContext
from xportra.application.dtos import (
    AnalysisReportDTO,
    ApplicabilityDTO,
    CaseReadinessDTO,
    WorkflowDTO,
)
from xportra.application.errors import (
    ApplicationAuthorizationError,
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    InvalidTransitionError,
    StaleAnalysisError,
    TenantMismatchError,
    TerminalWorkflowError,
    WorkflowNotReadyError,
)
from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.errors import (
    DomainValidationError,
    LLMProviderError,
)
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
)
from xportra.domain.evidence_hybrid import HybridRetrievalCandidate
from xportra.domain.evidence_prompt import (
    CitationAwarePromptBuilder,
    EvidencePromptConfig,
)
from xportra.domain.evidence_ranking import DeterministicEvidenceRanker
from xportra.domain.evidence_retrieval import EvidenceRetrievalResult
from xportra.domain.ingestion import (
    ComplianceCaseService,
    EvidenceRecord,
)
from xportra.domain.llm import GeneratedAnswer, LLMResponse
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
ACTOR_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)
CTX = ApplicationContext(
    actor_id=ACTOR_ID, tenant=TENANT, role="owner")
MEMBER_CTX = ApplicationContext(
    actor_id=ACTOR_ID, tenant=TENANT, role="member")
OTHER_CTX = ApplicationContext(
    actor_id=ACTOR_ID, tenant=OTHER_TENANT, role="owner")
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SHIPMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVIDENCE_ID = UUID("66666666-6666-6666-0000-000000000001")

WORKFLOWS = WorkflowApplicationService()
PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="Explain the compliance position."
)


def requirement_id(index):
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


def make_knowledge_evidence(**overrides):
    kwargs = dict(
        tenant_id=TENANT_ID,
        chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa00"),
        document_id=DOCUMENT_ID,
        chunk_index=0,
        content="Exporters must file the required form.",
        content_fingerprint="fp-0",
        source_id="sonsa/cert-guide",
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="2024.1",
        embedding_model="test-embed-model",
        embedding_dimensions=4,
        score=0.9,
    )
    kwargs.update(overrides)
    return EvidenceRetrievalResult(**kwargs)


def make_validated_answer(text="The filing is required [E1].",
                           contents=("Exporters must file the form.",),
                           tenant_id=TENANT_ID):
    if contents:
        candidates = []
        for index, content in enumerate(contents):
            evidence = make_knowledge_evidence(
                content=content,
                tenant_id=tenant_id,
                chunk_id=UUID(
                    f"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa0{index}"),
                content_fingerprint=f"fp-{index}",
                score=0.9 - index * 0.1,
            )
            candidates.append(HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=0.9 - index * 0.1,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"})))
        ranked = DeterministicEvidenceRanker().rank(
            candidates, top_k=len(candidates))
        selection = DeterministicContextSelector().select(
            ranked,
            tenant_id=TenantContext(tenant_id),
            budget=EvidenceContextBudget(4000))
    else:
        selection = DeterministicContextSelector().select(
            [],
            tenant_id=TenantContext(tenant_id),
            budget=EvidenceContextBudget(4000))
    prompt = CitationAwarePromptBuilder(
        config=PROMPT_CONFIG).build(
            selection, information_need="filing obligation")
    answer = GeneratedAnswer(
        prompt=prompt,
        response=LLMResponse(
            generated_text=text,
            model_identifier="test-model",
            finish_reason="stop"),
        tenant_id=TenantContext(tenant_id))
    return CitationAwareAnswerValidator().validate(answer)


def make_case(index=1, applicability="applicable",
              assessment="satisfied", evidence_statuses=(),
              assessment_reason="required evidence present"):
    req_id = requirement_id(index)
    records = []
    for slot, status in enumerate(evidence_statuses):
        records.append(EvidenceRecord(
            tenant_id=TENANT_ID,
            evidence_id=UUID(
                f"66666666-6666-6666-{slot:04d}-{index:012d}"),
            evidence_type="certificate",
            reference=f"cert://filing-{index}-{slot}",
            requirement_id=req_id,
            status=status,
            metadata={"supports_requirement": (
                status in ("accepted", "reviewed"))},
        ))
    applicability_result = {
        "id": UUID(f"11111111-1111-1111-1111-{index:012d}"),
        "tenant_id": TENANT_ID,
        "requirement_id": req_id,
        "outcome": applicability,
        "reason": "origin and commodity match",
        "context_fingerprint": "fp-context",
        "context": {"destination": "NG"},
        "status": "determined",
    }
    requirement = {
        "id": req_id,
        "requirement_text": f"Requirement {index} filing duty.",
        "requirement_type": "documentation",
        "source_location": "https://example.test/guide",
        "source_id": "sonsa/cert-guide",
        "normalized_document_id": DOCUMENT_ID,
        "artifact_id": UUID("99999999-9999-9999-9999-999999999999"),
    }
    if applicability == "applicable" and (
            assessment != "unknown" or records):
        assessment_result = {
            "id": UUID(f"22222222-2222-2222-2222-{index:012d}"),
            "tenant_id": TENANT_ID,
            "requirement_id": req_id,
            "applicability_result_id": applicability_result["id"],
            "outcome": assessment,
            "reason": assessment_reason,
            "evidence_id": records[0].evidence_id if records else None,
            "evidence_ids": [r.evidence_id for r in records],
            "status": "assessed",
        }
    else:
        assessment_result = None
    return ComplianceCaseService().build(
        applicability_result, requirement, assessment_result,
        records)


def make_requirement(index=1):
    return {
        "id": requirement_id(index),
        "requirement_text": f"Requirement {index} filing duty.",
        "requirement_type": "documentation",
        "actor": ["exporter"],
        "source_location": "https://example.test/guide",
    }


def make_summary(tenant_id=TENANT_ID):
    return {
        "tenant_id": tenant_id,
        "context_fingerprint": "fp-context",
        "status": "decision_summary",
        "applicability": {"total_requirements": 1},
        "risk": {"classified_count": 0},
        "actions": {"recommendation_count": 0},
    }


class FakeRAGService:
    def __init__(self, answers=None, failure=None):
        self._answers = list(answers or [make_validated_answer()])
        self._failure = failure
        self.calls = []

    def query(self, information_need, *, tenant_id, mode,
              context_budget, scope=None, top_k=5,
              candidate_pool=None):
        self.calls.append(information_need)
        if self._failure is not None:
            raise self._failure
        if len(self._answers) > 1:
            return self._answers.pop(0)
        return self._answers[0]


class FakeEvidenceService:
    """Recording double for the persistence-backed evidence service."""

    def __init__(self, rows=None, failure=None):
        self._rows = dict(rows or {})
        self._failure = failure
        self.calls = []

    def record(self, tenant, title, doc_type, uri, **kwargs):
        self.calls.append(("record", tenant.tenant_id))
        if self._failure is not None:
            raise self._failure
        row = {
            "id": EVIDENCE_ID,
            "tenant_id": tenant.tenant_id,
            "document_title": title,
            "document_type": doc_type,
            "file_reference_or_uri": uri,
            "status": kwargs.get("status", "uploaded"),
        }
        self._rows[EVIDENCE_ID] = row
        return row

    def record_with_requirements(self, tenant, title, doc_type,
                                 uri, requirement_ids, **kwargs):
        self.calls.append(
            ("record_with_requirements", tenant.tenant_id))
        if self._failure is not None:
            raise self._failure
        return self.record(tenant, title, doc_type, uri, **kwargs)

    def get(self, tenant, evidence_id):
        self.calls.append(("get", tenant.tenant_id))
        if self._failure is not None:
            raise self._failure
        return self._rows.get(evidence_id)


def start_case(ctx=CTX, shipment_id=SHIPMENT_ID):
    return WORKFLOWS.start_workflow(
        ctx, CASE_ID, shipment_id=shipment_id)


def progress_to_review(record, ctx=CTX):
    record, _ = WORKFLOWS.provide_information(ctx, record)
    record, _ = WORKFLOWS.note_evidence_pending(ctx, record)
    record, _ = WORKFLOWS.record_applicability(ctx, record)
    return record


def analysis_service(rag=None):
    return AnalysisApplicationService(
        rag_service=rag or FakeRAGService())


def run_first(record, ctx=CTX, rag=None, cases=None,
              summary="default"):
    params = {"max_context_chars": 4000}
    if summary == "default":
        params["decision_summary"] = make_summary()
    elif summary is not None:
        params["decision_summary"] = summary
    return analysis_service(rag).run_analysis(
        ctx, record,
        cases if cases is not None else [make_case(
            evidence_statuses=("accepted",))],
        **params)


class ContextTests(unittest.TestCase):
    def test_valid_context_carries_effective_tenant(self):
        self.assertEqual(CTX.tenant_id, TENANT_ID)
        self.assertEqual(CTX.role, "owner")
        self.assertEqual(CTX.actor_id, ACTOR_ID)

    def test_malformed_context_rejected(self):
        with self.assertRaises(TypeError):
            ApplicationContext(
                actor_id=ACTOR_ID, tenant=TENANT_ID,
                role="owner")
        with self.assertRaises(ValueError):
            ApplicationContext(
                actor_id=ACTOR_ID, tenant=TENANT,
                role="  ")
        with self.assertRaises(TypeError):
            ApplicationContext(
                actor_id="not-a-uuid", tenant=TENANT,
                role="owner")

    def test_use_case_rejects_non_context(self):
        with self.assertRaises(ApplicationValidationError):
            WORKFLOWS.start_workflow(
                TENANT, CASE_ID, shipment_id=SHIPMENT_ID)


class HttpIndependenceTests(unittest.TestCase):
    def test_application_imports_no_http_framework(self):
        import pathlib

        package = (pathlib.Path(__file__).resolve().parents[2]
                   / "xportra" / "application")
        for path in sorted(package.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.update(
                        alias.name.split(".")[0]
                        for alias in node.names)
                elif (isinstance(node, ast.ImportFrom)
                        and node.module and node.level == 0):
                    modules.add(node.module.split(".")[0])
            self.assertTrue(
                modules.isdisjoint(
                    {"fastapi", "starlette", "httpx",
                     "requests", "flask", "django"}),
                f"{path.name} imports an HTTP framework")

    def test_use_cases_run_without_http(self):
        record, dto = start_case()
        self.assertIsInstance(dto, WorkflowDTO)
        self.assertEqual(dto.tenant_id, str(TENANT_ID))
        self.assertEqual(dto.shipment_id, str(SHIPMENT_ID))


class TenantPropagationTests(unittest.TestCase):
    def test_domain_receives_context_tenant(self):
        record, dto = start_case(ctx=MEMBER_CTX)
        self.assertEqual(dto.tenant_id, str(TENANT_ID))
        self.assertEqual(record["tenant_id"], str(TENANT_ID))

    def test_cross_tenant_record_rejected(self):
        record, _ = start_case()
        with self.assertRaises(TenantMismatchError):
            WORKFLOWS.provide_information(OTHER_CTX, record)
        with self.assertRaises(TenantMismatchError):
            WORKFLOWS.get_workflow(OTHER_CTX, record)
        with self.assertRaises(TenantMismatchError):
            WORKFLOWS.is_closed(OTHER_CTX, record)

    def test_cross_tenant_analysis_rejected_before_cost(self):
        record, _ = start_case()
        record = progress_to_review(record)
        rag = FakeRAGService()
        with self.assertRaises(TenantMismatchError):
            analysis_service(rag).run_analysis(
                OTHER_CTX, record, [make_case()],
                max_context_chars=4000)
        self.assertEqual(rag.calls, [])

    def test_supply_builds_scope_from_context(self):
        record, _ = start_case()
        record = progress_to_review(record)
        record, _, _ = run_first(record)
        record, _ = WORKFLOWS.submit_for_review(CTX, record)
        record, _ = WORKFLOWS.request_additional_evidence(
            CTX, record, [requirement_id(1)])
        record, dto = WORKFLOWS.supply_evidence(
            CTX, record, EVIDENCE_ID)
        self.assertIn(str(EVIDENCE_ID),
                      dto.supplied_evidence_ids)


class DomainAuthorityTests(unittest.TestCase):
    def test_invalid_transition_propagates_with_cause(self):
        record, _ = start_case()
        record, _ = WORKFLOWS.provide_information(CTX, record)
        with self.assertRaises(InvalidTransitionError) as raised:
            WORKFLOWS.provide_information(CTX, record)
        self.assertIsInstance(
            raised.exception.__cause__, DomainValidationError)

    def test_not_ready_carries_structured_reasons(self):
        record, _ = start_case()
        record = progress_to_review(record)
        record, result, _ = run_first(record)
        with self.assertRaises(WorkflowNotReadyError) as raised:
            WORKFLOWS.finalize_package(CTX, record, result)
        self.assertTrue(raised.exception.reasons)
        self.assertTrue(all(
            len(reason) == 2
            for reason in raised.exception.reasons))

    def test_stale_analysis_has_own_category(self):
        record, _ = start_case()
        record = progress_to_review(record)
        record, first, _ = run_first(
            record, cases=[make_case(
                1, assessment="unknown", evidence_statuses=(),
                assessment_reason="required evidence absent")])
        record, _ = WORKFLOWS.submit_for_review(CTX, record)
        record, _ = WORKFLOWS.request_additional_evidence(
            CTX, record, [requirement_id(1)])
        record, _ = WORKFLOWS.supply_evidence(
            CTX, record, EVIDENCE_ID)
        record, _, _ = run_first(
            record, cases=[make_case(
                1, evidence_statuses=("accepted",))])
        record, _ = WORKFLOWS.submit_for_review(CTX, record)
        with self.assertRaises(StaleAnalysisError):
            WORKFLOWS.finalize_package(CTX, record, first)

    def test_terminal_closure_enforced(self):
        record, _ = start_case()
        record = progress_to_review(record)
        record, result, _ = run_first(record)
        record, _ = WORKFLOWS.submit_for_review(CTX, record)
        record, _ = WORKFLOWS.finalize_package(
            CTX, record, result)
        self.assertTrue(WORKFLOWS.is_closed(CTX, record))
        with self.assertRaises(TerminalWorkflowError):
            WORKFLOWS.supply_evidence(
                CTX, record, EVIDENCE_ID)
        rag = FakeRAGService()
        with self.assertRaises(TerminalWorkflowError):
            analysis_service(rag).run_analysis(
                CTX, record, [make_case()],
                max_context_chars=4000)
        self.assertEqual(rag.calls, [])


class DtoPrivacyTests(unittest.TestCase):
    def test_full_journey_dtos_leak_no_internals(self):
        record, _ = start_case()
        record = progress_to_review(record)
        record, result, report = run_first(record)
        record, _ = WORKFLOWS.submit_for_review(CTX, record)
        record, package_dto = WORKFLOWS.finalize_package(
            CTX, record, result)
        history = WORKFLOWS.get_history(
            CTX, record, reasoning_result=result,
            assessment_package=None)
        # Report and history DTOs are strictly JSON-safe.
        body = json.dumps({
            "report": report.to_dict(),
            "history": history.to_dict(),
        }).lower()
        # The carried Phase 3.5 summary keeps its authority
        # shape (including a UUID tenant identity the API
        # serializes); it is scanned but dumped leniently.
        package_body = json.dumps(
            package_dto.to_dict(), default=str).lower()
        for marker in ("prompt", "secret", "api_key", "password",
                       "openrouter", "qdrant", "generated_text",
                       "model_identifier", "input_fingerprint",
                       "content_fingerprint",
                       "answer_fingerprint",
                       "chain-of-thought"):
            self.assertNotIn(marker, body)
            self.assertNotIn(marker, package_body)

    def test_round_dto_exposes_references_not_fingerprints(self):
        record, _ = start_case()
        record = progress_to_review(record)
        record, _, _ = run_first(record)
        dto = WORKFLOWS.get_workflow(CTX, record)
        body = dto.to_dict()
        self.assertEqual(len(body["rounds"]), 1)
        self.assertEqual(
            set(body["rounds"][0]),
            {"round_index", "report_id", "analysis_ids",
             "trace_ids"})

    def test_report_carries_no_verdict(self):
        record, _ = start_case()
        _, _, report = run_first(progress_to_review(record))
        body = json.dumps(report.to_dict()).lower()
        for marker in ("verdict", "overall", "compliant",
                       "score", "percent"):
            self.assertNotIn(marker, body)
        self.assertIn("counts", report.to_dict())
        self.assertEqual(len(report.findings), 1)

    def test_malformed_translator_inputs_rejected(self):
        with self.assertRaises(ApplicationValidationError):
            WorkflowDTO.from_record({"nope": True},
                                    is_closed=False)
        with self.assertRaises(ApplicationValidationError):
            AnalysisReportDTO.from_record({"nope": True})


class OrchestrationTests(unittest.TestCase):
    def test_full_journey_through_application(self):
        record, dto = start_case()
        self.assertEqual(dto.state, "created")
        record, dto = WORKFLOWS.provide_information(CTX, record)
        self.assertEqual(dto.state, "information_provided")
        record, dto = WORKFLOWS.note_evidence_pending(
            CTX, record)
        record, dto = WORKFLOWS.record_applicability(
            CTX, record)
        self.assertEqual(dto.state, "applicability_determined")
        record, result, report = run_first(record)
        self.assertEqual(report.case_id, str(CASE_ID))
        record, dto = WORKFLOWS.submit_for_review(CTX, record)
        record, package_dto = WORKFLOWS.finalize_package(
            CTX, record, result)
        self.assertEqual(package_dto.state,
                         "assessment_package_ready")
        self.assertEqual(package_dto.shipment_id,
                         str(SHIPMENT_ID))
        history = WORKFLOWS.get_history(
            CTX, record, reasoning_result=result)
        self.assertTrue(history.round_count >= 1)

    def test_rerun_after_additional_evidence(self):
        record, _ = start_case()
        record = progress_to_review(record)
        record, _, _ = run_first(record, cases=[make_case(
            1, assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")])
        record, _ = WORKFLOWS.submit_for_review(CTX, record)
        record, _ = WORKFLOWS.request_additional_evidence(
            CTX, record, [requirement_id(1)])
        record, _ = WORKFLOWS.supply_evidence(
            CTX, record, EVIDENCE_ID)
        record, _, report = run_first(
            record, cases=[make_case(
                1, evidence_statuses=("accepted",))])
        self.assertEqual(len(report.findings), 1)
        dto = WORKFLOWS.get_workflow(CTX, record)
        self.assertEqual(dto.round_count, 2)

    def test_start_is_deterministic(self):
        first, _ = start_case()
        second, _ = start_case()
        self.assertEqual(first, second)

    def test_services_hold_no_workflow_state(self):
        service = WorkflowApplicationService()
        self.assertEqual(
            set(service.__dict__),
            {"_workflows", "_intake", "_readiness", "_history",
             "_result_store"})


class EvidenceTests(unittest.TestCase):
    def test_record_and_read_evidence(self):
        service = EvidenceApplicationService(
            evidence_service=FakeEvidenceService())
        dto = service.record_evidence(
            CTX, document_title="Phyto Certificate",
            document_type="certificate",
            file_reference_or_uri="supabase://bucket/cert.pdf")
        self.assertEqual(dto.evidence_id, str(EVIDENCE_ID))
        self.assertEqual(dto.tenant_id, str(TENANT_ID))
        fetched = service.get_evidence(CTX, EVIDENCE_ID)
        self.assertEqual(fetched.evidence_id, str(EVIDENCE_ID))

    def test_unknown_evidence_is_not_found(self):
        service = EvidenceApplicationService(
            evidence_service=FakeEvidenceService())
        with self.assertRaises(ApplicationNotFoundError):
            service.get_evidence(CTX, EVIDENCE_ID)

    def test_cross_tenant_row_rejected(self):
        foreign = {
            "id": EVIDENCE_ID,
            "tenant_id": OTHER_TENANT_ID,
            "document_title": "Other",
            "document_type": "certificate",
            "status": "uploaded",
        }
        service = EvidenceApplicationService(
            evidence_service=FakeEvidenceService(
                rows={EVIDENCE_ID: foreign}))
        with self.assertRaises(TenantMismatchError):
            service.get_evidence(CTX, EVIDENCE_ID)

    def test_evidence_validation_mapped(self):
        service = EvidenceApplicationService(
            evidence_service=FakeEvidenceService())
        with self.assertRaises(ApplicationValidationError):
            service.record_evidence(
                CTX, document_title="  ",
                document_type="certificate",
                file_reference_or_uri="supabase://bucket/x.pdf")


class AssessmentTests(unittest.TestCase):
    def test_applicability_preserves_unknown(self):
        service = AssessmentApplicationService()
        dto = service.determine_applicability(
            CTX, [make_requirement(1), make_requirement(2)],
            exporter={"country_of_registration": "NG"},
            destination={"country_code": "GH"})
        self.assertEqual(dto.counts["total_requirements"], 2)
        self.assertEqual(
            sum(dto.counts[key] for key in
                ("applicable_count", "not_applicable_count",
                 "unknown_count")), 2)
        self.assertEqual(len(dto.results), 2)

    def test_case_readiness_reports_gaps(self):
        service = AssessmentApplicationService()
        dto = service.assess_case_readiness(
            CTX, [make_case(
                1, assessment="unknown", evidence_statuses=(),
                assessment_reason="required evidence absent")])
        self.assertIn(dto.readiness_state,
                      {"ready", "partially_ready", "not_ready"})
        self.assertTrue(dto.missing_information_count >= 0)
        self.assertEqual(
            dto.missing_information_count, len(dto.gaps))

    def test_cross_tenant_case_rejected(self):
        service = AssessmentApplicationService()
        foreign_case = dict(make_case())
        foreign_case["tenant_id"] = OTHER_TENANT_ID
        with self.assertRaises(TenantMismatchError):
            service.assess_case_readiness(CTX, [foreign_case])


class ErrorTaxonomyTests(unittest.TestCase):
    def test_authorization_failure_propagates_untouched(self):
        denied = ApplicationAuthorizationError("denied")
        service = EvidenceApplicationService(
            evidence_service=FakeEvidenceService(
                failure=denied))
        with self.assertRaises(ApplicationAuthorizationError):
            service.record_evidence(
                CTX, document_title="T", document_type="c",
                file_reference_or_uri="u")

    def test_provider_failure_becomes_infrastructure_error(self):
        record, _ = start_case()
        record = progress_to_review(record)
        rag = FakeRAGService(failure=LLMProviderError(
            "generate", RuntimeError("provider down")))
        with self.assertRaises(InfrastructureError) as raised:
            analysis_service(rag).run_analysis(
                CTX, record, [make_case()],
                max_context_chars=4000)
        self.assertEqual(
            raised.exception.category, "infrastructure_failure")
        self.assertIsInstance(
            raised.exception.__cause__, LLMProviderError)

    def test_detail_sanitized(self):
        from xportra.application.errors import sanitized_detail

        long_failure = RuntimeError("x" * 500 + "\nsecret?")
        detail = sanitized_detail(long_failure)
        self.assertNotIn("\n", detail)
        self.assertLessEqual(len(detail), 320)


if __name__ == "__main__":
    unittest.main()
