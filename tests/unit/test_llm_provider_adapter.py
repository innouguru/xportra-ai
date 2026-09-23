"""Phase 5.15 — Production LLM Provider Adapter tests.

Covers the single production ``LLMClient`` (OpenRouter, TB-5 —
OpenAI-compatible chat completions over httpx, no vendor SDK):

- contract (structured prompt in, canonical ``LLMResponse`` out);
- request/response translation; failure translation (every listed
  provider failure becomes ``LLMProviderError``, never success);
- exactly one provider attempt (no retries, no fallback);
- security (credentials, tenant isolation, no raw leakage);
- immutability; composition wiring; deterministic end-to-end
  application verification through HTTP.

Deterministic only — the transport is ``httpx.MockTransport``.
No network, no credentials, no model downloads.
"""

import dataclasses
import json
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
    EvidencePrompt,
    EvidencePromptConfig,
)
from xportra.domain.evidence_ranking import DeterministicEvidenceRanker
from xportra.domain.evidence_retrieval import (
    EvidenceRetrievalResult,
    VectorIndexEvidenceRetriever,
)
from xportra.domain.llm import LLMGenerationConfig, LLMResponse
from xportra.domain.rag_application import build_rag_application_service
from xportra.infrastructure.llm import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    LLMSettings,
    OPENROUTER_BASE_URL,
    OPENROUTER_PROVIDER_NAME,
    OpenRouterLLMClient,
    ScriptedLLMClient,
)
from xportra.infrastructure.rag_composition import (
    RAGComposition,
    RAGConfigurationError,
    RAGInfrastructureConfig,
    compose_rag_stack,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT = TenantContext(TENANT_ID)
HEADER = {"X-Development-Tenant-ID": str(TENANT_ID)}
CHUNK_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_B = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
DOC_A = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1")
DOC_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2")

API_KEY_SENTINEL = "sk-test-sentinel-key-0000000000000000"
MODEL = "test-free-model"
CONFIG = LLMGenerationConfig(
    model_identifier=MODEL, temperature=0.3, max_output_tokens=256
)
PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="You are a compliance assistant."
)
SETTINGS = LLMSettings(
    api_key=API_KEY_SENTINEL, model_identifier=MODEL
)

RAG_ENV = {
    "VECTOR_STORE_URL": "http://localhost:6333",
    "VECTOR_STORE_COLLECTION": "xportra-test",
    "EMBEDDING_MODEL": "test-embed-model",
    "EMBEDDING_DIMENSIONS": "3",
    "LLM_API_KEY": API_KEY_SENTINEL,
    "LLM_MODEL": MODEL,
}


