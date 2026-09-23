"""Phase 5.13 — RAG Application/API Boundary tests.

Covers the thin production-facing request/response boundary over the
completed Phase 5 chain:

    HTTP Request -> RAGApplicationService -> HTTP Response

Deterministic fakes only — no live Qdrant, no live LLM provider, no
network, no credentials. The prompt builder and answer validator used
below are the REAL Phase 5.10/5.12 boundaries; only the context
pipeline (retrieval side) and the LLM client (provider side) are
faked, so orchestration forwarding is observable at both seams.
"""

import ast
import json
import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.domain.answer_validation import (
    AnswerValidationError,
    CitationAwareAnswerValidator,
)
from xportra.domain.errors import (
    DomainValidationError,
    LLMProviderError,
    VectorStoreError,
)
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
)
from xportra.domain.evidence_hybrid import HybridRetrievalCandidate
from xportra.domain.evidence_prompt import (
    CitationAwarePromptBuilder,
    EvidencePrompt,
    EvidencePromptConfig,
)
from xportra.domain.evidence_ranking import DeterministicEvidenceRanker
from xportra.domain.evidence_retrieval import (
    DEFAULT_TOP_K,
    EvidenceRetrievalResult,
    EvidenceRetrievalScope,
)
from xportra.domain.llm import LLMGenerationConfig, LLMResponse
from xportra.domain.rag_application import (
    RAGApplicationService,
    build_rag_application_service,
)
from xportra.persistence.tenant import TenantContext

TENANT_A_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT_A = TenantContext(TENANT_A_ID)
HEADER_A = {"X-Development-Tenant-ID": str(TENANT_A_ID)}
HEADER_B = {"X-Development-Tenant-ID": str(TENANT_B_ID)}

CHUNK_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
SERVER_MODEL = "server-configured-model"
PROVIDER_SECRET_SENTINEL = "sk-secret-that-must-never-leak-0123456789"

PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="You are a compliance assistant. Answer only from the evidence."
)
GEN_CONFIG = LLMGenerationConfig(
    model_identifier=SERVER_MODEL, temperature=0.0, max_output_tokens=256
)


def make_evidence(**overrides):
    kwargs = dict(
        tenant_id=TENANT_A_ID,
        chunk_id=CHUNK_ID,
        document_id=DOCUMENT_ID,
        chunk_index=0,
        content="Exporters must file Form NXP before shipment.",
        content_fingerprint="fp-1",
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


def make_selection(contents=("Exporters must file Form NXP before shipment.",)):
    candidates = []
    for i, text in enumerate(contents):
        if i == 0:
            evidence = make_evidence(content=text)
        else:
            evidence = make_evidence(
                content=text,
                chunk_id=UUID(f"cccccccc-cccc-cccc-cccc-ccccccccc{i:03d}"),
                content_fingerprint=f"fp-other-{i}",
                score=0.9 - i * 0.1,
            )
        candidates.append(
            HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=0.9 - i * 0.1,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}),
            )
        )
    ranked = DeterministicEvidenceRanker().rank(candidates, top_k=len(candidates))
    return DeterministicContextSelector().select(
        ranked, tenant_id=TENANT_A, budget=EvidenceContextBudget(4000)
    )


def make_response(text="File Form NXP before shipment [E1]."):
    return LLMResponse(
        generated_text=text,
        model_identifier=SERVER_MODEL,
        finish_reason="stop",
        usage=None,
        provider_name="test-provider",
    )


class FakeContextPipeline:
    """Deterministic stand-in for the Phase 5.8 context pipeline."""

    def __init__(self, selection=None, failure=None):
        self._selection = selection
        self._failure = failure
        self.calls = []

    def select_context(
        self,
        information_need,
        *,
        tenant_id,
        mode,
        context_budget,
        scope=None,
        top_k=DEFAULT_TOP_K,
        candidate_pool=None,
    ):
        self.calls.append(
            {
                "information_need": information_need,
                "tenant_id": tenant_id,
                "mode": mode,
                "context_budget": context_budget,
                "scope": scope,
                "top_k": top_k,
                "candidate_pool": candidate_pool,
            }
        )
        if self._failure is not None:
            raise self._failure
        return self._selection


