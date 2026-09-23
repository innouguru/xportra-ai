"""Phase 5.14 — Production RAG Composition & Infrastructure Wiring tests.

Covers the single explicit composition root
(``xportra.infrastructure.rag_composition``) that wires the
completed Phase 5 chain to real infrastructure classes:

- composition graph (real domain objects, real Qdrant adapter
  class, approved-baseline embedding implementation, injected LLM
  seam — no vendor adapter is vendored);
- configuration (one authoritative path, explicit failures,
  secret handling);
- deterministic end-to-end execution through HTTP with fake
  vector/embedding infrastructure (no live Qdrant, no live LLM,
  no model downloads);
- tenant isolation through real composition;
- failure semantics and security/observability boundaries.

The sentence-transformers model is NEVER loaded here: the provider
is exercised through its validation paths and a stub loader, and
the default provider is asserted to stay unloaded after
composition.
"""

import ast
import logging
import os
import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.dependencies import ApplicationServices
from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.errors import DomainValidationError, VectorStoreError
from xportra.domain.evidence_context import EvidenceContextBudget
from xportra.domain.evidence_context_pipeline import (
    EvidenceContextPipeline,
    build_evidence_context_pipeline,
)
from xportra.domain.evidence_indexing import EmbeddingModelConfig
from xportra.domain.evidence_pipeline import EvidenceRetrievalPipeline
from xportra.domain.evidence_prompt import (
    CitationAwarePromptBuilder,
    EvidencePromptConfig,
)
from xportra.domain.evidence_ranking import DeterministicEvidenceRanker
from xportra.domain.evidence_retrieval import (
    EvidenceRetrievalResult,
    VectorIndexEvidenceRetriever,
)
from xportra.domain.llm import LLMGenerationConfig, LLMResponse
from xportra.domain.rag_application import (
    RAGApplicationService,
    build_rag_application_service,
)
from xportra.infrastructure.llm import ScriptedLLMClient
from xportra.infrastructure.rag_composition import (
    RAGComposition,
    RAGConfigurationError,
    RAGInfrastructureConfig,
    SentenceTransformerEmbeddingProvider,
    compose_rag_stack,
    compose_rag_stack_from_environment,
)
from xportra.infrastructure.vector_index import QdrantEvidenceVectorIndex
from xportra.persistence.tenant import TenantContext

TENANT_A_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT_A = TenantContext(TENANT_A_ID)
TENANT_B = TenantContext(TENANT_B_ID)
HEADER_A = {"X-Development-Tenant-ID": str(TENANT_A_ID)}
HEADER_B = {"X-Development-Tenant-ID": str(TENANT_B_ID)}

CHUNK_A1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_A2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
CHUNK_B1 = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1")
DOC_A1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-bbbbbbbbbbb1")
DOC_A2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-bbbbbbbbbbb2")
DOC_B1 = UUID("bbbbbbbb-bbbb-bbbb-bbbb-aaaaaaaaaa01")

EMBEDDING_MODEL = "test-embed-model"
EMBEDDING_DIMENSIONS = 3
LLM_MODEL = "server-llm-model"
API_KEY_SENTINEL = "sk-test-sentinel-key-0000000000000000"
QDRANT_URL_SENTINEL = "http://sentinel-user:sentinel-pw-0000@localhost:6333"

RAG_ENV = {
    "VECTOR_STORE_URL": "http://localhost:6333",
    "VECTOR_STORE_COLLECTION": "xportra-test",
    "EMBEDDING_MODEL": EMBEDDING_MODEL,
    "EMBEDDING_DIMENSIONS": str(EMBEDDING_DIMENSIONS),
    "LLM_API_KEY": API_KEY_SENTINEL,
    "LLM_MODEL": LLM_MODEL,
}

PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="You are a compliance assistant."
)
GEN_CONFIG = LLMGenerationConfig(
    model_identifier=LLM_MODEL, temperature=0.0, max_output_tokens=128
)