def make_evidence(content, chunk_id, document_id, fingerprint, score):
    return EvidenceRetrievalResult(
        tenant_id=TENANT_ID,
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


def make_prompt(need="Form NXP deadline"):
    candidates = [
        HybridRetrievalCandidate(
            evidence=make_evidence(
                "Exporters must file Form NXP before shipment.",
                CHUNK_A, DOC_A, "fp-a", 0.9,
            ),
            semantic_score=0.9,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"}),
        ),
        HybridRetrievalCandidate(
            evidence=make_evidence(
                "Certificates need SONCAP clearance.",
                CHUNK_B, DOC_B, "fp-b", 0.8,
            ),
            semantic_score=0.8,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"}),
        ),
    ]
    ranked = DeterministicEvidenceRanker().rank(candidates, top_k=2)
    selection = DeterministicContextSelector().select(
        ranked, tenant_id=TENANT, budget=EvidenceContextBudget(4000)
    )
    return CitationAwarePromptBuilder(config=PROMPT_CONFIG).build(
        selection, information_need=need
    )


def provider_payload(content="File Form NXP before shipment [E1].", **over):
    payload = {
        "id": "gen-test-1",
        "model": "provider-echo-model",
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }
    payload.update(over)
    return payload


class CapturingTransport:
    """Deterministic httpx transport with request capture."""

    def __init__(self, handler):
        self.calls = []
        self._handler = handler
        self.transport = httpx.MockTransport(self._dispatch)

    def _dispatch(self, request):
        self.calls.append(request)
        return self._handler(request)

    def client(self):
        return httpx.Client(transport=self.transport)


def json_transport(payload, status=200):
    def handler(_request):
        return httpx.Response(status, json=payload)

    return CapturingTransport(handler)


def make_client(transport, **overrides):
    kwargs = dict(settings=SETTINGS)
    kwargs.update(overrides)
    return OpenRouterLLMClient(
        http_client=transport.client(), **kwargs
    )


class AdapterContractTests(unittest.TestCase):
    def test_structured_prompt_accepted(self):
        transport = json_transport(provider_payload())
        client = make_client(transport)
        response = client.generate(make_prompt(), configuration=CONFIG)
        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(len(transport.calls), 1)

    def test_prompt_contents_preserved_in_order(self):
        transport = json_transport(provider_payload())
        client = make_client(transport)
        prompt = make_prompt()
        client.generate(prompt, configuration=CONFIG)
        body = json.loads(transport.calls[0].content.decode("utf-8"))
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(
            body["messages"][0]["content"], prompt.system_instructions
        )
        user = body["messages"][1]
        self.assertEqual(user["role"], "user")
        self.assertIn(prompt.information_need, user["content"])
        self.assertIn(prompt.evidence_context, user["content"])
        first = user["content"].index("[E1]")
        second = user["content"].index("[E2]")
        self.assertLess(first, second)
        first_evidence = user["content"].index(
            "Exporters must file Form NXP"
        )
        second_evidence = user["content"].index(
            "Certificates need SONCAP"
        )
        self.assertLess(first_evidence, second_evidence)

    def test_model_identifier_translated(self):
        transport = json_transport(provider_payload())
        client = make_client(transport)
        client.generate(make_prompt(), configuration=CONFIG)
        body = json.loads(transport.calls[0].content.decode("utf-8"))
        self.assertEqual(body["model"], MODEL)

    def test_temperature_translated(self):
        transport = json_transport(provider_payload())
        client = make_client(transport)
        client.generate(make_prompt(), configuration=CONFIG)
        body = json.loads(transport.calls[0].content.decode("utf-8"))
        self.assertEqual(body["temperature"], 0.3)

    def test_max_output_tokens_translated(self):
        transport = json_transport(provider_payload())
        client = make_client(transport)
        client.generate(make_prompt(), configuration=CONFIG)
        body = json.loads(transport.calls[0].content.decode("utf-8"))
        self.assertEqual(body["max_tokens"], 256)
        self.assertNotIn("max_output_tokens", body)
        self.assertNotIn("top_p", body)

    def test_empty_evidence_prompt_translated(self):
        transport = json_transport(
            provider_payload("No evidence was found.")
        )
        client = make_client(transport)
        selection = DeterministicContextSelector().select(
            [], tenant_id=TENANT, budget=EvidenceContextBudget(4000)
        )
        prompt = CitationAwarePromptBuilder(
            config=PROMPT_CONFIG
        ).build(selection, information_need="need")
        self.assertTrue(prompt.is_empty)
        response = client.generate(prompt, configuration=CONFIG)
        self.assertEqual(
            response.generated_text, "No evidence was found."
        )

    def test_request_targets_chat_completions(self):
        transport = json_transport(provider_payload())
        client = make_client(transport)
        client.generate(make_prompt(), configuration=CONFIG)
        request = transport.calls[0]
        self.assertTrue(
            str(request.url).endswith("/chat/completions")
        )
        self.assertEqual(request.method, "POST")

    def test_malformed_inputs_rejected_before_transport(self):
        transport = json_transport(provider_payload())
        client = make_client(transport)
        with self.assertRaises(DomainValidationError):
            client.generate("not a prompt", configuration=CONFIG)
        with self.assertRaises(DomainValidationError):
            client.generate(make_prompt(), configuration="nope")
        self.assertEqual(transport.calls, [])

    def test_constructor_rejects_bad_arguments(self):
        transport = json_transport(provider_payload())
        with self.assertRaises(DomainValidationError):
            OpenRouterLLMClient(
                settings="nope",
                http_client=transport.client(),
            )
        with self.assertRaises(DomainValidationError):
            OpenRouterLLMClient(
                settings=SETTINGS, base_url="  ",
                http_client=transport.client(),
            )
        for bad_timeout in (0, -1, float("nan"), float("inf"), True):
            with self.assertRaises(DomainValidationError):
                OpenRouterLLMClient(
                    settings=SETTINGS, timeout_seconds=bad_timeout,
                    http_client=transport.client(),
                )


class AdapterResponseTests(unittest.TestCase):
    def test_generated_text_verbatim(self):
        transport = json_transport(provider_payload("Answer [E1]."))
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertEqual(response.generated_text, "Answer [E1].")

    def test_provider_model_preferred(self):
        transport = json_transport(provider_payload())
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertEqual(response.model_identifier, "provider-echo-model")

    def test_configured_model_fallback(self):
        payload = provider_payload()
        del payload["model"]
        transport = json_transport(payload)
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertEqual(response.model_identifier, MODEL)

    def test_finish_reason_preserved_and_optional(self):
        transport = json_transport(provider_payload())
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertEqual(response.finish_reason, "stop")
        payload = provider_payload()
        payload["choices"][0]["finish_reason"] = None
        response = make_client(json_transport(payload)).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertIsNone(response.finish_reason)

    def test_usage_mapped_and_optional(self):
        transport = json_transport(provider_payload())
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertEqual(response.usage.input_tokens, 10)
        self.assertEqual(response.usage.output_tokens, 5)
        self.assertEqual(response.usage.total_tokens, 15)
        payload = provider_payload()
        del payload["usage"]
        response = make_client(json_transport(payload)).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertIsNone(response.usage)

    def test_provider_name_recorded(self):
        transport = json_transport(provider_payload())
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertEqual(response.provider_name, OPENROUTER_PROVIDER_NAME)

    def test_empty_output_preserved_as_success(self):
        transport = json_transport(provider_payload(""))
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.generated_text, "")
        self.assertTrue(response.is_empty)


