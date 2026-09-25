"""Phase 8.4 — Normalized Phase 6 result store tests.

Covers ``ComplianceResultStore`` (atomic retention, exact
reconstruction, idempotent retry, tenant isolation, fail-closed
corruption handling) and its application integration
(persist-on-analysis, stored finalization/package/report
reads, terminal enforcement across requests).

Repositories are dict-backed fakes implementing the exact
repository interface (PK conflicts raise like the real
unique constraints); all domain services are real; no live
database is touched here — gated live coverage lives in
``tests/integration/test_result_store_postgresql.py``.
No Phase 1–8.3 test is modified.
"""

import unittest
from contextlib import contextmanager
from uuid import UUID

from xportra.application import (
    AnalysisApplicationService,
    WorkflowApplicationService,
)
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    StaleAnalysisError,
    TenantMismatchError,
    TerminalWorkflowError,
)
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    StaleAnalysisError,
    TenantMismatchError,
    TerminalWorkflowError,
)
from xportra.application.result_store import (
    ComplianceResultStore,
    rebuild_result,
)
from xportra.domain.answer_validation import CitationAwareAnswerValidator
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
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
ACTOR_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)
CTX = ApplicationContext(
    actor_id=ACTOR_ID, tenant=TENANT, role="owner")
OTHER_CTX = ApplicationContext(
    actor_id=ACTOR_ID, tenant=OTHER_TENANT, role="owner")
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SHIPMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVIDENCE_ID = UUID("66666666-6666-6666-0000-000000000001")

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


class FakeDatabase:
    @contextmanager
    def transaction(self):
        yield object()


def _conflict():
    return PersistenceIntegrityError(
        "test", RuntimeError("conflict"))


class FakeReportRepository:
    def __init__(self):
        self.rows = {}
        self.calls = []

    def create_in_transaction(
            self, connection, tenant, report_id, case_id,
            workflow_id, context_fingerprint, counts,
            missing, uncertain, conflicting,
            missing_information, conflicting_count,
            decision_summary):
        self.calls.append(report_id)
        if report_id in self.rows:
            raise _conflict()
        self.rows[report_id] = {
            "id": report_id, "tenant_id": tenant.tenant_id,
            "case_id": case_id, "workflow_id": workflow_id,
            "context_fingerprint": context_fingerprint,
            "total_requirements": counts["total_requirements"],
            "applicable_count": counts["applicable_count"],
            "satisfied_count": counts["satisfied_count"],
            "not_satisfied_count": counts["not_satisfied_count"],
            "unknown_count": counts["unknown_count"],
            "not_applicable_count": counts[
                "not_applicable_count"],
            "requirements_with_missing_information": missing,
            "uncertain_requirement_ids": uncertain,
            "requirements_with_conflicting_evidence": conflicting,
            "missing_information": missing_information,
            "conflicting_evidence_count": conflicting_count,
            "decision_summary": decision_summary,
        }
        return self.rows[report_id]

    def get(self, tenant, report_id):
        row = self.rows.get(report_id)
        if row is None or row["tenant_id"] != tenant.tenant_id:
            return None
        return row


class FakeAnalysisRepository:
    def __init__(self):
        self.rows = {}
        self.calls = []

    def create_in_transaction(
            self, connection, tenant, analysis_id, report_id,
            case_id, workflow_id, requirement_id, position,
            requirement_text, applicability, assessment,
            explanation, uncertainty, uncertainty_explanation,
            evidence_sufficiency, contradiction_state,
            sufficiency_explanation, missing_information,
            supporting_evidence, conflicting_evidence,
            knowledge_references, sources, missing_items):
        self.calls.append(analysis_id)
        if analysis_id in self.rows:
            raise _conflict()
        self.rows[analysis_id] = {
            "id": analysis_id, "tenant_id": tenant.tenant_id,
            "report_id": report_id, "case_id": case_id,
            "workflow_id": workflow_id,
            "requirement_id": requirement_id,
            "position": position,
            "requirement_text": requirement_text,
            "applicability": applicability,
            "assessment": assessment, "explanation": explanation,
            "uncertainty": uncertainty,
            "uncertainty_explanation": uncertainty_explanation,
            "evidence_sufficiency": evidence_sufficiency,
            "contradiction_state": contradiction_state,
            "sufficiency_explanation": sufficiency_explanation,
            "missing_information": missing_information,
            "supporting_evidence": supporting_evidence,
            "conflicting_evidence": conflicting_evidence,
            "knowledge_references": knowledge_references,
            "sources": sources, "missing_items": missing_items,
        }
        return self.rows[analysis_id]

    def get(self, tenant, analysis_id):
        row = self.rows.get(analysis_id)
        if row is None or row["tenant_id"] != tenant.tenant_id:
            return None
        return row

    def list_for_report(self, tenant, report_id):
        return sorted(
            (row for row in self.rows.values()
             if row["tenant_id"] == tenant.tenant_id
             and row["report_id"] == report_id),
            key=lambda row: (row["position"], str(row["id"])))


