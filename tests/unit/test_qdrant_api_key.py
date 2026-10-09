"""Qdrant API-key support — focused composition tests.

Proves the optional ``QDRANT_API_KEY`` variable is plumbed to the
``QdrantClient`` built by both the RAG stack and the evidence
index-sync composers, while keyless behavior is preserved exactly
when it is absent.

Mocks only: the ``QdrantClient`` constructor is observed (never
executed), the embedding provider and LLM client are deterministic
stubs. No network, no model download, no OpenRouter call, no live
Qdrant. The key value below is a non-secret placeholder sentinel.
"""

import unittest
from unittest import mock

from xportra.infrastructure.evidence_upload import (
    compose_evidence_index_sync_from_environment,
)
from xportra.infrastructure.llm import ScriptedLLMClient
from xportra.infrastructure.rag_composition import (
    RAGConfigurationError,
    RAGInfrastructureConfig,
    compose_rag_stack_from_environment,
    qdrant_api_key_from_environment,
)

API_KEY_SENTINEL = "qk-test-sentinel-key-0000000000000000"

RAG_ENV = {
    "VECTOR_STORE_URL": "http://127.0.0.1:1",
    "VECTOR_STORE_COLLECTION": "xportra-key-test",
    "EMBEDDING_MODEL": "test-embed-model",
    "EMBEDDING_DIMENSIONS": "3",
    "LLM_API_KEY": "test-sentinel-llm-key",
    "LLM_MODEL": "test-llm-model",
}

VECTOR_ENV = {
    name: RAG_ENV[name]
    for name in (
        "VECTOR_STORE_URL",
        "VECTOR_STORE_COLLECTION",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIMENSIONS",
    )
}


class StubEmbeddingProvider:
    """Deterministic provider double — no model, no download."""

    def embed(self, text):
        return [0.1, 0.2, 0.3]


def compose_rag(env):
    return compose_rag_stack_from_environment(
        environment=env,
        embedding_provider=StubEmbeddingProvider(),
        llm_client=ScriptedLLMClient(),
    )


class QdrantApiKeyParsingTests(unittest.TestCase):
    def test_missing_key_reads_as_none(self):
        self.assertIsNone(qdrant_api_key_from_environment({}))

    def test_blank_key_reads_as_none(self):
        for blank in ("", "   "):
            with self.subTest(blank=blank):
                self.assertIsNone(qdrant_api_key_from_environment(
                    {"QDRANT_API_KEY": blank}))

    def test_configured_key_is_stripped(self):
        self.assertEqual(
            qdrant_api_key_from_environment(
                {"QDRANT_API_KEY": "  padded-key  "}),
            "padded-key",
        )

    def test_non_mapping_reads_as_none(self):
        self.assertIsNone(qdrant_api_key_from_environment(object()))

    def test_config_carries_key_but_hides_it_from_repr(self):
        config = RAGInfrastructureConfig.from_environment(
            {**RAG_ENV, "QDRANT_API_KEY": API_KEY_SENTINEL})
        self.assertEqual(config.qdrant_api_key, API_KEY_SENTINEL)
        self.assertNotIn(API_KEY_SENTINEL, repr(config))

    def test_absent_key_configures_none(self):
        config = RAGInfrastructureConfig.from_environment(dict(RAG_ENV))
        self.assertIsNone(config.qdrant_api_key)


class RagStackApiKeyTests(unittest.TestCase):
    def test_client_receives_configured_key(self):
        import xportra.infrastructure.rag_composition as rag_module

        with mock.patch.object(
                rag_module, "QdrantClient") as client_factory:
            compose_rag({**RAG_ENV, "QDRANT_API_KEY": API_KEY_SENTINEL})
        self.assertEqual(client_factory.call_count, 1)
        _, kwargs = client_factory.call_args
        self.assertEqual(kwargs["url"], RAG_ENV["VECTOR_STORE_URL"])
        self.assertEqual(kwargs["api_key"], API_KEY_SENTINEL)
        self.assertFalse(kwargs["check_compatibility"])

    def test_client_created_keyless_when_absent(self):
        import xportra.infrastructure.rag_composition as rag_module

        with mock.patch.object(
                rag_module, "QdrantClient") as client_factory:
            compose_rag(dict(RAG_ENV))
        self.assertEqual(client_factory.call_count, 1)
        _, kwargs = client_factory.call_args
        self.assertEqual(kwargs["url"], RAG_ENV["VECTOR_STORE_URL"])
        self.assertIsNone(kwargs["api_key"])
        self.assertFalse(kwargs["check_compatibility"])

    def test_missing_url_still_fails_closed(self):
        env = dict(RAG_ENV, QDRANT_API_KEY=API_KEY_SENTINEL)
        del env["VECTOR_STORE_URL"]
        with self.assertRaises(RAGConfigurationError) as raised:
            compose_rag(env)
        self.assertNotIn(API_KEY_SENTINEL, str(raised.exception))

    def test_missing_collection_still_fails_closed(self):
        env = dict(RAG_ENV, QDRANT_API_KEY=API_KEY_SENTINEL)
        del env["VECTOR_STORE_COLLECTION"]
        with self.assertRaises(RAGConfigurationError):
            compose_rag(env)


class IndexSyncApiKeyTests(unittest.TestCase):
    def test_client_receives_configured_key(self):
        import xportra.infrastructure.evidence_upload as upload_module

        with mock.patch.object(
                upload_module, "QdrantClient") as client_factory:
            compose_evidence_index_sync_from_environment(
                {**VECTOR_ENV, "QDRANT_API_KEY": API_KEY_SENTINEL})
        self.assertEqual(client_factory.call_count, 1)
        _, kwargs = client_factory.call_args
        self.assertEqual(kwargs["url"], VECTOR_ENV["VECTOR_STORE_URL"])
        self.assertEqual(kwargs["api_key"], API_KEY_SENTINEL)
        self.assertFalse(kwargs["check_compatibility"])

    def test_client_created_keyless_when_absent(self):
        import xportra.infrastructure.evidence_upload as upload_module

        with mock.patch.object(
                upload_module, "QdrantClient") as client_factory:
            compose_evidence_index_sync_from_environment(
                dict(VECTOR_ENV))
        self.assertEqual(client_factory.call_count, 1)
        _, kwargs = client_factory.call_args
        self.assertIsNone(kwargs["api_key"])
        self.assertFalse(kwargs["check_compatibility"])

    def test_missing_url_still_fails_closed(self):
        env = dict(VECTOR_ENV, QDRANT_API_KEY=API_KEY_SENTINEL)
        del env["VECTOR_STORE_URL"]
        with self.assertRaises(RAGConfigurationError) as raised:
            compose_evidence_index_sync_from_environment(env)
        self.assertNotIn(API_KEY_SENTINEL, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
