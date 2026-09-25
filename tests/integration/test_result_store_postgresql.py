"""Phase 8.4 — Result-store PostgreSQL integration tests.

Gated on ``DATABASE_URL`` like every other database-backed
suite: applies migration 010, exercises the real
repositories and ``ComplianceResultStore`` end to end
(save, exact round-trip, tenant isolation, idempotent
retry, package linkage and conflict, round ordering,
cross-tenant FK rejection), then rolls the migration
back and verifies removal.

No live Qdrant/OpenRouter execution: analysis runs use
scripted validated answers through the real domain
pipeline.
"""

import json
import os
import pathlib
import unittest
from uuid import UUID

from xportra.application import (
    AnalysisApplicationService,
    WorkflowApplicationService,
)
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    TerminalWorkflowError,
)
from xportra.application.result_store import ComplianceResultStore
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
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.repositories import (
    ComplianceAnalysisReportRepository,
    ComplianceAnalysisRepository,
    ComplianceAnalysisTraceRepository,
    ComplianceWorkflowRoundRepository,
    FinalAssessmentPackageRepository,
    TenantRepository,
)
from xportra.persistence.tenant import TenantContext

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2] / "migrations"
)
UP = MIGRATIONS / "010_compliance_analysis_results.sql"
DOWN = MIGRATIONS / "010_compliance_analysis_results.down.sql"
TABLES = (
    "compliance_analysis_reports",
    "compliance_analyses",
    "compliance_analysis_traces",
    "compliance_workflow_rounds",
    "final_assessment_packages",
)

TENANT_A_SLUG = "phase-8-4-integration-a"
TENANT_B_SLUG = "phase-8-4-integration-b"
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SHIPMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVIDENCE_ID = UUID("66666666-6666-6666-0000-000000000001")

PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="Explain the compliance position."
)


def requirement_id(index):
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