class FakeTraceRepository:
    def __init__(self):
        self.rows = {}
        self.calls = []

    def create_in_transaction(
            self, connection, tenant, trace_id, report_id,
            analysis_id, case_id, workflow_id, requirement_id,
            position, context_fingerprint, applicability,
            assessment, explanation, evidence_sufficiency,
            contradiction_state, sufficiency_explanation,
            uncertainty, missing_information,
            answer_fingerprint, input_fingerprint, steps,
            supporting_evidence, conflicting_evidence,
            knowledge_references, sources):
        self.calls.append(trace_id)
        if trace_id in self.rows:
            raise _conflict()
        self.rows[trace_id] = {
            "id": trace_id, "tenant_id": tenant.tenant_id,
            "report_id": report_id, "analysis_id": analysis_id,
            "case_id": case_id, "workflow_id": workflow_id,
            "requirement_id": requirement_id,
            "position": position,
            "context_fingerprint": context_fingerprint,
            "applicability": applicability,
            "assessment": assessment, "explanation": explanation,
            "evidence_sufficiency": evidence_sufficiency,
            "contradiction_state": contradiction_state,
            "sufficiency_explanation": sufficiency_explanation,
            "uncertainty": uncertainty,
            "missing_information": missing_information,
            "answer_fingerprint": answer_fingerprint,
            "input_fingerprint": input_fingerprint,
            "steps": steps,
            "supporting_evidence": supporting_evidence,
            "conflicting_evidence": conflicting_evidence,
            "knowledge_references": knowledge_references,
            "sources": sources,
        }
        return self.rows[trace_id]

    def get(self, tenant, trace_id):
        row = self.rows.get(trace_id)
        if row is None or row["tenant_id"] != tenant.tenant_id:
            return None
        return row

    def list_for_report(self, tenant, report_id):
        return sorted(
            (row for row in self.rows.values()
             if row["tenant_id"] == tenant.tenant_id
             and row["report_id"] == report_id),
            key=lambda row: (row["position"], str(row["id"])))


class FakeRoundRepository:
    def __init__(self):
        self.rows = {}
        self.calls = []

    def create_in_transaction(
            self, connection, tenant, workflow_id, round_index,
            case_id, shipment_id, report_id, analysis_ids,
            trace_ids, input_fingerprints):
        self.calls.append((workflow_id, round_index))
        key = (tenant.tenant_id, workflow_id, round_index)
        if key in self.rows:
            raise _conflict()
        self.rows[key] = {
            "tenant_id": tenant.tenant_id,
            "workflow_id": workflow_id,
            "round_index": round_index, "case_id": case_id,
            "shipment_id": shipment_id, "report_id": report_id,
            "analysis_ids": analysis_ids,
            "trace_ids": trace_ids,
            "input_fingerprints": input_fingerprints,
        }
        return self.rows[key]

    def get(self, tenant, workflow_id, round_index):
        return self.rows.get(
            (tenant.tenant_id, workflow_id, round_index))

    def list_for_workflow(self, tenant, workflow_id):
        return sorted(
            (row for (t, w, _), row in self.rows.items()
             if t == tenant.tenant_id and w == workflow_id),
            key=lambda row: row["round_index"])

    def latest_for_workflow(self, tenant, workflow_id):
        rows = self.list_for_workflow(tenant, workflow_id)
        return rows[-1] if rows else None