class FakeLLMClient:
    """Deterministic stand-in for the Phase 5.11 LLM client."""

    def __init__(self, responses=None, failure=None):
        self._responses = list(responses or [])
        self._failure = failure
        self.calls = []

    def generate(self, prompt, *, configuration, tenant_id=None):
        self.calls.append(
            {
                "prompt": prompt,
                "configuration": configuration,
                "tenant_id": tenant_id,
            }
        )
        if self._failure is not None:
            raise self._failure
        return self._responses.pop(0)


class SpyValidator:
    """Records the generated answer, then delegates to the real validator."""

    def __init__(self, delegate=None):
        self.delegate = delegate or CitationAwareAnswerValidator()
        self.calls = []

    def validate(self, answer):
        self.calls.append(answer)
        return self.delegate.validate(answer)


def make_service(
    pipeline=None,
    llm=None,
    validator=None,
    selection_contents=(
        "Exporters must file Form NXP before shipment.",
    ),
    response_text="File Form NXP before shipment [E1].",
):
    pipeline = pipeline or FakeContextPipeline(
        selection=make_selection(selection_contents)
    )
    llm = llm or FakeLLMClient(responses=[make_response(response_text)])
    validator = validator or CitationAwareAnswerValidator()
    service = RAGApplicationService(
        context_pipeline=pipeline,
        prompt_builder=CitationAwarePromptBuilder(config=PROMPT_CONFIG),
        llm_client=llm,
        llm_generation_config=GEN_CONFIG,
        answer_validator=validator,
    )
    return service, pipeline, llm, validator


def client_for(rag_service, raise_server_exceptions=True):
    return TestClient(
        create_app(services=SimpleNamespace(rag=rag_service)),
        raise_server_exceptions=raise_server_exceptions,
    )