def make_evidence(
    tenant_id,
    chunk_id,
    document_id,
    content,
    fingerprint,
    source_id="sonsa/cert-guide",
    version="2024.1",
    score=0.9,
):
    return EvidenceRetrievalResult(
        tenant_id=tenant_id,
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        content=content,
        content_fingerprint=fingerprint,
        source_id=source_id,
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version=version,
        embedding_model=EMBEDDING_MODEL,
        embedding_dimensions=EMBEDDING_DIMENSIONS,
        score=score,
    )


def evidence_a1():
    return make_evidence(
        TENANT_A_ID, CHUNK_A1, DOC_A1,
        "Exporters must file Form NXP before shipment.", "fp-a1",
    )


def evidence_a2():
    return make_evidence(
        TENANT_A_ID, CHUNK_A2, DOC_A2,
        "Certificates need SONCAP clearance.", "fp-a2",
        source_id="sonsa/soncap-guide", score=0.8,
    )


def evidence_b1():
    return make_evidence(
        TENANT_B_ID, CHUNK_B1, DOC_B1,
        "Tenant B private rule.", "fp-b1",
        source_id="other/source", score=0.9,
    )


class FakeEmbeddingProvider:
    """Deterministic EmbeddingProvider stand-in."""

    def __init__(self, failure=None):
        self._failure = failure
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        if self._failure is not None:
            raise self._failure
        return [0.5, 0.1, 0.9]


class FakeVectorIndex:
    """Deterministic tenant-scoped vector/lexical index stand-in.

    Applies tenant filtering first, then the requested scope —
    mirroring the real adapter's contract without any network.
    """

    def __init__(self, failure=None, cross_tenant=False, ignore_scope=False):
        self._failure = failure
        self._cross_tenant = cross_tenant
        self._ignore_scope = ignore_scope
        self.find_calls = []
        self.find_lexical_calls = []

    def _corpus(self):
        return [evidence_a1(), evidence_a2(), evidence_b1()]

    def find(self, query_vector, *, tenant_id, top_k, scope=None):
        self.find_calls.append(
            {
                "query_vector": list(query_vector),
                "tenant_id": tenant_id,
                "top_k": top_k,
                "scope": scope,
            }
        )
        if self._failure is not None:
            raise self._failure
        if self._cross_tenant:
            return [evidence_b1()]
        items = [
            item for item in self._corpus()
            if item.tenant_id == tenant_id.tenant_id
        ]
        if scope is not None and not self._ignore_scope:
            items = [item for item in items if scope.accepts(item)]
        return items[:top_k]

    def find_lexical(self, terms, *, tenant_id, top_k, scope=None):
        self.find_lexical_calls.append(
            {
                "terms": tuple(terms),
                "tenant_id": tenant_id,
                "top_k": top_k,
                "scope": scope,
            }
        )
        if self._failure is not None:
            raise self._failure
        if not terms:
            return []
        items = [
            item for item in self._corpus()
            if item.tenant_id == tenant_id.tenant_id
        ]
        if scope is not None and not self._ignore_scope:
            items = [item for item in items if scope.accepts(item)]
        if self._cross_tenant:
            return [evidence_b1()]
        return items[:1][:top_k]


def make_answer(text="File Form NXP before shipment [E1]."):
    return LLMResponse(
        generated_text=text,
        model_identifier=LLM_MODEL,
        finish_reason="stop",
        usage=None,
        provider_name="scripted-test-client",
    )