class AdapterFailureTests(unittest.TestCase):
    def assert_provider_error(self, transport, **kwargs):
        with self.assertRaises(LLMProviderError) as ctx:
            make_client(transport, **kwargs).generate(
                make_prompt(), configuration=CONFIG
            )
        self.assertEqual(ctx.exception.operation, "generate")
        self.assertIsNotNone(ctx.exception.cause)
        return ctx.exception

    def test_authentication_failure(self):
        transport = json_transport(
            {"error": {"message": "invalid key"}}, status=401
        )
        error = self.assert_provider_error(transport)
        self.assertIsInstance(error.cause, httpx.HTTPStatusError)

    def test_rate_limit(self):
        transport = json_transport(
            {"error": {"message": "rate limited"}}, status=429
        )
        self.assert_provider_error(transport)

    def test_provider_http_error(self):
        transport = json_transport(
            {"error": {"message": "overloaded"}}, status=500
        )
        self.assert_provider_error(transport)

    def test_timeout_becomes_provider_error(self):
        def handler(_request):
            raise httpx.TimeoutException("timed out")

        self.assert_provider_error(CapturingTransport(handler))

    def test_network_failure_becomes_provider_error(self):
        def handler(_request):
            raise httpx.ConnectError("refused")

        self.assert_provider_error(CapturingTransport(handler))

    def test_malformed_json_becomes_provider_error(self):
        def handler(_request):
            return httpx.Response(200, content=b"not json{")

        self.assert_provider_error(CapturingTransport(handler))

    def test_missing_choices_becomes_provider_error(self):
        self.assert_provider_error(json_transport({"id": "x"}))
        self.assert_provider_error(
            json_transport({"choices": []})
        )
        self.assert_provider_error(
            json_transport({"choices": ["nope"]})
        )

    def test_missing_message_or_content_becomes_provider_error(self):
        payload = provider_payload()
        del payload["choices"][0]["message"]
        self.assert_provider_error(json_transport(payload))
        self.assert_provider_error(
            json_transport(provider_payload(None))
        )
        self.assert_provider_error(
            json_transport(provider_payload(42))
        )

    def test_unexpected_root_shape_becomes_provider_error(self):
        self.assert_provider_error(json_transport(["a", "list"]))

    def test_malformed_usage_becomes_provider_error(self):
        self.assert_provider_error(
            json_transport(provider_payload(usage="nope"))
        )
        payload = provider_payload()
        payload["usage"] = {"prompt_tokens": True}
        self.assert_provider_error(json_transport(payload))

    def test_malformed_finish_reason_becomes_provider_error(self):
        payload = provider_payload()
        payload["choices"][0]["finish_reason"] = 7
        self.assert_provider_error(json_transport(payload))


class AdapterRetryTests(unittest.TestCase):
    def test_success_is_single_attempt(self):
        transport = json_transport(provider_payload())
        make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertEqual(len(transport.calls), 1)

    def test_failure_is_single_attempt_no_retry(self):
        transport = json_transport(
            {"error": {"message": "overloaded"}}, status=500
        )
        with self.assertRaises(LLMProviderError):
            make_client(transport).generate(
                make_prompt(), configuration=CONFIG
            )
        self.assertEqual(len(transport.calls), 1)

    def test_timeout_is_single_attempt_no_fallback(self):
        seen_urls = []

        def handler(request):
            seen_urls.append(str(request.url))
            raise httpx.TimeoutException("timed out")

        transport = CapturingTransport(handler)
        with self.assertRaises(LLMProviderError):
            make_client(transport).generate(
                make_prompt(), configuration=CONFIG
            )
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(len(seen_urls), 1)


