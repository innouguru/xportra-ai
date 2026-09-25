"""Phase 10.1 — Production security & configuration hardening tests.

Covers R-10.1.1 through R-10.1.8 without changing product behavior:

- production configuration boundary (runtime predicates, startup
  validation, docs lockdown, security headers),
- development-tenant-header rejection in production (including when
  ``Authorization`` is also present),
- role authorization policy (owner/member/unknown),
- tenant-isolation matrix across workflow, evidence, analysis,
  report, final-package, and history operations,
- finalized-workflow protection,
- production error-surface (5xx detail stripping, generic unexpected
  errors, preserved structured semantics),
- logging/secret redaction and configuration hygiene.

Only the RAG/provider boundary, persistence repositories, and the
service container are faked/doubled. All domain, application, and API
boundary code under test is real. No prior test is modified.
"""

import asyncio
import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.auth import MemberContext
from xportra.api.authorization import (
    ASSOCIATE_EVIDENCE_REQUIREMENT,
    CREATE_COMPLIANCE_EVIDENCE,
    PROGRESS_COMPLIANCE_WORKFLOW,
    READ_TENANT_RESOURCE,
    RUN_COMPLIANCE_ANALYSIS,
    authorize,
)
from xportra.api.dependencies import (
    get_development_tenant_context,
    get_member_context,
    get_request_actor,
)
from xportra.api.errors import (
    APIError,
    PermissionDeniedError,
    _handle_application_error,
    _handle_unexpected_error,
)
from xportra.api.runtime import (
    ProductionConfigurationError,
    current_app_env,
    is_debug_enabled,
    is_production_environment,
    validate_app_env,
    validate_production_environment,
)
from xportra.application.analysis import AnalysisApplicationService
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    TenantMismatchError,
    TerminalWorkflowError,
    WorkflowNotReadyError,
)
from xportra.application.evidence import EvidenceApplicationService
from xportra.application.result_store import (
    ComplianceResultStore,
    rebuild_result,
)
from xportra.application.workflows import WorkflowApplicationService
from xportra.persistence.tenant import TenantContext

TENANT_A_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT_A = TenantContext(TENANT_A_ID)
TENANT_B = TenantContext(TENANT_B_ID)
ACTOR_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_A = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
EVIDENCE_A = UUID("66666666-6666-6666-0000-000000000001")
REPORT_A = UUID("77777777-7777-7777-7777-777777777777")
ANALYSIS_A = UUID("88888888-8888-8888-8888-888888888888")
REQUIREMENT_A = UUID("00000000-0000-0000-0000-000000000001")

CTX_A = ApplicationContext(
    actor_id=ACTOR_ID, tenant=TENANT_A, role="owner")
CTX_B = ApplicationContext(
    actor_id=ACTOR_ID, tenant=TENANT_B, role="owner")

WORKFLOWS = WorkflowApplicationService()


@contextmanager
def patched_env(**values):
    """Temporarily set (or clear with None) environment variables."""
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def start_record(ctx=CTX_A, case_id=CASE_A):
    record, _ = WORKFLOWS.start_workflow(ctx, case_id)
    return record


def closed_record():
    """A permanently closed workflow record owned by tenant A."""
    return {
        "id": UUID("99999999-9999-9999-9999-999999999999"),
        "tenant_id": TENANT_A_ID,
        "case_id": CASE_A,
        "shipment_id": None,
        "state": "assessment_package_ready",
        "rounds": [],
        "supplied_evidence_ids": [],
        "open_requirements": [],
    }