def make_e2e_service(
    index=None,
    embedder=None,
    llm=None,
    validator=None,
):
    """Real domain graph, deterministic fakes only at the infra seam."""
    index = index if index is not None else FakeVectorIndex()
    embedder = embedder if embedder is not None else FakeEmbeddingProvider()
    llm = llm if llm is not None else ScriptedLLMClient(
        responses=[make_answer()]
    )
    embedding_config = EmbeddingModelConfig(
        model_identifier=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    semantic = VectorIndexEvidenceRetriever(
        vector_index=index,
        provider=embedder,
        embedding_config=embedding_config,
    )
    context_pipeline = build_evidence_context_pipeline(
        semantic_retriever=semantic,
        lexical_index=index,
    )
    service = build_rag_application_service(
        context_pipeline=context_pipeline,
        prompt_config=PROMPT_CONFIG,
        llm_client=llm,
        llm_generation_config=GEN_CONFIG,
        answer_validator=validator or CitationAwareAnswerValidator(),
    )
    return service, index, embedder, llm


def client_for(rag_service, raise_server_exceptions=True):
    return TestClient(
        create_app(services=SimpleNamespace(rag=rag_service)),
        raise_server_exceptions=raise_server_exceptions,
    )


def post_query(client, headers=HEADER_A, **overrides):
    payload = {"information_need": "When must Form NXP be filed?"}
    payload.update(overrides)
    return client.post("/rag/query", headers=headers, json=payload)


class RAGCompositionGraphTests(unittest.TestCase):
    def test_compose_builds_real_graph_types(self):
        stack = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            embedding_provider=FakeEmbeddingProvider(),
            llm_client=ScriptedLLMClient(responses=[make_answer()]),
        )
        self.assertIsInstance(stack, RAGComposition)
        self.assertIsInstance(stack.service, RAGApplicationService)
        self.assertIsInstance(
            stack.vector_index, QdrantEvidenceVectorIndex
        )
        self.assertEqual(
            stack.vector_index.config.collection_name, "xportra-test"
        )
        self.assertIsInstance(
            stack.service._context_pipeline, EvidenceContextPipeline
        )
        self.assertIsInstance(
            stack.service._prompt_builder, CitationAwarePromptBuilder
        )
        self.assertIsInstance(
            stack.service._answer_validator, CitationAwareAnswerValidator
        )

    def test_single_index_serves_semantic_and_lexical_paths(self):
        stack = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            embedding_provider=FakeEmbeddingProvider(),
            llm_client=ScriptedLLMClient(responses=[make_answer()]),
        )
        pipeline = stack.service._context_pipeline._retrieval_pipeline
        self.assertIsInstance(pipeline, EvidenceRetrievalPipeline)
        hybrid = pipeline._hybrid_retriever
        self.assertIs(
            hybrid._semantic._vector_index, stack.vector_index
        )
        self.assertIs(hybrid._lexical, stack.vector_index)
        self.assertIsInstance(
            hybrid._semantic, VectorIndexEvidenceRetriever
        )
        self.assertIsInstance(
            pipeline._ranker, DeterministicEvidenceRanker
        )

    def test_default_embedding_provider_is_lazy_baseline(self):
        stack = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            llm_client=ScriptedLLMClient(responses=[make_answer()]),
        )
        self.assertIsInstance(
            stack.embedding_provider,
            SentenceTransformerEmbeddingProvider,
        )
        # Composed without downloading any model.
        self.assertFalse(stack.embedding_provider.is_loaded)

    def test_explicit_embedding_provider_is_used(self):
        embedder = FakeEmbeddingProvider()
        stack = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            embedding_provider=embedder,
            llm_client=ScriptedLLMClient(responses=[make_answer()]),
        )
        self.assertIs(stack.embedding_provider, embedder)

    def test_invalid_llm_client_fails_clearly(self):
        # Phase 5.15: a missing client now auto-builds the production
        # adapter; a non-client seam object still fails closed.
        config = RAGInfrastructureConfig.from_environment(dict(RAG_ENV))
        with self.assertRaises(RAGConfigurationError):
            compose_rag_stack(
                config,
                embedding_provider=FakeEmbeddingProvider(),
                llm_client=object(),
            )

    def test_invalid_config_type_fails_clearly(self):
        with self.assertRaises(RAGConfigurationError):
            compose_rag_stack(
                object(),
                embedding_provider=FakeEmbeddingProvider(),
                llm_client=ScriptedLLMClient(),
            )

    def test_recomposing_yields_independent_stacks(self):
        kwargs = dict(
            embedding_provider=FakeEmbeddingProvider(),
            llm_client=ScriptedLLMClient(responses=[make_answer()]),
        )
        first = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            **kwargs,
        )
        second = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            embedding_provider=FakeEmbeddingProvider(),
            llm_client=ScriptedLLMClient(responses=[make_answer()]),
        )
        self.assertIsNot(first.service, second.service)
        self.assertIsNot(first.vector_index, second.vector_index)

    def test_composition_module_has_no_http_imports(self):
        import pathlib

        path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "xportra"
            / "infrastructure"
            / "rag_composition.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        self.assertTrue(
            modules.isdisjoint({"fastapi", "starlette", "pydantic"})
        )