class RAGRequestValidationTests(unittest.TestCase):
    def test_valid_minimal_request_returns_validated_answer(self):
        service, _, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "When must Form NXP be filed?"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "valid")
        self.assertFalse(body["is_empty"])
        self.assertEqual(
            body["answer_text"], "File Form NXP before shipment [E1]."
        )

    def test_missing_information_need_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query", headers=HEADER_A, json={}
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_empty_information_need_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": ""},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_whitespace_information_need_fails_closed_at_domain(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "   "},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "domain_validation_error"
        )
        self.assertEqual(pipeline.calls, [])

    def test_malformed_information_need_type_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": 123},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_invalid_mode_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need", "mode": "neural"},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_invalid_top_k_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            zero = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need", "top_k": 0},
            )
            negative = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need", "top_k": -3},
            )
            boolean = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need", "top_k": True},
            )
        self.assertEqual(zero.status_code, 422)
        self.assertEqual(negative.status_code, 422)
        self.assertEqual(boolean.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_invalid_budget_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need", "max_context_characters": 0},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_oversized_information_need_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "x" * 4001},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_unknown_scope_dimension_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={
                    "information_need": "need",
                    "scope": {"jurisdiction": "NG"},
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_invalid_scope_value_fails_closed_at_domain(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={
                    "information_need": "need",
                    "scope": {"source_type": "not-a-real-type"},
                },
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(pipeline.calls, [])


class RAGTenantSecurityTests(unittest.TestCase):
    def test_authenticated_tenant_reaches_service(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pipeline.calls[0]["tenant_id"], TENANT_A)

    def test_different_authenticated_tenant_reaches_service(self):
        selection_b = make_selection()
        pipeline = FakeContextPipeline(selection=selection_b)
        service, _, _, _ = make_service(pipeline=pipeline)
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_B,
                json={"information_need": "need"},
            )
        # The fake returns tenant-A evidence regardless; what matters
        # is the tenant forwarded came from the header, not the body.
        self.assertEqual(
            pipeline.calls[0]["tenant_id"],
            TenantContext(TENANT_B_ID),
        )
        self.assertNotEqual(
            pipeline.calls[0]["tenant_id"], TENANT_A
        )
        self.assertEqual(response.status_code, 200)

    def test_tenant_id_in_body_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={
                    "information_need": "need",
                    "tenant_id": str(TENANT_B_ID),
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_tenant_id_in_scope_is_rejected(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={
                    "information_need": "need",
                    "scope": {"tenant_id": str(TENANT_B_ID)},
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(pipeline.calls, [])

    def test_missing_tenant_context_fails_closed(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query", json={"information_need": "need"}
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["error"]["code"], "authentication_required"
        )
        self.assertEqual(pipeline.calls, [])

    def test_cross_tenant_domain_failure_remains_rejected(self):
        pipeline = FakeContextPipeline(
            failure=DomainValidationError("cross-tenant access denied")
        )
        service, _, _, _ = make_service(pipeline=pipeline)
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 409)
        rendered = response.text.lower()
        self.assertNotIn(str(TENANT_A_ID), rendered)
        self.assertNotIn(str(TENANT_B_ID), rendered)


class RAGOrchestrationTests(unittest.TestCase):
    def test_context_pipeline_called_once(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(pipeline.calls), 1)

    def test_information_need_forwarded_normalized(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "  Form   NXP\ndeadline?  "},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            pipeline.calls[0]["information_need"], "Form NXP deadline?"
        )

    def test_mode_budget_top_k_candidate_pool_scope_forwarded(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={
                    "information_need": "need",
                    "mode": "semantic",
                    "max_context_characters": 1500,
                    "top_k": 3,
                    "candidate_pool": 9,
                    "scope": {
                        "source_id": "sonsa/cert-guide",
                        "document_version": "2024.1",
                    },
                },
            )
        self.assertEqual(response.status_code, 200)
        call = pipeline.calls[0]
        self.assertEqual(call["mode"], "semantic")
        self.assertIsInstance(call["context_budget"], EvidenceContextBudget)
        self.assertEqual(call["context_budget"].max_characters, 1500)
        self.assertEqual(call["top_k"], 3)
        self.assertEqual(call["candidate_pool"], 9)
        self.assertEqual(
            call["scope"],
            EvidenceRetrievalScope(
                source_id="sonsa/cert-guide",
                document_version="2024.1",
            ),
        )

    def test_scope_defaults_to_none(self):
        service, pipeline, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(pipeline.calls[0]["scope"])

    def test_llm_receives_authoritative_structured_prompt(self):
        service, pipeline, llm, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "Form NXP deadline"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(llm.calls), 1)
        prompt = llm.calls[0]["prompt"]
        self.assertIsInstance(prompt, EvidencePrompt)
        self.assertEqual(prompt.information_need, "Form NXP deadline")
        self.assertEqual(
            [c.label for c in prompt.citations], ["[E1]"]
        )
        # Server-side generation config — never caller-controlled.
        self.assertEqual(
            llm.calls[0]["configuration"], GEN_CONFIG
        )
        self.assertEqual(
            llm.calls[0]["configuration"].model_identifier, SERVER_MODEL
        )
        self.assertEqual(llm.calls[0]["tenant_id"], TENANT_A)

    def test_validator_receives_generated_answer(self):
        expected = make_response()
        llm = FakeLLMClient(responses=[expected])
        spy = SpyValidator()
        service, _, _, _ = make_service(llm=llm, validator=spy)
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(spy.calls), 1)
        answer = spy.calls[0]
        self.assertIs(answer.prompt, llm.calls[0]["prompt"])
        self.assertIs(answer.response, expected)
        self.assertEqual(
            answer.answer_text, "File Form NXP before shipment [E1]."
        )

    def test_request_cannot_override_generation_config(self):
        service, _, llm, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={
                    "information_need": "need",
                    "model_identifier": "attacker-model",
                    "temperature": 1.9,
                    "api_key": PROVIDER_SECRET_SENTINEL,
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(llm.calls, [])

    def test_dependencies_are_injectable_via_builder(self):
        pipeline = FakeContextPipeline(selection=make_selection())
        llm = FakeLLMClient(responses=[make_response()])
        service = build_rag_application_service(
            context_pipeline=pipeline,
            prompt_config=PROMPT_CONFIG,
            llm_client=llm,
            llm_generation_config=GEN_CONFIG,
        )
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "valid")


