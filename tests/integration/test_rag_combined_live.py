"""Combined live RAG verification for Phase 5.16 (explicitly gated).

GATED — runs only when ALL of the following are present:

* ``QDRANT_URL`` — reachable Qdrant instance;
* ``OPENROUTER_LIVE_TEST == "1"`` — explicit live-LLM consent;
* ``LLM_API_KEY`` / ``LLM_MODEL`` — real OpenRouter credentials;
* ``EMBEDDING_MODEL`` / ``EMBEDDING_DIMENSIONS`` — embedding config.

Never runs in ordinary unit/CI execution. No hardcoded keys,
tenant IDs (generated per run), Qdrant credentials, or secret
URLs. Uses isolated tenants and a uniquely-named throwaway
collection (deleted afterwards), with small controlled evidence
and a bounded ``max_output_tokens``.

Verifies the complete live path (structural citation integrity
only — never "the LLM answered correctly"):

```text
real HTTP API → dev tenant context → real Qdrant + real
sentence-transformers embeddings → real retrieval/ranking/
selection/prompt → real OpenRouter → GeneratedAnswer → real
answer validation → real API response
```

Plus tenant isolation live (A retrieves own; B cannot see A's;
body/scope overrides fail) and live failure paths (invalid
provider credentials → controlled provider error).
"""

import os
import unittest
import uuid
from types import SimpleNamespace

REQUIRED_LIVE_VARS = (
    "QDRANT_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
)

_LIVE_CONSENT = os.environ.get("OPENROUTER_LIVE_TEST", "").strip() == "1"
_MISSING = [
    name for name in REQUIRED_LIVE_VARS
    if not os.environ.get(name, "").strip()
]
RUN_COMBINED = _LIVE_CONSENT and not _MISSING

CONTROLLED_CONTENT = (
    "Controlled live-test rule: exporters must file Form NXP "
    "before shipment."
)


def _live_reason():
    if not _LIVE_CONSENT:
        return "OPENROUTER_LIVE_TEST != '1' (no live consent)"
    return f"missing live configuration: {', '.join(_MISSING)}"