def make_answer(text, tenant_id):
    evidence = EvidenceRetrievalResult(
        tenant_id=tenant_id,
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
    candidate = HybridRetrievalCandidate(
        evidence=evidence, semantic_score=0.9,
        lexical_score=None,
        retrieval_sources=frozenset({"semantic"}))
    ranked = DeterministicEvidenceRanker().rank([candidate],
                                                top_k=1)
    selection = DeterministicContextSelector().select(
        ranked, tenant_id=TenantContext(tenant_id),
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


def make_case(tenant_id, index=1):
    req_id = requirement_id(index)
    records = [EvidenceRecord(
        tenant_id=tenant_id,
        evidence_id=UUID(
            f"66666666-6666-6666-0000-{index:012d}"),
        evidence_type="certificate",
        reference=f"cert://filing-{index}",
        requirement_id=req_id,
        status="accepted",
        metadata={"supports_requirement": True},
    )]
    applicability_result = {
        "id": UUID(f"11111111-1111-1111-1111-{index:012d}"),
        "tenant_id": tenant_id,
        "requirement_id": req_id,
        "outcome": "applicable",
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
    assessment_result = {
        "id": UUID(f"22222222-2222-2222-2222-{index:012d}"),
        "tenant_id": tenant_id,
        "requirement_id": req_id,
        "applicability_result_id": applicability_result["id"],
        "outcome": "satisfied",
        "reason": "required evidence present",
        "evidence_id": records[0].evidence_id,
        "evidence_ids": [r.evidence_id for r in records],
        "status": "assessed",
    }
    return ComplianceCaseService().build(
        applicability_result, requirement, assessment_result,
        records)


def make_summary(tenant_id):
    return {
        "tenant_id": tenant_id,
        "context_fingerprint": "fp-context",
        "status": "decision_summary",
        "applicability": {"total_requirements": 1},
        "risk": {"classified_count": 0},
        "actions": {"recommendation_count": 0},
    }


class FakeRAGService:
    def __init__(self, tenant_id, text="The filing is required [E1]."):
        self._answer = make_answer(text, tenant_id)
        self.calls = []

    def query(self, information_need, *, tenant_id, mode,
              context_budget, scope=None, top_k=5,
              candidate_pool=None):
        self.calls.append(information_need)
        return self._answer


def apply_migration(database, path):
    with database.connection() as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(path.read_text(encoding="utf-8"))


def table_exists(database, table):
    with database.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass(%s)", (f"xportra.{table}",))
            return cursor.fetchone()["to_regclass"] is not None


class ResultStorePostgreSQLTests(unittest.TestCase):
    database = None
    tenant_a = None
    tenant_b = None
    ctx_a = None
    ctx_b = None
    store = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")

        cls.database = Database(DatabaseSettings.from_environment())
        apply_migration(cls.database, UP)
        for table in TABLES:
            if not table_exists(cls.database, table):
                raise unittest.SkipTest(
                    f"migration 010 table {table} was not created")

        tenants = TenantRepository(cls.database)
        tenant_a = tenants.create(
            "Phase 8.4 Tenant A", TENANT_A_SLUG)
        tenant_b = tenants.create(
            "Phase 8.4 Tenant B", TENANT_B_SLUG)
        cls.tenant_a = TenantContext(tenant_a["id"])
        cls.tenant_b = TenantContext(tenant_b["id"])
        cls.ctx_a = ApplicationContext(
            actor_id=None, tenant=cls.tenant_a, role="owner")
        cls.ctx_b = ApplicationContext(
            actor_id=None, tenant=cls.tenant_b, role="owner")
        cls.store = ComplianceResultStore(
            database=cls.database,
            reports=ComplianceAnalysisReportRepository(
                cls.database),
            analyses=ComplianceAnalysisRepository(cls.database),
            traces=ComplianceAnalysisTraceRepository(
                cls.database),
            rounds=ComplianceWorkflowRoundRepository(
                cls.database),
            packages=FinalAssessmentPackageRepository(
                cls.database),
        )

    @classmethod
    def tearDownClass(cls):
        if cls.database is None:
            return
        try:
            apply_migration(cls.database, DOWN)
            for table in TABLES:
                if table_exists(cls.database, table):
                    raise AssertionError(
                        f"rollback left table {table} behind")
        finally:
            with cls.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id FROM xportra.tenants
                        WHERE slug IN (%s, %s)
                        """,
                        (TENANT_A_SLUG, TENANT_B_SLUG),
                    )
                    ids = [row["id"] for row in cursor.fetchall()]
                    if ids:
                        cursor.execute(
                            "DELETE FROM xportra.tenants WHERE id = ANY(%s)",
                            (ids,),
                        )

    def _journey(self, tenant_id):
        from xportra.application import WorkflowApplicationService

        ctx = self.ctx_a if tenant_id == self.tenant_a.tenant_id \
            else self.ctx_b
        app = WorkflowApplicationService()
        record, _ = app.start_workflow(
            ctx, CASE_ID, shipment_id=SHIPMENT_ID)
        for op in ("provide_information", "note_evidence_pending",
                   "record_applicability"):
            record, _ = getattr(app, op)(ctx, record)
        return ctx, record

    def _analyze(self, ctx, record, text=None):
        service = AnalysisApplicationService(
            rag_service=FakeRAGService(
                ctx.tenant_id,
                text or "The filing is required [E1]."),
            result_store=self.store)
        return service.run_analysis(
            ctx, record, [make_case(ctx.tenant_id)],
            max_context_chars=4000,
            decision_summary=make_summary(ctx.tenant_id))

    def test_migration_tables_exist(self):
        for table in TABLES:
            self.assertTrue(
                table_exists(self.database, table), table)

    def test_live_round_trip_is_exact(self):
        ctx, record = self._journey(self.tenant_a.tenant_id)
        record, result, _ = self._analyze(ctx, record)
        rebuilt = self.store.load_result(ctx, result.report.id)
        self.assertEqual(
            json.loads(json.dumps(
                rebuilt.to_record(), default=str)),
            json.loads(json.dumps(
                result.to_record(), default=str)))

    def test_live_tenant_isolation(self):
        ctx, record = self._journey(self.tenant_a.tenant_id)
        _, result, _ = self._analyze(ctx, record)
        with self.assertRaises(ApplicationNotFoundError):
            self.store.load_result(self.ctx_b, result.report.id)
        with self.assertRaises(ApplicationNotFoundError):
            WorkflowApplicationService(
                result_store=self.store).describe_stored_report(
                    self.ctx_b, result.report.id)

    def test_live_idempotent_retry(self):
        from xportra.application._guards import (
            workflow_from_record,
        )

        ctx, record = self._journey(self.tenant_a.tenant_id)
        record, result, _ = self._analyze(ctx, record)
        first = self.store.store_analysis_result(
            ctx, workflow_from_record(record), result)
        second = self.store.store_analysis_result(
            ctx, workflow_from_record(record), result)
        self.assertEqual(first, second)

    def test_live_finalize_and_second_rejected(self):
        app = WorkflowApplicationService(
            result_store=self.store)
        ctx, record = self._journey(self.tenant_a.tenant_id)
        record, result, _ = self._analyze(ctx, record)
        record, _ = app.submit_for_review(ctx, record)
        record, dto = app.finalize_stored_package(ctx, record)
        self.assertEqual(dto.state, "assessment_package_ready")
        stored = app.get_stored_package(ctx, record)
        self.assertEqual(stored.report.report_id,
                         str(result.report.id))
        with self.assertRaises(TerminalWorkflowError):
            app.finalize_stored_package(ctx, record)

    def test_live_cross_tenant_link_rejected(self):
        ctx, record = self._journey(self.tenant_a.tenant_id)
        record, result, _ = self._analyze(ctx, record)
        rounds = ComplianceWorkflowRoundRepository(self.database)
        with self.assertRaises(PersistenceIntegrityError):
            with self.database.transaction() as connection:
                rounds.create_in_transaction(
                    connection, self.ctx_b, UUID(record["id"]),
                    99, CASE_ID, None, result.report.id,
                    [], [], [])

    def test_live_rounds_ordering(self):
        ctx, record = self._journey(self.tenant_a.tenant_id)
        record, _, _ = self._analyze(ctx, record)
        workflow_id = UUID(record["id"])
        rows = self.store.rounds_for_workflow(ctx, workflow_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["round_index"], 1)
        latest = self.store.latest_round_for_workflow(
            ctx, workflow_id)
        assert latest is not None
        self.assertEqual(
            latest["report_id"], rows[0]["report_id"])


if __name__ == "__main__":
    unittest.main()