class RuntimeEnvironmentTests(unittest.TestCase):
    def test_default_environment_is_development(self):
        with patched_env(APP_ENV=None):
            self.assertEqual(current_app_env(), "development")
            self.assertFalse(is_production_environment())

    def test_production_predicate_is_exact_and_case_insensitive(self):
        self.assertTrue(
            is_production_environment({"APP_ENV": "production"}))
        self.assertTrue(
            is_production_environment({"APP_ENV": "Production"}))
        self.assertFalse(
            is_production_environment({"APP_ENV": "test"}))
        self.assertFalse(is_production_environment({}))

    def test_unknown_app_env_is_rejected(self):
        with self.assertRaises(ProductionConfigurationError):
            validate_app_env({"APP_ENV": "staging"})
        self.assertEqual(
            validate_app_env({"APP_ENV": "test"}), "test")

    def test_production_validation_requires_jwt_secret(self):
        with self.assertRaises(ProductionConfigurationError):
            validate_production_environment({
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql://localhost/x",
            })

    def test_production_validation_requires_database_url(self):
        with self.assertRaises(ProductionConfigurationError):
            validate_production_environment({
                "APP_ENV": "production",
                "SUPABASE_JWT_SECRET": "secret-value",
            })

    def test_production_validation_rejects_debug(self):
        for debug in ("true", "1", "yes", "on", "bogus"):
            with self.subTest(debug=debug):
                with self.assertRaises(ProductionConfigurationError):
                    validate_production_environment({
                        "APP_ENV": "production",
                        "SUPABASE_JWT_SECRET": "secret-value",
                        "DATABASE_URL": "postgresql://localhost/x",
                        "APP_DEBUG": debug,
                    })

    def test_production_validation_accepts_pinned_configuration(self):
        validate_production_environment({
            "APP_ENV": "production",
            "SUPABASE_JWT_SECRET": "secret-value",
            "DATABASE_URL": "postgresql://localhost/x",
        })
        validate_production_environment({
            "APP_ENV": "production",
            "SUPABASE_JWT_SECRET": "secret-value",
            "DATABASE_URL": "postgresql://localhost/x",
            "APP_DEBUG": "false",
        })

    def test_non_production_skips_secret_validation(self):
        validate_production_environment({"APP_ENV": "development"})
        validate_production_environment({})

    def test_debug_knob_parsing(self):
        self.assertTrue(is_debug_enabled({"APP_DEBUG": "true"}))
        self.assertFalse(is_debug_enabled({"APP_DEBUG": "false"}))
        self.assertFalse(is_debug_enabled({}))


class ProductionAppFactoryTests(unittest.TestCase):
    def test_unknown_app_env_rejects_app_creation(self):
        with patched_env(APP_ENV="staging"):
            with self.assertRaises(ProductionConfigurationError):
                create_app(services=SimpleNamespace())

    def test_production_disables_docs_and_openapi_schema(self):
        with patched_env(APP_ENV="production",
                          SUPABASE_JWT_SECRET="test-secret"):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                for path in ("/docs", "/redoc", "/openapi.json"):
                    with self.subTest(path=path):
                        self.assertEqual(
                            client.get(path).status_code, 404)

    def test_development_keeps_openapi_schema(self):
        with patched_env(APP_ENV=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                self.assertEqual(
                    client.get("/openapi.json").status_code, 200)

    def test_security_headers_present_in_both_environments(self):
        for env in ("development", "production"):
            extra = {"SUPABASE_JWT_SECRET": "test-secret"} \
                if env == "production" else {}
            with patched_env(APP_ENV=env, **extra):
                with TestClient(create_app(
                        services=SimpleNamespace())) as client:
                    response = client.get("/openapi.json")
                with self.subTest(env=env):
                    self.assertEqual(
                        response.headers["x-content-type-options"],
                        "nosniff")
                    self.assertEqual(
                        response.headers["x-frame-options"], "DENY")
                    self.assertEqual(
                        response.headers["referrer-policy"],
                        "no-referrer")

    def test_production_composed_path_requires_database_url(self):
        with patched_env(APP_ENV="production",
                          SUPABASE_JWT_SECRET="test-secret",
                          DATABASE_URL=None,
                          APP_DEBUG=None):
            with self.assertRaises(ProductionConfigurationError):
                create_app()

    def test_production_composed_path_requires_jwt_secret(self):
        with patched_env(APP_ENV="production",
                          SUPABASE_JWT_SECRET=None,
                          DATABASE_URL="postgresql://localhost/x",
                          APP_DEBUG=None):
            with self.assertRaises(ProductionConfigurationError):
                create_app()

    def test_production_dev_header_request_is_rejected(self):
        with patched_env(APP_ENV="production",
                          SUPABASE_JWT_SECRET="test-secret"):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.post(
                    "/exporters",
                    headers={"X-Development-Tenant-ID": str(
                        TENANT_A_ID)},
                    json={"legal_name": "Acme"},
                )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"],
                         "development_tenant_context_disabled")


