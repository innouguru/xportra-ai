"""Phase 5.16 — Production RAG End-to-End Verification & Phase Closure.

Executable verification audits over the already-built system. No new
RAG functionality: configuration audit, security audit, lightweight
performance sanity checks, and the explicit failure-closed matrix
(§11), all deterministic with no external services.

Live infrastructure verification lives in the gated integration
tests (Qdrant smoke, OpenRouter live, combined live RAG) and is
NOT EXECUTED here — recorded as gated, never as verified.
"""

import ast
import pathlib
import unittest
from types import SimpleNamespace
from uuid import UUID

import httpx
from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.errors import DomainValidationError, LLMProviderError
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
)
from xportra.domain.evidence_context_pipeline import (
    build_evidence_context_pipeline,
)
from xportra.domain.evidence_hybrid import HybridRetrievalCandidate
from xportra.domain.evidence_indexing import EmbeddingModelConfig
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
from xportra.domain.rag_application import build_rag_application_service
from xportra.domain.vector_index import VectorIndexConfig
from xportra.infrastructure.llm import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    LLMSettings,
    OPENROUTER_BASE_URL,
    OpenRouterLLMClient,
    ScriptedLLMClient,
)
from xportra.infrastructure.rag_composition import (
    RAGConfigurationError,
    RAGInfrastructureConfig,
    SentenceTransformerEmbeddingProvider,
    compose_rag_stack,
)
from xportra.persistence.tenant import TenantContext

ROOT = pathlib.Path(__file__).resolve().parents[2]

TENANT_A_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT_A = TenantContext(TENANT_A_ID)
HEADER_A = {"X-Development-Tenant-ID": str(TENANT_A_ID)}
HEADER_B = {"X-Development-Tenant-ID": str(TENANT_B_ID)}
CHUNK_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_B = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
DOC_A = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1")
DOC_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2")

API_KEY_SENTINEL = "sk-test-sentinel-key-0000000000000000"
MODEL = "test-free-model"
GEN_CONFIG = LLMGenerationConfig(
    model_identifier=MODEL, temperature=0.0, max_output_tokens=128
)
PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="You are a compliance assistant."
)
RAG_ENV = {
    "VECTOR_STORE_URL": "http://localhost:6333",
    "VECTOR_STORE_COLLECTION": "xportra-test",
    "EMBEDDING_MODEL": "test-embed-model",
    "EMBEDDING_DIMENSIONS": "3",
    "LLM_API_KEY": API_KEY_SENTINEL,
    "LLM_MODEL": MODEL,
}

CONTENT_A = "Exporters must file Form NXP before shipment."
CONTENT_B = "Certificates need SONCAP clearance."


def make_evidence(tenant_id, chunk_id, document_id, content,
                  fingerprint, score=0.9):
    return EvidenceRetrievalResult(
        tenant_id=tenant_id,
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        content=content,
        content_fingerprint=fingerprint,
        source_id="sonsa/cert-guide",
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="2024.1",
        embedding_model="test-embed-model",
        embedding_dimensions=3,
        score=score,
    )


class FakeEmbedder:
    def embed(self, text):
        return [0.5, 0.1, 0.9]


class FakeIndex:
    """Tenant-first, scope-narrowing deterministic index stand-in."""

    def __init__(self, failure=None, cross_tenant=False):
        self._failure = failure
        self._cross_tenant = cross_tenant
        self.find_calls = []
        self.find_lexical_calls = []

    def _items(self):
        return [
            make_evidence(
                TENANT_A_ID, CHUNK_A, DOC_A, CONTENT_A, "fp-a", 0.9),
            make_evidence(
                TENANT_A_ID, CHUNK_B, DOC_B, CONTENT_B, "fp-b", 0.8),
        ]

    def find(self, query_vector, *, tenant_id, top_k, scope=None):
        self.find_calls.append(tenant_id)
        if self._failure is not None:
            raise self._failure
        if self._cross_tenant:
            return [make_evidence(
                TENANT_B_ID,
                UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1"),
                UUID("bbbbbbbb-bbbb-bbbb-bbbb-aaaaaaaaaa01"),
                "Foreign evidence.", "fp-x", 0.99)]
        items = [i for i in self._items()
                 if i.tenant_id == tenant_id.tenant_id]
        if scope is not None:
            items = [i for i in items if scope.accepts(i)]
        return items[:top_k]

    def find_lexical(self, terms, *, tenant_id, top_k, scope=None):
        self.find_lexical_calls.append(tenant_id)
        if self._failure is not None:
            raise self._failure
        if not terms:
            return []
        items = [i for i in self._items()
                 if i.tenant_id == tenant_id.tenant_id]
        if scope is not None:
            items = [i for i in items if scope.accepts(i)]
        return items[:1][:top_k]