class FakePackageRepository:
    def __init__(self):
        self.rows = {}
        self.calls = []

    def create_in_transaction(
            self, connection, tenant, workflow_id, case_id,
            shipment_id, report_id, round_index,
            open_requirements):
        self.calls.append(workflow_id)
        key = (tenant.tenant_id, workflow_id)
        if key in self.rows:
            raise _conflict()
        self.rows[key] = {
            "tenant_id": tenant.tenant_id,
            "workflow_id": workflow_id, "case_id": case_id,
            "shipment_id": shipment_id, "report_id": report_id,
            "round_index": round_index,
            "open_requirements": open_requirements,
        }
        return self.rows[key]

    def get(self, tenant, workflow_id):
        return self.rows.get((tenant.tenant_id, workflow_id))


def make_store(reports=None, analyses=None, traces=None,
               rounds=None, packages=None):
    return ComplianceResultStore(
        database=FakeDatabase(),
        reports=reports or FakeReportRepository(),
        analyses=analyses or FakeAnalysisRepository(),
        traces=traces or FakeTraceRepository(),
        rounds=rounds or FakeRoundRepository(),
        packages=packages or FakePackageRepository(),
    )


def journey_record(ctx=CTX, case_id=CASE_ID):
    app = WorkflowApplicationService()
    record, _ = app.start_workflow(
        ctx, case_id, shipment_id=SHIPMENT_ID)
    for op in ("provide_information", "note_evidence_pending",
               "record_applicability"):
        record, _ = getattr(app, op)(ctx, record)
    return record


def run_analysis(record, store=None, rag=None, cases=None,
                 summary="default", ctx=CTX):
    service = AnalysisApplicationService(
        rag_service=rag or FakeRAGService(),
        result_store=store)
    params = {"max_context_chars": 4000}
    if summary == "default":
        params["decision_summary"] = make_summary()
    elif summary is not None:
        params["decision_summary"] = summary
    return service.run_analysis(
        ctx, record,
        cases if cases is not None else [make_case(
            evidence_statuses=("accepted",))],
        **params)


def review_record(record, ctx=CTX):
    record, _ = WorkflowApplicationService().submit_for_review(
        ctx, record)
    return record


def transfer(record):
    import json as _json

    return _json.loads(_json.dumps(record))


def normalized(record):
    """JSON-normalized comparison form (UUIDs become strings).

    Mirrors what PostgreSQL JSONB storage guarantees: the
    carried decision summary keeps UUID objects in memory
    but crosses JSON as strings. Content identity is what
    matters, and this comparison proves it exactly.
    """
    import json as _json

    return _json.loads(_json.dumps(record, default=str))


def store_result_for(store, record, result):
    from xportra.application._guards import workflow_from_record

    return store.store_analysis_result(
        CTX, workflow_from_record(record), result)