class RAGInfrastructureConfigTests(unittest.TestCase):
    def test_valid_environment_maps_all_fields(self):
        config = RAGInfrastructureConfig.from_environment(dict(RAG_ENV))
        self.assertEqual(config.qdrant_url, "http://localhost:6333")
        self.assertEqual(config.vector.collection_name, "xportra-test")
        self.assertEqual(
            config.vector.embedding_model, EMBEDDING_MODEL
        )
        self.assertEqual(
            config.vector.embedding_dimensions, EMBEDDING_DIMENSIONS
        )
        self.assertEqual(
            config.embedding.model_identifier, EMBEDDING_MODEL
        )
        self.assertEqual(
            config.embedding.dimensions, EMBEDDING_DIMENSIONS
        )
        self.assertEqual(
            config.generation.model_identifier, LLM_MODEL
        )
        self.assertTrue(config.prompt.system_instructions.strip())

    def test_missing_vector_url_fails(self):
        env = dict(RAG_ENV)
        del env["VECTOR_STORE_URL"]
        with self.assertRaises(RAGConfigurationError):
            RAGInfrastructureConfig.from_environment(env)

    def test_missing_collection_fails(self):
        env = dict(RAG_ENV)
        del env["VECTOR_STORE_COLLECTION"]
        with self.assertRaises(RAGConfigurationError):
            RAGInfrastructureConfig.from_environment(env)

    def test_missing_embedding_model_fails(self):
        env = dict(RAG_ENV)
        del env["EMBEDDING_MODEL"]
        with self.assertRaises(RAGConfigurationError):
            RAGInfrastructureConfig.from_environment(env)

    def test_invalid_embedding_dimensions_fail(self):
        for bad in ("", "abc", "0", "-5", "3.5"):
            env = dict(RAG_ENV)
            env["EMBEDDING_DIMENSIONS"] = bad
            with self.assertRaises(
                RAGConfigurationError, msg=f"dimensions={bad!r}"
            ):
                RAGInfrastructureConfig.from_environment(env)

    def test_missing_llm_key_fails_as_configuration_error(self):
        env = dict(RAG_ENV)
        del env["LLM_API_KEY"]
        with self.assertRaises(RAGConfigurationError) as ctx:
            RAGInfrastructureConfig.from_environment(env)
        self.assertIn("LLM_API_KEY", str(ctx.exception))

    def test_missing_llm_model_fails_as_configuration_error(self):
        env = dict(RAG_ENV)
        del env["LLM_MODEL"]
        with self.assertRaises(RAGConfigurationError):
            RAGInfrastructureConfig.from_environment(env)

    def test_secret_excluded_from_config_repr(self):
        config = RAGInfrastructureConfig.from_environment(dict(RAG_ENV))
        # The realistic leak surfaces: repr/str (used by logging,
        # tracebacks, and debuggers). The secret holder itself is
        # excluded via field(repr=False).
        rendered = repr(config) + str(config)
        self.assertNotIn(API_KEY_SENTINEL, rendered)