def provider_transport(payload, status=200):
    def handler(_request):
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


def provider_payload(content="File Form NXP before shipment [E1]."):
    return {
        "id": "gen-1",
        "model": "provider-echo",
        "choices": [{
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 8,
                  "completion_tokens": 6,
                  "total_tokens": 14},
    }


def make_service(index=None, llm=None):
    index = index if index is not None else FakeIndex()
    embedding_config = EmbeddingModelConfig(
        model_identifier="test-embed-model", dimensions=3)
    semantic = VectorIndexEvidenceRetriever(
        vector_index=index,
        provider=FakeEmbedder(),
        embedding_config=embedding_config,
    )
    llm = llm if llm is not None else ScriptedLLMClient(
        responses=[LLMResponse(
            generated_text="File Form NXP before shipment [E1].",
            model_identifier=MODEL)])
    return build_rag_application_service(
        context_pipeline=build_evidence_context_pipeline(
            semantic_retriever=semantic, lexical_index=index),
        prompt_config=PROMPT_CONFIG,
        llm_client=llm,
        llm_generation_config=GEN_CONFIG,
        answer_validator=CitationAwareAnswerValidator(),
    ), index


def post(service, headers=HEADER_A, **payload):
    body = {"information_need": "When must Form NXP be filed?"}
    body.update(payload)
    with TestClient(
        create_app(services=SimpleNamespace(rag=service))
    ) as client:
        return client.post("/rag/query", headers=headers, json=body)


class ProductionConfigAuditTests(unittest.TestCase):
    def _schema_variables(self):
        text = (ROOT / "docs" / "architecture"
                / "environment-schema.md").read_text(encoding="utf-8")
        variables = set()
        for line in text.splitlines():
            if line.startswith("#### "):
                variables.add(line[5:].strip())
        return variables

    def _example_variables(self):
        variables = {}
        for line in (ROOT / ".env.example").read_text(
                encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            variables[name.strip()] = value.strip()
        return variables

    def test_example_variables_are_documented(self):
        schema = self._schema_variables()
        for name in self._example_variables():
            self.assertIn(name, schema, f"undocumented: {name}")

    def test_required_rag_variables_present_in_example(self):
        example = self._example_variables()
        for name in (
            "VECTOR_STORE_URL", "VECTOR_STORE_COLLECTION",
            "EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS",
            "LLM_API_KEY", "LLM_MODEL",
            "LLM_BASE_URL", "LLM_TIMEOUT_SECONDS",
        ):
            self.assertIn(name, example, f"missing: {name}")

    def test_example_contains_placeholders_only(self):
        for name, value in self._example_variables().items():
            self.assertNotIn(
                "sk-", value, f"{name} looks like a real secret")
            self.assertNotIn(
                "eyJ", value, f"{name} looks like a real token")
            if name == "DATABASE_URL":
                self.assertEqual(value, "")

    def test_embedding_vector_consistency_by_construction(self):
        embedding = EmbeddingModelConfig(
            model_identifier="m", dimensions=384)
        vector = VectorIndexConfig.from_embedding_config("c", embedding)
        self.assertEqual(vector.embedding_model, "m")
        self.assertEqual(vector.embedding_dimensions, 384)
        with self.assertRaises(DomainValidationError):
            EmbeddingModelConfig(
                model_identifier="m", dimensions=0)

    def test_llm_timeout_is_finite(self):
        self.assertTrue(
            DEFAULT_LLM_TIMEOUT_SECONDS > 0
            and DEFAULT_LLM_TIMEOUT_SECONDS
            != float("inf"))
        config = RAGInfrastructureConfig.from_environment(
            dict(RAG_ENV))
        self.assertEqual(
            config.llm_timeout_seconds, DEFAULT_LLM_TIMEOUT_SECONDS)
        self.assertEqual(
            config.llm_base_url, OPENROUTER_BASE_URL)

    def test_no_hidden_provider_fallback_in_adapter(self):
        # Static guarantee on code identifiers (docstrings may deny
        # fallback in prose): no retry/failover/fallback machinery
        # exists anywhere in the adapter module.
        tree = ast.parse(
            (ROOT / "xportra" / "infrastructure"
             / "llm.py").read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        for marker in ("fallback", "failover", "retry", "retries",
                       "backup", "secondary"):
            self.assertNotIn(marker, names)


class ProductionSecurityAuditTests(unittest.TestCase):
    def test_no_key_literals_in_package(self):
        import re

        # Key-like tokens (long `sk-` strings such as provider keys),
        # not prose hyphenations like "risk-classified".
        key_like = re.compile(r"sk-[A-Za-z0-9\-_]{20,}")
        offenders = []
        for path in sorted((ROOT / "xportra").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if key_like.search(text):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_secret_holder_repr_is_safe(self):
        settings = LLMSettings(
            api_key=API_KEY_SENTINEL, model_identifier=MODEL)
        self.assertNotIn(API_KEY_SENTINEL, repr(settings))
        self.assertNotIn(API_KEY_SENTINEL, str(settings))
        self.assertEqual(settings.api_key, API_KEY_SENTINEL)

    def test_domain_has_no_io_or_network_surface(self):
        roots = set()
        opens = []
        for path in sorted((ROOT / "xportra" / "domain").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots.update(
                        a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.level == 0:
                        roots.add(node.module.split(".")[0])
            text = path.read_text(encoding="utf-8")
            if "open(" in text:
                opens.append(path.name)
        forbidden = {"fastapi", "starlette", "qdrant_client",
                     "openai", "anthropic", "httpx", "requests",
                     "socket", "os", "sys", "subprocess"}
        self.assertTrue(
            roots.isdisjoint(forbidden),
            f"forbidden domain imports: {roots & forbidden}")
        self.assertEqual(opens, [])

    def test_api_builds_no_infrastructure_transports(self):
        violations = []
        for path in sorted((ROOT / "xportra" / "api").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for marker in ("QdrantClient(", "OpenRouterLLMClient(",
                           "httpx.Client(", "SentenceTransformer("):
                if marker in text:
                    violations.append(f"{path.name}: {marker}")
        self.assertEqual(violations, [])

    def test_adapter_executes_nothing(self):
        text = (ROOT / "xportra" / "infrastructure"
                / "llm.py").read_text(encoding="utf-8")
        for marker in ("exec(", "eval(", "os.system",
                       "subprocess", "__import__"):
            self.assertNotIn(marker, text)


class ProductionPerformanceSanityTests(unittest.TestCase):
    def test_embedding_model_loads_once(self):
        loads = []

        def stub_loader(identifier):
            loads.append(identifier)

            class StubModel:
                def encode(self, _text):
                    return [0.1, 0.2, 0.3]

            return StubModel()

        provider = SentenceTransformerEmbeddingProvider(
            embedding_config=EmbeddingModelConfig(
                model_identifier="m", dimensions=3),
            model_loader=stub_loader,
        )
        provider.embed("first need")
        provider.embed("second need")
        self.assertEqual(loads, ["m"])
        self.assertTrue(provider.is_loaded)

    def test_no_retrieval_duplication_per_query(self):
        service, index = make_service()
        self.assertEqual(post(service).status_code, 200)
        # Hybrid runs each path exactly once by design — no
        # accidental duplication.
        self.assertEqual(len(index.find_calls), 1)
        self.assertEqual(len(index.find_lexical_calls), 1)

    def test_service_and_clients_stable_across_requests(self):
        adapter = OpenRouterLLMClient(
            settings=LLMSettings(
                api_key=API_KEY_SENTINEL, model_identifier=MODEL),
            http_client=httpx.Client(
                transport=provider_transport(provider_payload())),
        )
        service, _ = make_service(llm=adapter)
        first = post(service)
        second = post(service)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertIs(service._llm_client, adapter)

    def test_context_bounded_by_budget(self):
        service, _ = make_service()
        response = post(service, max_context_characters=50)
        self.assertEqual(response.status_code, 200)
        # 50 chars admit only the first (~47-char) evidence item.
        self.assertEqual(len(response.json()["citations"]), 1)


class ProductionFailureMatrixTests(unittest.TestCase):
    """§11 failure-closed matrix with observed results."""

    def test_missing_llm_configuration(self):
        env = dict(RAG_ENV)
        del env["LLM_API_KEY"]
        with self.assertRaises(RAGConfigurationError):
            RAGInfrastructureConfig.from_environment(env)

    def test_llm_authentication_failure(self):
        adapter = OpenRouterLLMClient(
            settings=LLMSettings(
                api_key=API_KEY_SENTINEL, model_identifier=MODEL),
            http_client=httpx.Client(transport=provider_transport(
                {"error": {"message": "invalid key"}}, status=401)),
        )
        service, _ = make_service(llm=adapter)
        response = post(service)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "llm_provider_error")
        self.assertNotIn("answer_text", response.json())

    def test_llm_timeout(self):
        def handler(_request):
            raise httpx.TimeoutException("timed out")

        adapter = OpenRouterLLMClient(
            settings=LLMSettings(
                api_key=API_KEY_SENTINEL, model_identifier=MODEL),
            http_client=httpx.Client(
                transport=httpx.MockTransport(handler)),
        )
        service, _ = make_service(llm=adapter)
        response = post(service)
        self.assertEqual(response.status_code, 502)

    def test_llm_malformed_response(self):
        adapter = OpenRouterLLMClient(
            settings=LLMSettings(
                api_key=API_KEY_SENTINEL, model_identifier=MODEL),
            http_client=httpx.Client(
                transport=provider_transport({"choices": []})),
        )
        service, _ = make_service(llm=adapter)
        response = post(service)
        self.assertEqual(response.status_code, 502)

    def test_qdrant_unavailable(self):
        from qdrant_client import QdrantClient

        from xportra.domain.errors import VectorStoreError
        from xportra.infrastructure.vector_index import (
            QdrantEvidenceVectorIndex,
        )

        index = QdrantEvidenceVectorIndex(
            QdrantClient(url="http://127.0.0.1:9", timeout=5.0),
            VectorIndexConfig.from_embedding_config(
                "unreachable-test",
                EmbeddingModelConfig(
                    model_identifier="m", dimensions=3)),
        )
        with self.assertRaises(VectorStoreError) as ctx:
            index.ensure_collection()
        self.assertNotIn("answer_text", str(ctx.exception))

    def test_cross_tenant_result_rejected(self):
        service, _ = make_service(index=FakeIndex(cross_tenant=True))
        response = post(service)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "vector_store_error")

    def test_invalid_citation_rejected(self):
        adapter = OpenRouterLLMClient(
            settings=LLMSettings(
                api_key=API_KEY_SENTINEL, model_identifier=MODEL),
            http_client=httpx.Client(transport=provider_transport(
                provider_payload("See [E9]."))),
        )
        service, _ = make_service(llm=adapter)
        response = post(service)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"],
            "citation_integrity_error")

    def test_empty_model_output(self):
        adapter = OpenRouterLLMClient(
            settings=LLMSettings(
                api_key=API_KEY_SENTINEL, model_identifier=MODEL),
            http_client=httpx.Client(
                transport=provider_transport(provider_payload(""))),
        )
        service, _ = make_service(llm=adapter)
        response = post(service)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "empty")

    def test_no_retrieved_evidence(self):
        class EmptyIndex(FakeIndex):
            def find(self, *a, **k):
                return []

            def find_lexical(self, *a, **k):
                return []

        adapter = OpenRouterLLMClient(
            settings=LLMSettings(
                api_key=API_KEY_SENTINEL, model_identifier=MODEL),
            http_client=httpx.Client(transport=provider_transport(
                provider_payload("No evidence was found."))),
        )
        service, _ = make_service(index=EmptyIndex(), llm=adapter)
        response = post(service)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "valid")
        self.assertEqual(body["citations"], [])

    def test_invalid_request(self):
        service, _ = make_service()
        response = post(service, information_need="")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