class StoreRoundTripTests(unittest.TestCase):
    def test_store_and_rebuild_is_exact(self):
        store = make_store()
        record = journey_record()
        record, result, _ = run_analysis(record)
        linkage = store_result_for(store, record, result)
        self.assertEqual(linkage["report_id"], result.report.id)
        self.assertEqual(linkage["round_index"], 1)
        rebuilt = store.load_result(CTX, result.report.id)
        self.assertEqual(
            normalized(rebuilt.to_record()),
            normalized(result.to_record()))

    def test_retry_same_result_converges(self):
        reports, analyses, traces, rounds, packages = (
            FakeReportRepository(), FakeAnalysisRepository(),
            FakeTraceRepository(), FakeRoundRepository(),
            FakePackageRepository())
        store = make_store(reports, analyses, traces, rounds,
                           packages)
        record = journey_record()
        record, result, _ = run_analysis(record)
        first = store_result_for(store, record, result)
        second = store_result_for(store, record, result)
        self.assertEqual(first, second)
        self.assertEqual(len(reports.rows), 1)
        self.assertEqual(len(analyses.rows), 1)
        self.assertEqual(len(traces.rows), 1)
        self.assertEqual(len(rounds.rows), 1)

    def test_divergent_round_slot_keeps_first(self):
        from xportra.application._guards import (
            workflow_from_record,
        )

        store = make_store()
        base = journey_record()
        record_a, first, _ = run_analysis(
            dict(base), rag=FakeRAGService(answers=[
                make_validated_answer(
                    text="The filing is required [E1].")]))
        store_result_for(store, record_a, first)
        record_b, second, _ = run_analysis(
            dict(base), rag=FakeRAGService(answers=[
                make_validated_answer(
                    text="A certificate filing is required [E1].")]))
        self.assertNotEqual(first.report.id, second.report.id)
        with self.assertRaises(InfrastructureError):
            store.store_analysis_result(
                CTX, workflow_from_record(record_b), second)
        kept = store.load_result(CTX, first.report.id)
        self.assertEqual(normalized(kept.to_record()),
                         normalized(first.to_record()))

    def test_unknown_report_is_not_found(self):
        store = make_store()
        with self.assertRaises(ApplicationNotFoundError):
            store.load_result(CTX, UUID(int=0))

    def test_foreign_tenant_cannot_load(self):
        store = make_store()
        record = journey_record()
        record, result, _ = run_analysis(record)
        store_result_for(store, record, result)
        with self.assertRaises(ApplicationNotFoundError):
            store.load_result(OTHER_CTX, result.report.id)

    def test_latest_round_resolution(self):
        from xportra.application._guards import (
            workflow_from_record,
        )

        store = make_store()
        record = journey_record()
        record, first, _ = run_analysis(record)
        store_result_for(store, record, first)
        record = review_record(record)
        app = WorkflowApplicationService()
        record, _ = app.request_additional_evidence(
            CTX, record, [requirement_id(1)])
        record, _ = app.supply_evidence(
            CTX, record, EVIDENCE_ID)
        record, second, _ = run_analysis(record)
        store_result_for(store, record, second)
        workflow_id = workflow_from_record(record).id
        latest = store.latest_round_for_workflow(
            CTX, workflow_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["round_index"], 2)
        self.assertEqual(latest["report_id"], second.report.id)
        rounds = store.rounds_for_workflow(CTX, workflow_id)
        self.assertEqual(
            [row["round_index"] for row in rounds], [1, 2])
        self.assertIsNone(store.latest_round_for_workflow(
            CTX, UUID(int=1)))

    def test_store_requires_configured_shape(self):
        with self.assertRaises(ApplicationValidationError):
            ComplianceResultStore(
                database=FakeDatabase(),
                reports=FakeReportRepository(),
                analyses=object(),
                traces=FakeTraceRepository(),
                rounds=FakeRoundRepository(),
                packages=FakePackageRepository())
        with self.assertRaises(ApplicationValidationError):
            ComplianceResultStore(
                database=None,
                reports=FakeReportRepository(),
                analyses=FakeAnalysisRepository(),
                traces=FakeTraceRepository(),
                rounds=FakeRoundRepository(),
                packages=FakePackageRepository())


class ReconstructionFailureTests(unittest.TestCase):
    def _stored(self):
        store = make_store()
        record = journey_record()
        record, result, _ = run_analysis(record)
        store_result_for(store, record, result)
        return store, result

    def test_trace_pointing_outside_result_rejected(self):
        store, result = self._stored()
        store._traces.rows[result.traces[0].id]["analysis_id"] = (
            UUID(int=9))
        with self.assertRaises(ApplicationValidationError):
            store.load_result(CTX, result.report.id)

    def test_foreign_tenant_analysis_row_rejected(self):
        store, result = self._stored()
        store._analyses.rows[result.analyses[0].id][
            "tenant_id"] = OTHER_TENANT_ID
        with self.assertRaises(ApplicationValidationError):
            store.load_result(CTX, result.report.id)

    def test_mislinked_trace_report_rejected(self):
        # NOTE: trace.case_id is requirement-view-scoped by
        # Phase 6.5 design and is deliberately not compared;
        # the enforced linkages are tenant, report, and
        # analysis identity. Completeness of the trace set
        # against round linkage is enforced downstream by
        # the 7.3 gate over client-plus-server rounds.
        store, result = self._stored()
        store._traces.rows[result.traces[0].id][
            "analysis_id"] = UUID(int=7)
        with self.assertRaises(ApplicationValidationError):
            store.load_result(CTX, result.report.id)

    def test_corrupt_state_value_rejected(self):
        store, result = self._stored()
        store._analyses.rows[result.analyses[0].id][
            "assessment"] = "compliant"
        with self.assertRaises(ApplicationValidationError):
            store.load_result(CTX, result.report.id)

    def test_corrupt_summary_rejected(self):
        store, result = self._stored()
        store._reports.rows[result.report.id][
            "decision_summary"] = ["not", "a", "mapping"]
        with self.assertRaises(ApplicationValidationError):
            store.load_result(CTX, result.report.id)

    def test_rebuild_helpers_reject_malformed(self):
        from xportra.application.result_store import (
            rebuild_analysis,
            rebuild_report,
            rebuild_trace,
        )

        with self.assertRaises(ApplicationValidationError):
            rebuild_analysis({"nope": True})
        with self.assertRaises(ApplicationValidationError):
            rebuild_trace(None)
        with self.assertRaises(ApplicationValidationError):
            rebuild_report({}, ())