class RAGInfrastructureSelectionTests(unittest.TestCase):
    def test_real_qdrant_index_with_consistent_config(self):
        stack = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            embedding_provider=FakeEmbeddingProvider(),
            llm_client=ScriptedLLMClient(responses=[make_answer()]),
        )
        self.assertEqual(
            stack.vector_index.config.embedding_model, EMBEDDING_MODEL
        )
        self.assertEqual(
            stack.vector_index.config.embedding_dimensions,
            EMBEDDING_DIMENSIONS,
        )

    def test_embedding_provider_rejects_bad_input_without_loading(self):
        provider = SentenceTransformerEmbeddingProvider(
            embedding_config=EmbeddingModelConfig(
                model_identifier=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
            )
        )
        for bad in ("", "   ", 123, None, b"bytes"):
            with self.assertRaises(DomainValidationError):
                provider.embed(bad)
        self.assertFalse(provider.is_loaded)

    def test_embedding_dimension_mismatch_fails_closed(self):
        def stub_loader(_identifier):
            class StubModel:
                def encode(self, _text):
                    return [0.1, 0.2]

            return StubModel()

        provider = SentenceTransformerEmbeddingProvider(
            embedding_config=EmbeddingModelConfig(
                model_identifier=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
            ),
            model_loader=stub_loader,
        )
        with self.assertRaises(DomainValidationError):
            provider.embed("Form NXP deadline")
        self.assertTrue(provider.is_loaded)

    def test_embedding_load_failure_propagates(self):
        def broken_loader(_identifier):
            raise RuntimeError("model download failed")

        provider = SentenceTransformerEmbeddingProvider(
            embedding_config=EmbeddingModelConfig(
                model_identifier=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
            ),
            model_loader=broken_loader,
        )
        with self.assertRaises(VectorStoreError):
            provider.embed("Form NXP deadline")

    def test_embedding_failure_surfaces_without_success(self):
        service, _, _, _ = make_e2e_service(
            embedder=FakeEmbeddingProvider(
                failure=RuntimeError("embedding backend down")
            )
        )
        with client_for(service) as client:
            response = post_query(client)
        # The existing retrieval translation owns this failure.
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "domain_validation_error"
        )


class RAGEndToEndCompositionTests(unittest.TestCase):
    def test_successful_query_through_real_graph(self):
        service, _, _, _ = make_e2e_service()
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "valid")
        self.assertFalse(body["is_empty"])
        self.assertEqual(
            body["answer_text"], "File Form NXP before shipment [E1]."
        )
        self.assertEqual(body["extracted_references"], ["[E1]"])
        self.assertEqual(
            [(c["label"], c["rank_position"]) for c in body["citations"]],
            [("[E1]", 1)],
        )

    def test_evidence_and_provenance_reach_response(self):
        llm = ScriptedLLMClient(
            responses=[make_answer("File first [E1], then clear [E2].")]
        )
        service, _, _, _ = make_e2e_service(llm=llm)
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        by_label = {c["label"]: c["evidence"] for c in body["citations"]}
        self.assertEqual(by_label["[E1]"]["chunk_id"], str(CHUNK_A1))
        self.assertEqual(by_label["[E1]"]["document_id"], str(DOC_A1))
        self.assertEqual(
            by_label["[E1]"]["content_fingerprint"], "fp-a1"
        )
        self.assertEqual(by_label["[E2]"]["chunk_id"], str(CHUNK_A2))
        self.assertEqual(
            by_label["[E2]"]["source_id"], "sonsa/soncap-guide"
        )

    def test_lexical_mode_uses_lexical_path(self):
        service, index, _, _ = make_e2e_service()
        with client_for(service) as client:
            response = post_query(client, mode="lexical")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "valid")
        self.assertTrue(index.find_lexical_calls)
        self.assertEqual(
            index.find_lexical_calls[0]["tenant_id"], TENANT_A
        )

    def test_generation_config_is_server_controlled(self):
        service, _, _, llm = make_e2e_service()
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(
            llm.calls[0]["configuration"].model_identifier, LLM_MODEL
        )

    def test_invalid_model_citation_rejected(self):
        llm = ScriptedLLMClient(responses=[make_answer("See [E9].")])
        service, _, _, _ = make_e2e_service(llm=llm)
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"], "citation_integrity_error"
        )

    def test_provider_failure_does_not_become_success(self):
        from xportra.domain.errors import LLMProviderError

        llm = ScriptedLLMClient(
            failures=[LLMProviderError(
                "generate", RuntimeError("provider timeout"))]
        )
        service, _, _, _ = make_e2e_service(llm=llm)
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "llm_provider_error"
        )

    def test_empty_model_output_stays_empty_success(self):
        llm = ScriptedLLMClient(responses=[make_answer("   ")])
        service, _, _, _ = make_e2e_service(llm=llm)
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "empty")
        self.assertTrue(body["is_empty"])

    def test_no_evidence_follows_empty_context_path(self):
        class EmptyIndex(FakeVectorIndex):
            def find(self, *args, **kwargs):
                self.find_calls.append(kwargs)
                return []

            def find_lexical(self, *args, **kwargs):
                self.find_lexical_calls.append(kwargs)
                return []

        llm = ScriptedLLMClient(
            responses=[make_answer("No evidence was found.")]
        )
        service, _, _, _ = make_e2e_service(
            index=EmptyIndex(), llm=llm
        )
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "valid")
        self.assertEqual(body["citations"], [])
        self.assertEqual(body["extracted_references"], [])