class AdapterSecurityTests(unittest.TestCase):
    def test_api_key_in_header_not_in_body(self):
        transport = json_transport(provider_payload())
        make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        request = transport.calls[0]
        self.assertEqual(
            request.headers["authorization"],
            f"Bearer {API_KEY_SENTINEL}",
        )
        self.assertNotIn(
            API_KEY_SENTINEL, request.content.decode("utf-8")
        )

    def test_api_key_never_logged(self):
        transport = json_transport(provider_payload())
        client = make_client(transport)
        with self.assertLogs(
            "xportra.infrastructure.llm", level="DEBUG"
        ) as captured:
            client.generate(make_prompt(), configuration=CONFIG)
        rendered = "\n".join(captured.output)
        self.assertNotIn(API_KEY_SENTINEL, rendered)
        self.assertNotIn("authorization", rendered.lower())

    def test_api_key_not_in_response(self):
        transport = json_transport(provider_payload())
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        rendered = repr(response) + str(response.to_record())
        self.assertNotIn(API_KEY_SENTINEL, rendered)

    def test_tenant_absent_from_provider_prompt(self):
        transport = json_transport(provider_payload())
        make_client(transport).generate(
            make_prompt(), configuration=CONFIG, tenant_id=TENANT
        )
        body = json.loads(transport.calls[0].content.decode("utf-8"))
        rendered = json.dumps(body)
        self.assertNotIn(str(TENANT_ID), rendered)
        self.assertNotIn("tenant", rendered.lower())

    def test_raw_provider_response_not_exposed(self):
        transport = json_transport(provider_payload())
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        self.assertIs(type(response), LLMResponse)
        for attr in ("raw", "provider_response", "json", "choices"):
            self.assertFalse(hasattr(response, attr))

    def test_failure_logs_carry_no_secrets(self):
        transport = json_transport(
            {"error": {"message": "bad key"}}, status=401
        )
        client = make_client(transport)
        with self.assertLogs(
            "xportra.infrastructure.llm", level="DEBUG"
        ) as captured:
            with self.assertRaises(LLMProviderError):
                client.generate(make_prompt(), configuration=CONFIG)
        rendered = "\n".join(captured.output)
        self.assertNotIn(API_KEY_SENTINEL, rendered)
        self.assertNotIn("authorization", rendered.lower())