class PrivacyStructureTests(unittest.TestCase):
    MARKERS = ("prompt", "api_key", "password",
               "chain-of-thought", "openrouter", "qdrant")

    def test_stored_structures_carry_no_internals(self):
        import json

        reports, analyses, traces, rounds, packages = (
            FakeReportRepository(), FakeAnalysisRepository(),
            FakeTraceRepository(), FakeRoundRepository(),
            FakePackageRepository())
        store = make_store(reports, analyses, traces, rounds,
                           packages)
        record = journey_record()
        record, result, _ = run_analysis(record)
        store_result_for(store, record, result)
        payloads = []
        for repo in (reports, analyses, traces, rounds):
            for row in repo.rows.values():
                payloads.append(dict(row))
        body = json.dumps(payloads, default=str).lower()
        for marker in self.MARKERS:
            self.assertNotIn(marker, body)

    def test_stored_columns_are_declared_identities(self):
        reports = FakeReportRepository()
        store = make_store(reports=reports)
        record = journey_record()
        record, result, _ = run_analysis(record)
        from xportra.application._guards import (
            workflow_from_record,
        )

        store.store_analysis_result(
            CTX, workflow_from_record(record), result)
        row = reports.rows[result.report.id]
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["case_id"], CASE_ID)
        self.assertIn("decision_summary", row)