class RAGCompositionTenantTests(unittest.TestCase):
    def test_tenant_a_retrieves_only_tenant_a(self):
        service, index, _, _ = make_e2e_service()
        with client_for(service) as client:
            response = post_query(client, headers=HEADER_A)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(index.find_calls[0]["tenant_id"], TENANT_A)
        rendered = response.text
        self.assertIn(str(CHUNK_A1), rendered)
        self.assertNotIn(str(CHUNK_B1), rendered)
        self.assertNotIn(str(DOC_B1), rendered)

    def test_tenant_b_retrieves_only_tenant_b(self):
        llm = ScriptedLLMClient(responses=[make_answer(
            "Tenant B rule applies [E1].")])
        service, index, _, _ = make_e2e_service(llm=llm)
        with client_for(service) as client:
            response = post_query(client, headers=HEADER_B)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(index.find_calls[0]["tenant_id"], TENANT_B)
        rendered = response.text
        self.assertIn(str(CHUNK_B1), rendered)
        self.assertNotIn(str(CHUNK_A1), rendered)
        self.assertNotIn(str(DOC_A1), rendered)

    def test_body_tenant_override_rejected(self):
        service, index, _, _ = make_e2e_service()
        with client_for(service) as client:
            response = post_query(
                client,
                tenant_id=str(TENANT_B_ID),
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(index.find_calls, [])
        self.assertEqual(index.find_lexical_calls, [])

    def test_scope_cannot_bypass_tenant_filter(self):
        llm = ScriptedLLMClient(
            responses=[make_answer("No evidence was found.")]
        )
        service, _, _, _ = make_e2e_service(llm=llm)
        with client_for(service) as client:
            response = post_query(
                client,
                headers=HEADER_A,
                scope={"document_id": str(DOC_B1)},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["citations"], [])
        self.assertNotIn(str(CHUNK_B1), response.text)
        self.assertNotIn(str(DOC_B1), response.text)

    def test_cross_tenant_vector_result_rejected(self):
        service, _, _, _ = make_e2e_service(
            index=FakeVectorIndex(cross_tenant=True)
        )
        with client_for(service) as client:
            response = post_query(client, headers=HEADER_A)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "vector_store_error"
        )
        self.assertNotIn(str(CHUNK_B1), response.text)

    def test_out_of_scope_result_rejected(self):
        service, _, _, _ = make_e2e_service(
            index=FakeVectorIndex(ignore_scope=True)
        )
        with client_for(service) as client:
            response = post_query(
                client,
                headers=HEADER_A,
                scope={"document_id": str(DOC_A2)},
            )
        # The fake returns tenant-A items without scope narrowing;
        # the existing scope re-check must reject out-of-scope rows.
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "vector_store_error"
        )