class RAGSuccessTests(unittest.TestCase):
    def test_citations_preserved_from_authoritative_mapping(self):
        service, _, _, _ = make_service(
            selection_contents=(
                "Exporters must file Form NXP before shipment.",
                "Certificates need SONCAP clearance.",
            ),
            response_text="File first [E1], then clear [E2].",
        )
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["extracted_references"], ["[E1]", "[E2]"])
        self.assertEqual(body["invalid_references"], [])
        self.assertEqual(
            [(c["label"], c["rank_position"]) for c in body["citations"]],
            [("[E1]", 1), ("[E2]", 2)],
        )

    def test_provenance_preserved_without_internals(self):
        service, _, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        evidence = response.json()["citations"][0]["evidence"]
        self.assertEqual(evidence["chunk_id"], str(CHUNK_ID))
        self.assertEqual(evidence["document_id"], str(DOCUMENT_ID))
        self.assertEqual(evidence["source_id"], "sonsa/cert-guide")
        self.assertEqual(evidence["source_type"], "guidance")
        self.assertEqual(
            evidence["source_location"], "https://example.test/guide"
        )
        self.assertEqual(evidence["document_version"], "2024.1")
        self.assertEqual(evidence["content_fingerprint"], "fp-1")
        self.assertNotIn("tenant_id", evidence)
        self.assertNotIn("content", evidence)
        self.assertNotIn("score", evidence)
        self.assertNotIn("embedding_model", evidence)

    def test_empty_answer_represented_correctly(self):
        service, _, _, _ = make_service(response_text="   ")
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need with no evidence"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "empty")
        self.assertTrue(body["is_empty"])
        self.assertEqual(body["answer_text"], "   ")
        self.assertEqual(body["citations"], [])

    def test_structured_invalid_citations_status_preserved(self):
        pipeline = FakeContextPipeline(selection=make_selection())
        llm = FakeLLMClient(responses=[make_response("See [E9].")])
        service, _, _, _ = make_service(
            pipeline=pipeline,
            llm=llm,
            validator=CitationAwareAnswerValidator(
                fail_on_invalid_citations=False
            ),
        )
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "invalid_citations")
        self.assertEqual(body["invalid_references"], ["[E9]"])
        self.assertEqual(body["citations"], [])


class RAGFailureMappingTests(unittest.TestCase):
    def test_retrieval_failure_is_not_a_success(self):
        pipeline = FakeContextPipeline(
            failure=VectorStoreError("find", RuntimeError("index down"))
        )
        service, _, _, _ = make_service(pipeline=pipeline)
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "vector_store_error"
        )

    def test_llm_provider_failure_is_not_a_success(self):
        llm = FakeLLMClient(
            failure=LLMProviderError(
                "generate", RuntimeError("provider timeout")
            )
        )
        service, _, _, _ = make_service(llm=llm)
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "llm_provider_error"
        )
        rendered = response.text.lower()
        self.assertNotIn("timeout", rendered)

    def test_llm_auth_provider_failure_maps_without_details(self):
        llm = FakeLLMClient(
            failure=LLMProviderError(
                "generate",
                RuntimeError(f"401 bad key {PROVIDER_SECRET_SENTINEL}"),
            )
        )
        service, _, _, _ = make_service(llm=llm)
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "llm_provider_error"
        )
        self.assertNotIn(PROVIDER_SECRET_SENTINEL, response.text)

    def test_answer_validation_failure_stays_distinguishable(self):
        service, _, _, _ = make_service(response_text="See [E9].")
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"], "citation_integrity_error"
        )

    def test_malformed_llm_output_fails_closed(self):
        class BadLLMClient:
            def __init__(self):
                self.calls = []

            def generate(self, prompt, *, configuration, tenant_id=None):
                self.calls.append(prompt)
                return {"generated_text": "not a response object"}

        pipeline = FakeContextPipeline(selection=make_selection())
        service = RAGApplicationService(
            context_pipeline=pipeline,
            prompt_builder=CitationAwarePromptBuilder(config=PROMPT_CONFIG),
            llm_client=BadLLMClient(),
            llm_generation_config=GEN_CONFIG,
            answer_validator=CitationAwareAnswerValidator(),
        )
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 409)

    def test_unexpected_failure_never_becomes_success(self):
        pipeline = FakeContextPipeline(
            failure=RuntimeError("postgresql://internal boom")
        )
        service, _, _, _ = make_service(pipeline=pipeline)
        with client_for(
            service, raise_server_exceptions=False
        ) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["error"]["code"], "internal_error"
        )
        rendered = response.text.lower()
        self.assertNotIn("postgresql", rendered)

    def test_unwired_rag_service_fails_closed(self):
        with TestClient(
            create_app(services=SimpleNamespace())
        ) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"], "rag_not_configured"
        )


