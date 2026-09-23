"""Opt-in live OpenRouter test for the Phase 5.15 provider adapter.

GATED: runs only when ``OPENROUTER_LIVE_TEST == "1"`` with
``LLM_API_KEY`` and ``LLM_MODEL`` present in the environment.
Never part of the normal unit suite, never required for CI, no
hardcoded credentials, no credential logging, clearly marked as
live/external. A failure here never weakens the deterministic
unit tests.

Verifies the complete live path (no Qdrant required — the
selection is built from hand-made candidates through the real
ranker/selector/builder):

```text
RAGApplicationService → EvidencePrompt → OpenRouterLLMClient
→ live provider → LLMResponse → GeneratedAnswer → AnswerValidator
```

The live assertion is deliberately behavioral, not textual: the
model's wording is unpredictable, so the test proves execution,
translation, and validation mechanics (canonical response shape,
provider name, validator statuses) rather than any particular
answer text. Uses a small ``max_output_tokens`` to bound cost.
"""

import os
import unittest
from uuid import UUID

GATE = os.environ.get("OPENROUTER_LIVE_TEST", "").strip() == "1"
HAS_KEY = bool(os.environ.get("LLM_API_KEY", "").strip())
HAS_MODEL = bool(os.environ.get("LLM_MODEL", "").strip())

RUN_LIVE = GATE and HAS_KEY and HAS_MODEL


@unittest.skipIf(
    not RUN_LIVE,
    "OPENROUTER_LIVE_TEST != '1' or LLM_API_KEY/LLM_MODEL unset "
    "(opt-in live provider test)",
)
class OpenRouterLiveTests(unittest.TestCase):
    def test_live_generate_validates(self):
        from xportra.domain.answer_validation import (
            CitationAwareAnswerValidator,
        )
        from xportra.domain.evidence_context import (
            DeterministicContextSelector,
            EvidenceContextBudget,
        )
        from xportra.domain.evidence_hybrid import (
            HybridRetrievalCandidate,
        )
        from xportra.domain.evidence_prompt import (
            CitationAwarePromptBuilder,
            EvidencePromptConfig,
        )
        from xportra.domain.evidence_ranking import (
            DeterministicEvidenceRanker,
        )
        from xportra.domain.evidence_retrieval import (
            EvidenceRetrievalResult,
        )
        from xportra.domain.llm import LLMGenerationConfig, LLMResponse
        from xportra.infrastructure.llm import (
            LLMSettings,
            OPENROUTER_PROVIDER_NAME,
            OpenRouterLLMClient,
            answer_from_response,
        )
        from xportra.persistence.tenant import TenantContext

        tenant_id = UUID("11111111-1111-1111-1111-111111111111")
        tenant = TenantContext(tenant_id)
        evidence = EvidenceRetrievalResult(
            tenant_id=tenant_id,
            chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"),
            document_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1"),
            chunk_index=0,
            content="Exporters must file Form NXP before shipment.",
            content_fingerprint="fp-live-1",
            source_id="sonsa/cert-guide",
            source_type="guidance",
            source_location=None,
            document_version="2024.1",
            embedding_model="live-test-model",
            embedding_dimensions=3,
            score=0.9,
        )
        ranked = DeterministicEvidenceRanker().rank(
            [
                HybridRetrievalCandidate(
                    evidence=evidence,
                    semantic_score=0.9,
                    lexical_score=None,
                    retrieval_sources=frozenset({"semantic"}),
                )
            ],
            top_k=1,
        )
        selection = DeterministicContextSelector().select(
            ranked,
            tenant_id=tenant,
            budget=EvidenceContextBudget(4000),
        )
        prompt = CitationAwarePromptBuilder(
            config=EvidencePromptConfig(
                system_instructions=(
                    "Answer only from the evidence. "
                    "Cite it with its [En] labels."
                )
            )
        ).build(selection, information_need="Form NXP deadline")
        settings = LLMSettings.from_environment()
        client = OpenRouterLLMClient(settings=settings)
        try:
            response = client.generate(
                prompt,
                configuration=LLMGenerationConfig(
                    model_identifier=settings.model_identifier,
                    temperature=0.0,
                    max_output_tokens=64,
                ),
                tenant_id=tenant,
            )
        finally:
            client.close()
        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(
            response.provider_name, OPENROUTER_PROVIDER_NAME
        )
        answer = answer_from_response(
            prompt, response, tenant_id=tenant
        )
        validated = CitationAwareAnswerValidator(
            fail_on_invalid_citations=False
        ).validate(answer)
        self.assertIn(
            validated.status, ("valid", "invalid_citations", "empty")
        )


if __name__ == "__main__":
    unittest.main()