class RAGCompositionFailureTests(unittest.TestCase):
    def test_vector_failure_maps_without_success(self):
        service, _, _, _ = make_e2e_service(
            index=FakeVectorIndex(failure=RuntimeError("index down"))
        )
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "vector_store_error"
        )

    def test_answer_validation_failure_maps(self):
        llm = ScriptedLLMClient(responses=[make_answer("See [E9].")])
        service, _, _, _ = make_e2e_service(llm=llm)
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 422)

    def test_missing_configuration_fails_at_startup(self):
        env = dict(RAG_ENV)
        del env["VECTOR_STORE_URL"]
        with self.assertRaises(RAGConfigurationError):
            compose_rag_stack_from_environment(
                environment=env,
                llm_client=ScriptedLLMClient(),
            )

    def test_wiring_entry_point_composes_service(self):
        previous = dict(os.environ)
        os.environ.update(
            {
                "DATABASE_URL": "postgresql://localhost:5432/xportra-test",
                **RAG_ENV,
            }
        )
        try:
            services = ApplicationServices.from_environment_with_rag(
                llm_client=ScriptedLLMClient(
                    responses=[make_answer()]
                ),
                embedding_provider=FakeEmbeddingProvider(),
            )
        finally:
            os.environ.clear()
            os.environ.update(previous)
        self.assertIsInstance(services.rag, RAGApplicationService)

    def test_wiring_entry_point_autowires_production_llm(self):
        # Phase 5.15: with valid canonical LLM settings and no
        # explicit client, the entry point wires the production
        # adapter instead of failing.
        from xportra.infrastructure.llm import OpenRouterLLMClient

        previous = dict(os.environ)
        os.environ.update(
            {
                "DATABASE_URL": "postgresql://localhost:5432/xportra-test",
                **RAG_ENV,
            }
        )
        try:
            services = ApplicationServices.from_environment_with_rag(
                embedding_provider=FakeEmbeddingProvider(),
            )
        finally:
            os.environ.clear()
            os.environ.update(previous)
        self.assertIsInstance(services.rag, RAGApplicationService)
        self.assertIsInstance(
            services.rag._llm_client, OpenRouterLLMClient
        )

    def test_unexpected_failure_never_becomes_success(self):
        service, _, _, _ = make_e2e_service(
            index=FakeVectorIndex(
                failure=RuntimeError("postgresql://internal boom"))
        )
        with client_for(
            service, raise_server_exceptions=False
        ) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("postgresql", response.text.lower())


class RAGCompositionSecurityTests(unittest.TestCase):
    def _secret_env(self):
        env = dict(RAG_ENV)
        env["VECTOR_STORE_URL"] = QDRANT_URL_SENTINEL
        return env

    def test_response_and_logs_carry_no_secrets(self):
        service, _, _, _ = make_e2e_service()
        with self.assertLogs(
            "xportra.infrastructure.rag_composition", level="INFO"
        ) as captured:
            compose_rag_stack(
                RAGInfrastructureConfig.from_environment(
                    self._secret_env()
                ),
                embedding_provider=FakeEmbeddingProvider(),
                llm_client=ScriptedLLMClient(
                    responses=[make_answer()]
                ),
            )
        with client_for(service) as client:
            response = post_query(client)
        self.assertEqual(response.status_code, 200)
        rendered = response.text + "\n".join(captured.output)
        self.assertNotIn(API_KEY_SENTINEL, rendered)
        self.assertNotIn("sentinel-pw-0000", rendered)
        self.assertNotIn("authorization", rendered.lower())
        # ...while still logging the operational identifiers.
        self.assertTrue(
            any("xportra-test" in line for line in captured.output)
        )

    def test_response_contains_no_infrastructure_objects(self):
        service, _, _, _ = make_e2e_service()
        with client_for(service) as client:
            response = post_query(client)
        rendered = response.text
        for marker in (
            "QdrantClient",
            "ScriptedLLMClient",
            "PointStruct",
            "FakeVectorIndex",
            "sentence_transformers",
        ):
            self.assertNotIn(marker, rendered)

    def test_api_layer_constructs_no_infrastructure_clients(self):
        import pathlib

        api_dir = (
            pathlib.Path(__file__).resolve().parents[2] / "xportra" / "api"
        )
        violations = []
        for path in sorted(api_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for marker in (
                "QdrantClient(",
                "SentenceTransformer(",
                "ScriptedLLMClient(",
                "SentenceTransformerEmbeddingProvider(",
                "compose_rag_stack(",
            ):
                if marker in text:
                    violations.append(f"{path.name}: {marker}")
        self.assertEqual(violations, [])

    def test_domain_has_no_infrastructure_imports(self):
        import pathlib

        domain_dir = (
            pathlib.Path(__file__).resolve().parents[2]
            / "xportra"
            / "domain"
        )
        violations = []
        for path in sorted(domain_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith(
                        "xportra.infrastructure"
                    ):
                        violations.append(
                            f"{path.name}: {node.module}"
                        )
        self.assertEqual(violations, [])

    def test_logging_uses_module_logger_without_secrets(self):
        import xportra.infrastructure.rag_composition as module

        self.assertEqual(
            module.logger.name,
            "xportra.infrastructure.rag_composition",
        )
        self.assertIsInstance(module.logger, logging.Logger)


if __name__ == "__main__":
    unittest.main()