class DevelopmentHeaderRejectionTests(unittest.TestCase):
    def test_development_pathway_still_available_outside_production(
            self):
        with patched_env(APP_ENV=None):
            context = get_development_tenant_context(str(TENANT_A_ID))
            self.assertEqual(context, TENANT_A)
            member = get_member_context(
                None, None, None, str(TENANT_A_ID))
            self.assertEqual(member.tenant, TENANT_A)
            self.assertEqual(member.role, "owner")

    def test_development_context_rejected_in_production(self):
        with patched_env(APP_ENV="production"):
            with self.assertRaises(APIError) as raised:
                get_development_tenant_context(str(TENANT_A_ID))
            self.assertEqual(raised.exception.status_code, 503)
            self.assertEqual(raised.exception.code,
                             "development_tenant_context_disabled")

    def test_member_context_rejects_dev_header_in_production(self):
        with patched_env(APP_ENV="production"):
            with self.assertRaises(APIError) as raised:
                get_member_context(
                    None, None, None, str(TENANT_A_ID))
            self.assertEqual(raised.exception.code,
                             "development_tenant_context_disabled")

    def test_member_context_rejects_dev_header_even_with_bearer(
            self):
        # G1 regression: the header must not be silently ignored
        # when Authorization is also present in production.
        with patched_env(APP_ENV="production"):
            with self.assertRaises(APIError) as raised:
                get_member_context(
                    None, "Bearer anything", None, str(TENANT_A_ID))
            self.assertEqual(raised.exception.status_code, 503)
            self.assertEqual(raised.exception.code,
                             "development_tenant_context_disabled")

    def test_request_actor_rejects_dev_header_in_production(self):
        with patched_env(APP_ENV="production"):
            with self.assertRaises(APIError) as raised:
                get_request_actor(None, str(TENANT_A_ID))
            self.assertEqual(raised.exception.code,
                             "development_tenant_context_disabled")

    def test_request_body_cannot_carry_tenant_identity(self):
        # extra="forbid" schemas reject injected tenant selection.
        with patched_env(APP_ENV=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.post(
                    "/exporters",
                    headers={"X-Development-Tenant-ID": str(
                        TENANT_A_ID)},
                    json={"legal_name": "Acme",
                          "tenant_id": str(TENANT_B_ID)},
                )
                workflow = client.post(
                    "/compliance/workflows/start",
                    headers={"X-Development-Tenant-ID": str(
                        TENANT_A_ID)},
                    json={"case_id": str(CASE_A),
                          "tenant_id": str(TENANT_B_ID)},
                )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(workflow.status_code, 422)


class AuthorizationPolicyTests(unittest.TestCase):
    def test_owner_may_progress_and_analyze(self):
        member = MemberContext(TENANT_A, "owner")
        self.assertIs(
            authorize(member, PROGRESS_COMPLIANCE_WORKFLOW), member)
        self.assertIs(
            authorize(member, RUN_COMPLIANCE_ANALYSIS), member)

    def test_member_is_denied_workflow_and_analysis(self):
        member = MemberContext(TENANT_A, "member")
        for permission in (PROGRESS_COMPLIANCE_WORKFLOW,
                           RUN_COMPLIANCE_ANALYSIS):
            with self.subTest(permission=permission):
                with self.assertRaises(PermissionDeniedError):
                    authorize(member, permission)

    def test_member_keeps_read_and_evidence_permissions(self):
        member = MemberContext(TENANT_A, "member")
        for permission in (READ_TENANT_RESOURCE,
                           CREATE_COMPLIANCE_EVIDENCE,
                           ASSOCIATE_EVIDENCE_REQUIREMENT):
            with self.subTest(permission=permission):
                self.assertIs(authorize(member, permission), member)

    def test_unknown_role_is_denied_everything(self):
        member = MemberContext(TENANT_A, "auditor")
        for permission in (READ_TENANT_RESOURCE,
                           CREATE_COMPLIANCE_EVIDENCE,
                           PROGRESS_COMPLIANCE_WORKFLOW,
                           RUN_COMPLIANCE_ANALYSIS):
            with self.subTest(permission=permission):
                with self.assertRaises(PermissionDeniedError):
                    authorize(member, permission)


class TenantIsolationMatrixTests(unittest.TestCase):
    def test_cross_tenant_workflow_operations_fail_closed(self):
        record = start_record(CTX_A)
        operations = [
            lambda: WORKFLOWS.provide_information(CTX_B, record),
            lambda: WORKFLOWS.get_workflow(CTX_B, record),
            lambda: WORKFLOWS.get_history(CTX_B, record),
            lambda: WORKFLOWS.is_closed(CTX_B, record),
            lambda: WORKFLOWS.supply_evidence(
                CTX_B, record, EVIDENCE_A),
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(TenantMismatchError):
                    operation()

    def test_cross_tenant_analysis_is_rejected_before_any_call(self):
        service = AnalysisApplicationService(
            rag_service=SimpleNamespace(
                query=lambda *args, **kwargs: None))
        record = start_record(CTX_A)
        with self.assertRaises(TenantMismatchError):
            service.run_analysis(CTX_B, record, [])

    def test_cross_tenant_evidence_read_fails_closed(self):
        class LeakingDomainEvidence:
            def record(self, *args, **kwargs):
                raise AssertionError("must not record")

            def get(self, tenant, evidence_id):
                # Misbehaving lower layer returns another tenant's row;
                # the application boundary must still refuse it.
                return {"id": evidence_id, "tenant_id": TENANT_A_ID,
                        "document_title": "t", "document_type": "d",
                        "file_reference_or_uri": "u",
                        "source_id": None, "content_hash": None,
                        "status": "uploaded"}

        service = EvidenceApplicationService(
            evidence_service=LeakingDomainEvidence())
        with self.assertRaises(TenantMismatchError):
            service.get_evidence(CTX_B, EVIDENCE_A)

    def test_unknown_tenant_evidence_read_does_not_leak(self):
        class ScopedDomainEvidence:
            def record(self, *args, **kwargs):
                raise AssertionError("must not record")

            def get(self, tenant, evidence_id):
                return None

        service = EvidenceApplicationService(
            evidence_service=ScopedDomainEvidence())
        with self.assertRaises(ApplicationNotFoundError):
            service.get_evidence(CTX_B, EVIDENCE_A)

    def test_evidence_recording_uses_context_tenant(self):
        captured = {}

        class CapturingDomainEvidence:
            def record(self, tenant, *args, **kwargs):
                captured["tenant"] = tenant
                return {"id": EVIDENCE_A, "tenant_id": tenant.tenant_id,
                        "document_title": "t", "document_type": "d",
                        "file_reference_or_uri": "u",
                        "source_id": None, "content_hash": None,
                        "status": "uploaded"}

            def get(self, tenant, evidence_id):
                raise AssertionError("must not read")

        service = EvidenceApplicationService(
            evidence_service=CapturingDomainEvidence())
        service.record_evidence(
            CTX_B, document_title="t", document_type="d",
            file_reference_or_uri="u")
        self.assertEqual(captured["tenant"], TENANT_B)

    def test_cross_tenant_stored_report_read_fails_closed(self):
        store = _scoped_result_store()
        with self.assertRaises(ApplicationNotFoundError):
            store.load_result(CTX_B, REPORT_A)
        result = store.load_result(CTX_A, REPORT_A)
        self.assertEqual(result.tenant_id, TENANT_A_ID)

    def test_mixed_tenant_stored_rows_fail_closed(self):
        report_row, analysis_rows, trace_rows = _stored_rows()
        tampered = [dict(analysis_rows[0], tenant_id=TENANT_B_ID)]
        with self.assertRaises(ApplicationValidationError):
            rebuild_result(report_row, tampered, trace_rows)

    def test_cross_tenant_stored_package_paths_fail_closed(self):
        service = WorkflowApplicationService(
            result_store=_unreachable_store())
        record = start_record(CTX_A)
        with self.assertRaises(TenantMismatchError):
            service.get_stored_package(CTX_B, record)
        with self.assertRaises(TenantMismatchError):
            service.finalize_stored_package(CTX_B, record)
        with self.assertRaises(TenantMismatchError):
            service.load_current_result(CTX_B, record)


class FinalizedWorkflowProtectionTests(unittest.TestCase):
    def test_closed_workflow_rejects_mutation_but_allows_reads(self):
        record = closed_record()
        self.assertTrue(WORKFLOWS.is_closed(CTX_A, record))
        self.assertIsNotNone(WORKFLOWS.get_workflow(CTX_A, record))
        self.assertIsNotNone(WORKFLOWS.get_history(CTX_A, record))
        for operation in (
            lambda: WORKFLOWS.provide_information(CTX_A, record),
            lambda: WORKFLOWS.supply_evidence(
                CTX_A, record, EVIDENCE_A),
        ):
            with self.assertRaises(TerminalWorkflowError):
                operation()

    def test_closed_workflow_stays_isolated_across_tenants(self):
        record = closed_record()
        with self.assertRaises(TenantMismatchError):
            WORKFLOWS.is_closed(CTX_B, record)
        with self.assertRaises(TenantMismatchError):
            WORKFLOWS.provide_information(CTX_B, record)


class ProductionErrorSurfaceTests(unittest.TestCase):
    def test_unexpected_errors_are_generic(self):
        response = asyncio.run(_handle_unexpected_error(
            None, RuntimeError("DATABASE_URL=secret db exploded")))
        self.assertEqual(response.status_code, 500)
        body = _body(response)
        self.assertEqual(body["error"]["code"], "internal_error")
        self.assertNotIn("secret", body["error"]["message"])

    def test_production_5xx_details_are_stripped(self):
        error = InfrastructureError(
            "DomainPersistenceError: duplicate key violates unique "
            'constraint "compliance_analysis_reports_pkey"')
        with patched_env(APP_ENV="production"):
            response = asyncio.run(
                _handle_application_error(None, error))
        self.assertEqual(response.status_code, 503)
        body = _body(response)
        self.assertEqual(body["error"]["code"],
                         "infrastructure_failure")
        self.assertNotIn("compliance_analysis_reports", str(body))
        self.assertNotIn("duplicate key", str(body))

    def test_development_keeps_diagnostic_details(self):
        error = InfrastructureError("operational detail")
        with patched_env(APP_ENV=None):
            response = asyncio.run(
                _handle_application_error(None, error))
        body = _body(response)
        self.assertEqual(body["error"]["code"],
                         "infrastructure_failure")
        self.assertIn("operational detail",
                      body["error"]["message"])

    def test_structured_4xx_semantics_survive_in_production(self):
        with patched_env(APP_ENV="production"):
            mismatch = asyncio.run(_handle_application_error(
                None, TenantMismatchError(
                    "workflow belongs to a different tenant")))
            not_ready = asyncio.run(_handle_application_error(
                None, WorkflowNotReadyError(
                    "workflow is not ready",
                    reasons=(("missing_shipment_reference", "bind one"),))))
        mismatch_body = _body(mismatch)
        self.assertEqual(mismatch.status_code, 403)
        self.assertEqual(mismatch_body["error"]["code"],
                         "tenant_mismatch")
        not_ready_body = _body(not_ready)
        self.assertEqual(not_ready.status_code, 409)
        self.assertEqual(not_ready_body["error"]["code"], "not_ready")
        self.assertEqual(
            not_ready_body["error"]["details"]["reasons"],
            [{"code": "missing_shipment_reference",
              "detail": "bind one"}])


class LoggingAndSecretsTests(unittest.TestCase):
    def test_secret_holders_exclude_credentials_from_repr(self):
        from xportra.infrastructure.llm import LLMSettings
        from xportra.infrastructure.rag_composition import (
            RAGInfrastructureConfig,
        )
        settings = LLMSettings(
            api_key="super-secret-key", model_identifier="model")
        self.assertNotIn("super-secret-key", repr(settings))
        config = RAGInfrastructureConfig.from_environment({
            "VECTOR_STORE_URL": "http://localhost:6333",
            "VECTOR_STORE_COLLECTION": "collection",
            "EMBEDDING_MODEL": "model",
            "EMBEDDING_DIMENSIONS": "4",
            "LLM_API_KEY": "super-secret-key",
            "LLM_MODEL": "model",
        })
        self.assertNotIn("super-secret-key", repr(config))

    def test_rag_composition_logs_carry_no_secrets(self):
        from xportra.infrastructure.rag_composition import (
            RAGInfrastructureConfig,
            compose_rag_stack,
        )
        config = RAGInfrastructureConfig.from_environment({
            "VECTOR_STORE_URL": "http://localhost:6333",
            "VECTOR_STORE_COLLECTION": "collection",
            "EMBEDDING_MODEL": "model",
            "EMBEDDING_DIMENSIONS": "4",
            "LLM_API_KEY": "super-secret-key",
            "LLM_MODEL": "model",
        })
        with self.assertLogs("xportra.infrastructure.rag_composition",
                             level="INFO") as captured:
            compose_rag_stack(
                config,
                embedding_provider=SimpleNamespace(
                    embed=lambda text: [0.0] * 4),
                llm_client=SimpleNamespace(
                    generate=lambda *args, **kwargs: None),
            )
        self.assertNotIn("super-secret-key",
                         "\n".join(captured.output))
        self.assertNotIn("localhost:6333",
                         "\n".join(captured.output))


class ConfigurationHygieneTests(unittest.TestCase):
    def test_example_configuration_holds_placeholders_only(self):
        from pathlib import Path
        values = {}
        for line in (Path(__file__).resolve().parents[2]
                     / ".env.example").read_text(
                         encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
        for name, value in values.items():
            self.assertNotIn("sk-", value,
                             f"{name} looks like a real secret")
            self.assertNotIn("eyJ", value,
                             f"{name} looks like a real token")
        for name in ("SUPABASE_JWT_SECRET", "LLM_API_KEY",
                     "DATABASE_URL"):
            self.assertEqual(values[name], "",
                             f"{name} must be empty in the example")

    def test_application_source_holds_no_embedded_secrets(self):
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parents[2] / "xportra"
        pattern = re.compile(
            r"BEGIN [A-Z ]*PRIVATE KEY|"
            r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{16,}|"
            r"xox[bap]-|ghp_[A-Za-z0-9]+|"
            r"AKIA[0-9A-Z]{16}")
        hits = [str(path) for path in root.rglob("*.py")
                if pattern.search(
                    path.read_text(encoding="utf-8"))]
        self.assertEqual(hits, [])


def _body(response):
    import json
    return json.loads(bytes(response.body).decode("utf-8"))


def _stored_rows():
    analysis_row = {
        "id": ANALYSIS_A,
        "tenant_id": TENANT_A_ID,
        "requirement_id": REQUIREMENT_A,
        "requirement_text": "File the form.",
        "applicability": "applicable",
        "assessment": "satisfied",
        "explanation": "Evidence supports the requirement.",
        "supporting_evidence": [],
        "conflicting_evidence": [],
        "knowledge_references": [],
        "sources": [],
        "missing_information": [],
        "uncertainty": "certain",
        "uncertainty_explanation": "",
        "evidence_sufficiency": "supported",
        "contradiction_state": "none",
        "sufficiency_explanation": "Supported by evidence.",
        "missing_items": [],
    }
    report_row = {
        "id": REPORT_A,
        "tenant_id": TENANT_A_ID,
        "case_id": CASE_A,
        "context_fingerprint": "fp",
        "total_requirements": 1,
        "applicable_count": 1,
        "satisfied_count": 1,
        "not_satisfied_count": 0,
        "unknown_count": 0,
        "not_applicable_count": 0,
        "requirements_with_missing_information": [],
        "missing_information": [],
        "uncertain_requirement_ids": [],
        "requirements_with_conflicting_evidence": [],
        "conflicting_evidence_count": 0,
        "decision_summary": None,
    }
    return report_row, [analysis_row], []


class _ScopedRepository:
    """Tenant-scoped in-memory double honoring the repository contract."""

    def __init__(self, rows):
        self._rows = rows

    def create_in_transaction(self, *args, **kwargs):
        raise AssertionError("writes are out of scope here")

    def get(self, tenant, identity):
        for row in self._rows:
            if (row["id"] == identity
                    and row["tenant_id"] == tenant.tenant_id):
                return row
        return None

    def list_for_report(self, tenant, report_id):
        return [row for row in self._rows
                if row.get("report_id", report_id) == report_id
                and row["tenant_id"] == tenant.tenant_id]


def _scoped_result_store():
    report_row, analysis_rows, _ = _stored_rows()
    for row in analysis_rows:
        row["report_id"] = REPORT_A
    return ComplianceResultStore(
        database=SimpleNamespace(
            transaction=lambda: _null_transaction()),
        reports=_ScopedRepository([report_row]),
        analyses=_ScopedRepository(analysis_rows),
        traces=_ScopedRepository([]),
        rounds=_ScopedRepository([]),
        packages=_ScopedRepository([]),
    )


@contextmanager
def _null_transaction():
    yield SimpleNamespace()


def _unreachable_store():
    def _unreachable(*args, **kwargs):
        raise AssertionError("result store must not be reached")

    return SimpleNamespace(
        load_result=_unreachable,
        store_package_linkage=_unreachable,
        load_package=_unreachable,
        rounds_for_workflow=_unreachable,
        latest_round_for_workflow=_unreachable,
        store_analysis_result=_unreachable)


if __name__ == "__main__":
    unittest.main()
