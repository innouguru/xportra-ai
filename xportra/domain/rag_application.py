"""RAG application service for Phase 5.13.

Thin application-level orchestration boundary that composes the completed
Phase 5 domain chain into a single production-facing entry point:

```text
information_need
    ↓
EvidenceContextPipeline     (Phase 5.8: retrieval + ranking + selection)
    ↓
EvidenceContextSelection
    ↓
CitationAwarePromptBuilder  (Phase 5.10: prompt construction)
    ↓
EvidencePrompt
    ↓
LLMClient.generate(...)     (Phase 5.11: LLM invocation)
    ↓
LLMResponse
    ↓
GeneratedAnswer             (Phase 5.11 answer wrapping)
    ↓
AnswerValidator.validate(...) (Phase 5.12: citation integrity)
    ↓
ValidatedAnswer
```

This module is ORCHESTRATION ONLY. It reimplements nothing: no
retrieval, no ranking, no context selection, no prompt construction,
no LLM provider call, no citation parsing, no citation validation.
It performs no Qdrant call, no embedding call, no HTTP call, no
database access, and no compliance reasoning. It imports no
infrastructure package: the answer-wrapping seam is the trivial
``GeneratedAnswer`` construction the domain already owns (the
infrastructure ``answer_from_response`` helper remains a thin alias
for standalone use).

Tenant identity is an execution-level keyword (``require_tenant_context``),
never a field of any value object here, so unscoped invocation cannot
be expressed. Failures from any collaborator propagate unchanged and
are never converted into an empty successful answer.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .answer_validation import AnswerValidator, ValidatedAnswer
from .errors import DomainValidationError, require_tenant_context
from .evidence_context import EvidenceContextBudget
from .evidence_context_pipeline import EvidenceContextPipelineContract
from .evidence_prompt import CitationAwarePromptBuilder, EvidencePromptConfig
from .llm import (
    GeneratedAnswer,
    LLMClient,
    LLMGenerationConfig,
    LLMResponse,
)
from .evidence_retrieval import DEFAULT_TOP_K


@runtime_checkable
class RAGApplicationContract(Protocol):
    """Application-facing RAG query contract.

    One call: an information need in, a validated answer out.
    Implementations must delegate to the injected domain boundaries
    without reimplementing any retrieval, ranking, selection, prompt,
    LLM, or validation logic.
    """

    def query(
        self,
        information_need: str,
        *,
        tenant_id: Any,
        mode: str,
        context_budget: EvidenceContextBudget,
        scope: Any | None = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
    ) -> ValidatedAnswer: ...


class RAGApplicationService:
    """Compose the complete Phase 5 RAG chain into one application call.

    Dependency injection
    --------------------
    All collaborators are injected explicitly — the orchestrator never
    constructs a context pipeline, a prompt builder, an embedding
    provider, a Qdrant client, an LLM SDK client, or any
    infrastructure adapter:

    ```text
    RAGApplicationService
        ↓ EvidenceContextPipeline    (Phase 5.8)
        ↓ CitationAwarePromptBuilder (Phase 5.10)
        ↓ LLMClient                  (Phase 5.11)
        ↓ AnswerValidator            (Phase 5.12)
    ```

    Delegation
    ----------
    1. Context: ``information_need``, ``tenant_id``, ``mode``,
       ``context_budget``, ``scope``, ``top_k``, and
       ``candidate_pool`` are forwarded unchanged to the injected
       ``EvidenceContextPipeline`` — the single authoritative
       retrieval/ranking/selection boundary. Mode/scope/top-k
       validation stays where it already lives (Phases 5.3/5.6);
       this layer introduces no new mode and no silent conversion.
    2. Prompt: the resulting selection and the normalized
       information need go to the injected
       ``CitationAwarePromptBuilder`` — the single authoritative
       prompt-construction boundary.
    3. LLM: the authoritative structured ``EvidencePrompt`` (never a
       re-rendered copy) and the injected ``LLMGenerationConfig``
       go to the injected ``LLMClient``. Tenant identity travels
       as internal invocation metadata only.
    4. Answer: the ``LLMResponse`` is bound to the prompt and tenant
       into a ``GeneratedAnswer`` (structural fail-closed check
       only — the injected client must return a canonical
       ``LLMResponse``, never a provider object).
    5. Validation: the ``GeneratedAnswer`` goes to the injected
       ``AnswerValidator`` — the single authoritative citation
       integrity boundary. Its invalid-citation policy
       (fail-closed raising vs. structured ``invalid_citations``
       status) is owned by the injected validator instance, not
       by per-call flags here.

    Result integrity
    ----------------
    The orchestrator is not a transformation boundary: the
    ``ValidatedAnswer`` returned is the exact object produced by
    the injected validator.

    Failure semantics
    -----------------
    No broad exception handling: retrieval, ranking,
    context-selection, prompt-construction, LLM provider, and
    answer-validation failures propagate unchanged from the
    responsible boundary. Failures are never converted into an
    empty successful answer, and empty model output stays a
    distinct valid ``empty`` status owned by Phases 5.11/5.12.
    """

    def __init__(
        self,
        *,
        context_pipeline: EvidenceContextPipelineContract,
        prompt_builder: CitationAwarePromptBuilder,
        llm_client: LLMClient,
        llm_generation_config: LLMGenerationConfig,
        answer_validator: AnswerValidator,
    ) -> None:
        if (
            context_pipeline is None
            or isinstance(context_pipeline, (str, bytes))
            or not callable(
                getattr(context_pipeline, "select_context", None))
        ):
            raise DomainValidationError(
                "a context pipeline is required")
        if (
            prompt_builder is None
            or isinstance(prompt_builder, (str, bytes))
            or not callable(getattr(prompt_builder, "build", None))
        ):
            raise DomainValidationError(
                "a prompt builder is required")
        if (
            llm_client is None
            or isinstance(llm_client, (str, bytes))
            or not callable(getattr(llm_client, "generate", None))
        ):
            raise DomainValidationError(
                "an LLM client is required")
        if not isinstance(
                llm_generation_config, LLMGenerationConfig):
            raise DomainValidationError(
                "an LLMGenerationConfig is required")
        if (
            answer_validator is None
            or isinstance(answer_validator, (str, bytes))
            or not callable(getattr(answer_validator, "validate", None))
        ):
            raise DomainValidationError(
                "an answer validator is required")
        self._context_pipeline = context_pipeline
        self._prompt_builder = prompt_builder
        self._llm_client = llm_client
        self._llm_generation_config = llm_generation_config
        self._answer_validator = answer_validator

    def query(
        self,
        information_need: str,
        *,
        tenant_id: Any,
        mode: str,
        context_budget: EvidenceContextBudget,
        scope: Any | None = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
    ) -> ValidatedAnswer:
        """Execute the complete RAG chain for one information need.

        Returns the exact ``ValidatedAnswer`` produced by the
        injected validator.
        """
        require_tenant_context(tenant_id)
        if not isinstance(information_need, str):
            raise DomainValidationError(
                "an information need is required")
        normalized_need = " ".join(information_need.split())
        if not normalized_need:
            raise DomainValidationError(
                "an information need is required")
        if not isinstance(context_budget, EvidenceContextBudget):
            raise DomainValidationError(
                "an EvidenceContextBudget is required")

        selection = self._context_pipeline.select_context(
            normalized_need,
            tenant_id=tenant_id,
            mode=mode,
            context_budget=context_budget,
            scope=scope,
            top_k=top_k,
            candidate_pool=candidate_pool,
        )

        prompt = self._prompt_builder.build(
            selection, information_need=normalized_need)

        response = self._llm_client.generate(
            prompt,
            configuration=self._llm_generation_config,
            tenant_id=tenant_id,
        )
        if not isinstance(response, LLMResponse):
            raise DomainValidationError(
                "LLM client produced malformed output")

        answer = GeneratedAnswer(
            prompt=prompt, response=response, tenant_id=tenant_id)
        return self._answer_validator.validate(answer)


def build_rag_application_service(
    *,
    context_pipeline: EvidenceContextPipelineContract,
    prompt_config: EvidencePromptConfig,
    llm_client: LLMClient,
    llm_generation_config: LLMGenerationConfig,
    answer_validator: AnswerValidator | None = None,
) -> RAGApplicationService:
    """Smallest composition helper: wire the concrete RAG service.

    Combines caller-supplied collaborators with the deterministic
    Phase 5.10 ``CitationAwarePromptBuilder`` (built from the given
    prompt config) and the fail-closed Phase 5.12
    ``CitationAwareAnswerValidator`` (the default when
    ``answer_validator`` is omitted). This is a construction
    boundary only: no dependency-injection framework, no
    application startup wiring, no infrastructure construction.
    """
    from .answer_validation import CitationAwareAnswerValidator

    if answer_validator is None:
        answer_validator = CitationAwareAnswerValidator()
    prompt_builder = CitationAwarePromptBuilder(config=prompt_config)
    return RAGApplicationService(
        context_pipeline=context_pipeline,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        llm_generation_config=llm_generation_config,
        answer_validator=answer_validator,
    )


__all__ = [
    "RAGApplicationService",
    "RAGApplicationContract",
    "build_rag_application_service",
]