class ApplicationIntegrationTests(unittest.TestCase):
    def test_analysis_persists_on_success(self):
        store = make_store()
        service = AnalysisApplicationService(
            rag_service=FakeRAGService(), result_store=store)
        record = journey_record()
        record, result, dto = service.run_analysis(
            CTX, record, [make_case(
                evidence_statuses=("accepted",))],
            max_context_chars=4000,
            decision_summary=make_summary())
        self.assertEqual(dto.report_id, str(result.report.id))
        rebuilt = store.load_result(CTX, result.report.id)
        self.assertEqual(
            normalized(rebuilt.to_record()),
            normalized(result.to_record()))

    def test_store_failure_fails_request(self):
        class FailingStore:
            def store_analysis_result(self, *args, **kwargs):
                from xportra.application.errors import (
                    InfrastructureError as Infra,
                )
                raise Infra("store down")

        service = AnalysisApplicationService(
            rag_service=FakeRAGService(), result_store=FailingStore())
        record = journey_record()
        with self.assertRaises(InfrastructureError):
            service.run_analysis(
                CTX, record, [make_case(
                    evidence_statuses=("accepted",))],
                max_context_chars=4000,
                decision_summary=make_summary())

    def test_finalize_stored_package_end_to_end(self):
        store = make_store()
        app = WorkflowApplicationService(result_store=store)
        analysis = AnalysisApplicationService(
            rag_service=FakeRAGService(), result_store=store)
        record, _ = app.start_workflow(
            CTX, CASE_ID, shipment_id=SHIPMENT_ID)
        record = journey_record()
        record, result, _ = analysis.run_analysis(
            CTX, record, [make_case(
                evidence_statuses=("accepted",))],
            max_context_chars=4000,
            decision_summary=make_summary())
        record = review_record(record)
        record, dto = app.finalize_stored_package(
            CTX, transfer(record))
        self.assertEqual(dto.state,
                         "assessment_package_ready")
        self.assertEqual(dto.report.report_id,
                         str(result.report.id))
        stored = app.get_stored_package(CTX, transfer(record))
        self.assertEqual(stored.report.report_id,
                         str(result.report.id))
        with self.assertRaises(TerminalWorkflowError):
            app.finalize_stored_package(CTX, transfer(record))

    def test_forged_rounds_rejected(self):
        store = make_store()
        app = WorkflowApplicationService(result_store=store)
        analysis = AnalysisApplicationService(
            rag_service=FakeRAGService(), result_store=store)
        record = journey_record()
        record, _, _ = analysis.run_analysis(
            CTX, record, [make_case(
                evidence_statuses=("accepted",))],
            max_context_chars=4000,
            decision_summary=make_summary())
        record = review_record(record)
        forged = dict(record)
        forged["rounds"] = []
        with self.assertRaises(StaleAnalysisError):
            app.finalize_stored_package(CTX, forged)

    def test_stale_client_record_rejected(self):
        store = make_store()
        app = WorkflowApplicationService(result_store=store)
        analysis = AnalysisApplicationService(
            rag_service=FakeRAGService(
                answers=[make_validated_answer(
                    text="The filing is required [E1]."),
                    make_validated_answer(
                        text="A certificate is required [E1].")]),
            result_store=store)
        record = journey_record()
        record, _, _ = analysis.run_analysis(
            CTX, record, [make_case(
                evidence_statuses=("accepted",))],
            max_context_chars=4000,
            decision_summary=make_summary())
        stale_view = transfer(review_record(transfer(record)))
        record = review_record(record)
        app.request_additional_evidence(
            CTX, record, [requirement_id(1)])
        record, _ = app.supply_evidence(
            CTX, record, EVIDENCE_ID)
        record, _, _ = analysis.run_analysis(
            CTX, record, [make_case(
                evidence_statuses=("accepted",))],
            max_context_chars=4000,
            decision_summary=make_summary())
        record = review_record(record)
        with self.assertRaises(StaleAnalysisError):
            app.finalize_stored_package(CTX, stale_view)

    def test_missing_store_paths_fail_closed(self):
        app = WorkflowApplicationService()
        record = journey_record()
        with self.assertRaises(ApplicationValidationError):
            app.finalize_stored_package(CTX, record)
        with self.assertRaises(ApplicationValidationError):
            app.get_stored_package(CTX, record)
        with self.assertRaises(ApplicationValidationError):
            app.describe_stored_report(CTX, UUID(int=3))
        with self.assertRaises(ApplicationValidationError):
            app.load_current_result(CTX, record)
        with self.assertRaises(ApplicationValidationError):
            WorkflowApplicationService(result_store=object())
        with self.assertRaises(ApplicationValidationError):
            AnalysisApplicationService(
                rag_service=FakeRAGService(),
                result_store=object())

    def test_unknown_stored_entities_not_found(self):
        store = make_store()
        app = WorkflowApplicationService(result_store=store)
        record = journey_record()
        with self.assertRaises(ApplicationNotFoundError):
            app.load_current_result(CTX, record)
        with self.assertRaises(ApplicationNotFoundError):
            app.get_stored_package(CTX, record)
        with self.assertRaises(ApplicationNotFoundError):
            app.describe_stored_report(CTX, UUID(int=5))
        with self.assertRaises(ApplicationNotFoundError):
            app.finalize_stored_package(CTX, record)

    def test_cross_tenant_stored_access_rejected(self):
        store = make_store()
        app = WorkflowApplicationService(result_store=store)
        record = journey_record()
        record, result, _ = AnalysisApplicationService(
            rag_service=FakeRAGService(),
            result_store=store).run_analysis(
                CTX, record, [make_case(
                    evidence_statuses=("accepted",))],
                max_context_chars=4000,
                decision_summary=make_summary())
        before = transfer(record)
        with self.assertRaises(TenantMismatchError):
            app.load_current_result(OTHER_CTX, record)
        with self.assertRaises(TenantMismatchError):
            app.finalize_stored_package(OTHER_CTX, record)
        with self.assertRaises(ApplicationNotFoundError):
            app.describe_stored_report(
                OTHER_CTX, result.report.id)
        self.assertEqual(record, before)

    def test_describe_stored_report_round_trip(self):
        store = make_store()
        app = WorkflowApplicationService(result_store=store)
        record = journey_record()
        record, result, _ = AnalysisApplicationService(
            rag_service=FakeRAGService(),
            result_store=store).run_analysis(
                CTX, record, [make_case(
                    evidence_statuses=("accepted",))],
                max_context_chars=4000,
                decision_summary=make_summary())
        dto = app.describe_stored_report(
            CTX, result.report.id)
        self.assertEqual(dto.report_id, str(result.report.id))
        self.assertEqual(len(dto.findings), 1)
        with self.assertRaises(ApplicationValidationError):
            app.describe_stored_report(CTX, "not-a-uuid")


if __name__ == "__main__":
    unittest.main()