class AdapterImmutabilityTests(unittest.TestCase):
    def test_prompt_unchanged_after_success(self):
        transport = json_transport(provider_payload())
        prompt = make_prompt()
        before = prompt.to_record()
        make_client(transport).generate(prompt, configuration=CONFIG)
        self.assertEqual(prompt.to_record(), before)

    def test_prompt_unchanged_after_failure(self):
        transport = json_transport(
            {"error": {"message": "bad"}}, status=500
        )
        prompt = make_prompt()
        before = prompt.to_record()
        with self.assertRaises(LLMProviderError):
            make_client(transport).generate(
                prompt, configuration=CONFIG
            )
        self.assertEqual(prompt.to_record(), before)

    def test_response_immutable(self):
        transport = json_transport(provider_payload())
        response = make_client(transport).generate(
            make_prompt(), configuration=CONFIG
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            response.generated_text = "mutated"


class AdapterCompositionTests(unittest.TestCase):
    def test_production_client_wired_by_default(self):
        stack = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            embedding_provider=_StubEmbedder(),
        )
        self.assertIsInstance(stack, RAGComposition)
        self.assertIsInstance(
            stack.llm_client, OpenRouterLLMClient
        )
        self.assertIs(stack.service._llm_client, stack.llm_client)

    def test_explicit_client_still_wins(self):
        scripted = ScriptedLLMClient(
            responses=[
                LLMResponse(
                    generated_text="scripted",
                    model_identifier=MODEL,
                )
            ]
        )
        stack = compose_rag_stack(
            RAGInfrastructureConfig.from_environment(dict(RAG_ENV)),
            embedding_provider=_StubEmbedder(),
            llm_client=scripted,
        )
        self.assertIs(stack.llm_client, scripted)

    def test_missing_llm_credentials_still_fail_closed(self):
        env = dict(RAG_ENV)
        del env["LLM_API_KEY"]
        with self.assertRaises(RAGConfigurationError):
            compose_rag_stack(
                RAGInfrastructureConfig.from_environment(env),
                embedding_provider=_StubEmbedder(),
            )

    def test_invalid_timeout_env_fails_closed(self):
        for bad in ("abc", "-5", "0", "inf"):
            env = dict(RAG_ENV)
            env["LLM_TIMEOUT_SECONDS"] = bad
            with self.assertRaises(
                RAGConfigurationError, msg=f"timeout={bad!r}"
            ):
                RAGInfrastructureConfig.from_environment(env)

    def test_custom_base_url_honored(self):
        env = dict(RAG_ENV)
        env["LLM_BASE_URL"] = "https://example.test/v1/"
        config = RAGInfrastructureConfig.from_environment(env)
        self.assertEqual(
            config.llm_base_url, "https://example.test/v1/"
        )
        stack = compose_rag_stack(
            config, embedding_provider=_StubEmbedder()
        )
        self.assertEqual(
            stack.llm_client._base_url, "https://example.test/v1"
        )

    def test_api_layer_builds_no_provider_transport(self):
        import ast
        import pathlib

        api_dir = (
            pathlib.Path(__file__).resolve().parents[2] / "xportra" / "api"
        )
        violations = []
        for path in sorted(api_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for marker in ("OpenRouterLLMClient(", "httpx.Client("):
                if marker in text:
                    violations.append(f"{path.name}: {marker}")
        self.assertEqual(violations, [])


class _StubEmbedder:
    def embed(self, text):
        return [0.5, 0.1, 0.9]


class _StubIndex:
    def __init__(self):
        self.find_calls = []

    def _items(self):
        return [
            make_evidence(
                "Exporters must file Form NXP before shipment.",
                CHUNK_A, DOC_A, "fp-a", 0.9,
            ),
            make_evidence(
                "Certificates need SONCAP clearance.",
                CHUNK_B, DOC_B, "fp-b", 0.8,
            ),
        ]

    def find(self, query_vector, *, tenant_id, top_k, scope=None):
        self.find_calls.append(tenant_id)
        return [
            item for item in self._items()
            if item.tenant_id == tenant_id.tenant_id
        ][:top_k]

    def find_lexical(self, terms, *, tenant_id, top_k, scope=None):
        if not terms:
            return []
        return self.find([], tenant_id=tenant_id, top_k=top_k,
                         scope=scope)[:1]


def _e2e_service(payload):
    transport = json_transport(payload) \
        if isinstance(payload, dict) else payload
    adapter = OpenRouterLLMClient(
        settings=SETTINGS, http_client=transport.client()
    )
    embedding_config = EmbeddingModelConfig(
        model_identifier="test-embed-model", dimensions=3
    )
    index = _StubIndex()
    semantic = VectorIndexEvidenceRetriever(
        vector_index=index,
        provider=_StubEmbedder(),
        embedding_config=embedding_config,
    )
    service = build_rag_application_service(
        context_pipeline=build_evidence_context_pipeline(
            semantic_retriever=semantic, lexical_index=index
        ),
        prompt_config=PROMPT_CONFIG,
        llm_client=adapter,
        llm_generation_config=CONFIG,
        answer_validator=CitationAwareAnswerValidator(),
    )
    return service, transport


class AdapterEndToEndTests(unittest.TestCase):
    def test_provider_answer_validated_through_http(self):
        service, transport = _e2e_service(provider_payload())
        with TestClient(
            create_app(services=SimpleNamespace(rag=service))
        ) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER,
                json={"information_need": "Form NXP deadline"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "valid")
        self.assertEqual(
            body["answer_text"],
            "File Form NXP before shipment [E1].",
        )
        self.assertEqual(
            body["citations"][0]["evidence"]["chunk_id"], str(CHUNK_A)
        )
        # The provider received the structured prompt translation.
        sent = json.loads(transport.calls[0].content.decode("utf-8"))
        self.assertIn("Exporters must file Form NXP", json.dumps(sent))
        self.assertIn("[E1]", json.dumps(sent))
        self.assertNotIn(str(TENANT_ID), json.dumps(sent))

    def test_provider_failure_not_a_success(self):
        service, _ = _e2e_service(
            json_transport(
                {"error": {"message": "overloaded"}}, status=500
            )
        )
        with TestClient(
            create_app(services=SimpleNamespace(rag=service))
        ) as client:
            response = client.post(
                "/rag/query",
                headers=HEADER,
                json={"information_need": "Form NXP deadline"},
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "llm_provider_error"
        )


if __name__ == "__main__":
    unittest.main()