@unittest.skipIf(not RUN_COMBINED, _live_reason())
class CombinedLiveRAGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import dataclasses

        from fastapi.testclient import TestClient

        from xportra.api.app import create_app
        from xportra.domain.evidence_indexing import (
            EmbeddingModelConfig,
            IndexableEvidenceChunk,
        )
        from xportra.domain.evidence_corpus import content_fingerprint
        from xportra.domain.llm import LLMGenerationConfig
        from xportra.infrastructure.rag_composition import (
            RAGInfrastructureConfig,
            compose_rag_stack,
        )
        from xportra.persistence.tenant import TenantContext

        cls.tenant_a_id = uuid.uuid4()
        cls.tenant_b_id = uuid.uuid4()
        cls.tenant_a = TenantContext(cls.tenant_a_id)
        cls.chunk_id = uuid.uuid4()
        cls.document_id = uuid.uuid4()
        cls.collection = f"xportra-live-{uuid.uuid4().hex[:8]}"

        env = {
            "VECTOR_STORE_URL": os.environ["QDRANT_URL"],
            "VECTOR_STORE_COLLECTION": cls.collection,
            "EMBEDDING_MODEL": os.environ["EMBEDDING_MODEL"],
            "EMBEDDING_DIMENSIONS":
                os.environ["EMBEDDING_DIMENSIONS"],
            "LLM_API_KEY": os.environ["LLM_API_KEY"],
            "LLM_MODEL": os.environ["LLM_MODEL"],
        }
        base = RAGInfrastructureConfig.from_environment(env)
        generation = LLMGenerationConfig(
            model_identifier=base.generation.model_identifier,
            temperature=0.0,
            max_output_tokens=128,
        )
        config = dataclasses.replace(base, generation=generation)
        # Real embedding provider (loads the configured model now —
        # live gate only) and real OpenRouter client.
        cls.stack = compose_rag_stack(config)
        cls.stack.ensure_collection()
        provider = cls.stack.embedding_provider
        vector = provider.embed(CONTROLLED_CONTENT)
        chunk = IndexableEvidenceChunk(
            tenant_id=cls.tenant_a_id,
            chunk_id=cls.chunk_id,
            document_id=cls.document_id,
            chunk_index=0,
            content=CONTROLLED_CONTENT,
            content_fingerprint=content_fingerprint(
                CONTROLLED_CONTENT),
            source_id="live/controlled-guide",
            source_type="guidance",
            source_location=None,
            document_version="live.1",
            embedding_model=config.embedding.model_identifier,
            embedding_dimensions=config.embedding.dimensions,
            embedding_vector=vector,
        )
        cls.stack.vector_index.upsert(chunk, tenant_id=cls.tenant_a)
        cls.client = TestClient(
            create_app(
                services=SimpleNamespace(rag=cls.stack.service))
        )

    @classmethod
    def tearDownClass(cls):
        try:
            cls.stack.vector_index._client.delete_collection(
                cls.collection)
        except Exception:
            pass
        try:
            cls.stack.llm_client.close()
        except Exception:
            pass

    def _headers(self, tenant_id):
        return {"X-Development-Tenant-ID": str(tenant_id)}

    def test_live_query_returns_structured_response(self):
        with self.client as client:
            response = client.post(
                "/rag/query",
                headers=self._headers(self.tenant_a_id),
                json={"information_need":
                      "What is the controlled filing rule?"},
            )
        # The composed stack uses the fail-closed validator, so a
        # live model that invents citation labels is a 422 integrity
        # rejection — also a correct machinery outcome. Either way
        # the structure (not the wording) is asserted.
        if response.status_code == 422:
            self.assertEqual(
                response.json()["error"]["code"],
                "citation_integrity_error")
            return
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["status"],
                      ("valid", "invalid_citations", "empty"))
        self.assertIsInstance(body["answer_text"], str)
        labels = {c["label"] for c in body["citations"]}
        self.assertTrue(
            labels <= {"[E1]"},
            f"citations outside authoritative mapping: {labels}")
        self.assertEqual(body["invalid_references"], [])
        for citation in body["citations"]:
            self.assertEqual(
                citation["evidence"]["chunk_id"],
                str(self.chunk_id))
            self.assertEqual(
                citation["evidence"]["document_id"],
                str(self.document_id))

    def test_live_tenant_isolation(self):
        with self.client as client:
            other = client.post(
                "/rag/query",
                headers=self._headers(self.tenant_b_id),
                json={"information_need":
                      "What is the controlled filing rule?"},
            )
            override = client.post(
                "/rag/query",
                headers=self._headers(self.tenant_b_id),
                json={"information_need": "rule",
                      "tenant_id": str(self.tenant_a_id)},
            )
            scoped = client.post(
                "/rag/query",
                headers=self._headers(self.tenant_b_id),
                json={"information_need": "rule",
                      "scope": {"document_id":
                                str(self.document_id)}},
            )
        self.assertIn(other.status_code, (200, 422))
        self.assertNotIn(str(self.chunk_id), other.text)
        self.assertEqual(override.status_code, 422)
        self.assertEqual(scoped.status_code, 200)
        self.assertNotIn(str(self.chunk_id), scoped.text)


@unittest.skipIf(
    not (os.environ.get("OPENROUTER_LIVE_TEST", "").strip() == "1"
         and os.environ.get("LLM_MODEL", "").strip()),
    "OPENROUTER_LIVE_TEST != '1' or LLM_MODEL unset",
)
class ProviderAuthFailureLiveTests(unittest.TestCase):
    def test_invalid_credentials_fail_controlled(self):
        from xportra.domain.evidence_prompt import EvidencePrompt
        from xportra.domain.llm import LLMGenerationConfig
        from xportra.domain.errors import LLMProviderError
        from xportra.infrastructure.llm import (
            LLMSettings,
            OpenRouterLLMClient,
        )

        real_key = os.environ.get("LLM_API_KEY", "").strip()
        bad_key = (real_key + "-invalid-suffix") if real_key \
            else "sk-live-test-invalid-key"
        prompt = EvidencePrompt(
            system_instructions="Answer from the evidence.",
            information_need="live auth probe",
            evidence_context="",
            citations=(),
            evidence_heading="EVIDENCE",
            question_heading="NEED",
            tenant_id=None,
        )
        client = OpenRouterLLMClient(
            settings=LLMSettings(
                api_key=bad_key,
                model_identifier=os.environ["LLM_MODEL"]),
            timeout_seconds=30.0,
        )
        try:
            with self.assertRaises(LLMProviderError):
                client.generate(
                    prompt,
                    configuration=LLMGenerationConfig(
                        model_identifier=os.environ["LLM_MODEL"],
                        max_output_tokens=16),
                )
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