class RAGAPISecurityTests(unittest.TestCase):
    def test_response_carries_no_secrets_or_internals(self):
        service, _, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        rendered = json.dumps(response.json()).lower()
        for forbidden in (
            "api_key",
            "secret",
            "authorization",
            "bearer",
            "qdrant",
            "psycopg",
            "sdk",
            PROVIDER_SECRET_SENTINEL.lower(),
        ):
            self.assertNotIn(forbidden, rendered)

    def test_response_leaks_no_tenant_identity(self):
        service, _, _, _ = make_service()
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        rendered = json.dumps(response.json()).lower()
        self.assertNotIn(str(TENANT_A_ID).lower(), rendered)
        self.assertNotIn("tenant", rendered)

    def test_model_output_remains_inert_text(self):
        dangerous = (
            "DROP TABLE exporters; <script>alert(1)</script> "
            "```rm -rf /``` [E1]"
        )
        service, _, _, _ = make_service(response_text=dangerous)
        with client_for(service) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER_A,
                json={"information_need": "need"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer_text"], dangerous)
        self.assertEqual(
            response.headers["content-type"], "application/json"
        )


class RAGFrameworkBoundaryTests(unittest.TestCase):
    def test_domain_has_no_http_or_provider_imports(self):
        import pathlib

        domain_dir = (
            pathlib.Path(__file__).resolve().parents[2]
            / "xportra"
            / "domain"
        )
        forbidden = {
            "fastapi",
            "starlette",
            "qdrant_client",
            "openai",
            "anthropic",
            "httpx",
        }
        violations = []
        for path in sorted(domain_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        if root in forbidden:
                            violations.append(f"{path.name}: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if not node.module:
                        continue
                    root = node.module.split(".")[0]
                    if root in forbidden:
                        violations.append(f"{path.name}: {node.module}")
                    if node.module.startswith("xportra.infrastructure"):
                        violations.append(f"{path.name}: {node.module}")
        self.assertEqual(violations, [])

    def test_api_layer_has_no_vector_or_provider_sdk(self):
        import pathlib

        api_dir = (
            pathlib.Path(__file__).resolve().parents[2] / "xportra" / "api"
        )
        forbidden_roots = {"qdrant_client", "openai", "anthropic"}
        violations = []
        for path in sorted(api_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in forbidden_roots:
                            violations.append(
                                f"{path.name}: {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module and (
                        node.module.split(".")[0] in forbidden_roots
                        or node.module.startswith("xportra.infrastructure")
                    ):
                        violations.append(f"{path.name}: {node.module}")
            for marker in ("QdrantClient", "OpenAI(", "Anthropic("):
                if marker in text:
                    violations.append(f"{path.name}: {marker}")
        self.assertEqual(violations, [])

    def test_service_contract_stays_http_free(self):
        import inspect

        import xportra.domain.rag_application as module

        source = inspect.getsource(module)
        for marker in ("fastapi", "starlette", "Request", "JSONResponse"):
            self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
