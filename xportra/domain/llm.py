"""LLM invocation & answer boundary for Phase 5.11.

The first explicit boundary between the deterministic evidence/prompt
subsystem (Phases 5.1–5.10) and an external LLM:

```text
EvidencePrompt            (Phase 5.10 — authoritative, structured)
      ↓
LLMClient (protocol)      (this module — provider-independent contract)
      ↓
LLMResponse               (normalized, provider-independent)
      ↓
GeneratedAnswer           (application wrapper — answers, not verdicts)
```

Provider SDKs (OpenAI/Anthropic/OpenRouter/HTTP) belong in
``xportra/infrastructure`` behind the ``LLMClient`` protocol — never in
domain contracts, mirroring the Phase 4.4/5.1 vector-store boundary
(domain protocol + infrastructure adapter).

Failure semantics: fail closed. Configuration validation happens
BEFORE any external call; provider/infrastructure failures are
translated at the infrastructure boundary into
``LLMProviderError(operation, cause)`` (mirroring ``VectorStoreError``)
and are never converted into an empty answer, ``None``, or ``[]``.

Security: generated model output is UNTRUSTED. The adapter only
obtains output — it never executes generated code/SQL, invokes tools,
performs filesystem operations, or triggers external actions. Model
output never manufactures citations: ``EvidencePrompt.citations``
remain the only authoritative evidence references, and text appearing
in model output proves nothing about actual citation correctness
(validation is a later answer-validation boundary).

Tenant handling: tenant identity is carried as internal invocation
metadata only — it is NEVER injected into model-visible text unless a
future explicit product requirement demands it.

No retries: none in this phase (no existing project-wide retry policy
to inherit); retries affect cost/latency/idempotency and must be
designed deliberately later. No credentials in domain contracts;
``LLM_API_KEY`` handling belongs to infrastructure configuration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .errors import DomainValidationError
from .evidence_prompt import EvidencePrompt

MAX_TEMPERATURE = 2.0


@dataclass(frozen=True, slots=True)
class LLMGenerationConfig:
    """Immutable, validated generation configuration.

    Deliberately minimal, provider-neutral fields only:

    - ``model_identifier`` — non-empty string (the canonical
      ``LLM_MODEL`` value flows in here via infrastructure config;
      no default is invented).
    - ``temperature`` — finite float in ``[0.0, 2.0]`` (the range
      supported by both major provider families); booleans, strings,
      ``None``, NaN, and infinities are rejected fail-closed.
    - ``max_output_tokens`` — positive integer (bool/string/None
      rejected).

    No provider-specific fields (stop sequences, top_p, penalties,
    endpoints) are invented — provider adapters translate this
    canonical config into their own request formats.
    """

    model_identifier: str
    temperature: float = 0.0
    max_output_tokens: int = 1024

    def __post_init__(self) -> None:
        if not isinstance(self.model_identifier, str) or (
            not self.model_identifier.strip()
        ):
            raise DomainValidationError(
                "LLM model identifier is required")
        if (
            isinstance(self.temperature, bool)
            or not isinstance(self.temperature, (int, float))
            or not math.isfinite(self.temperature)
            or self.temperature < 0.0
            or self.temperature > MAX_TEMPERATURE
        ):
            raise DomainValidationError(
                "temperature must be a finite number in "
                f"[0.0, {MAX_TEMPERATURE}]")
        if (
            isinstance(self.max_output_tokens, bool)
            or not isinstance(self.max_output_tokens, int)
            or self.max_output_tokens <= 0
        ):
            raise DomainValidationError(
                "max_output_tokens must be a positive integer")

    def to_record(self) -> dict:
        return {
            "model_identifier": self.model_identifier,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Provider-neutral token-usage accounting (optional fields).

    All fields optional — some providers/reasoning modes do not
    expose them. Never inferred; only reported values are stored.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def to_record(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Normalized, provider-independent model response.

    The canonical representation crossing the LLM boundary — never a
    raw provider SDK object. Optional fields (``finish_reason``,
    ``usage``, ``provider_name``) remain explicitly optional so every
    provider can conform; no provider-specific fields leak into the
    canonical model. No secrets, no API keys, no request headers are
    ever stored.
    """

    generated_text: str
    model_identifier: str
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    provider_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.generated_text, str):
            raise DomainValidationError("generated text is malformed")
        if not isinstance(self.model_identifier, str) or (
            not self.model_identifier.strip()
        ):
            raise DomainValidationError(
                "response model identifier is required")
        if self.finish_reason is not None and (
            not isinstance(self.finish_reason, str)
            or not self.finish_reason.strip()
        ):
            raise DomainValidationError("finish reason is malformed")
        if self.usage is not None and not isinstance(
                self.usage, LLMUsage):
            raise DomainValidationError("usage is malformed")
        if self.provider_name is not None and (
            not isinstance(self.provider_name, str)
            or not self.provider_name.strip()
        ):
            raise DomainValidationError("provider name is malformed")

    @property
    def is_empty(self) -> bool:
        """True when the model produced no substantive output."""
        return not self.generated_text.strip()

    def to_record(self) -> dict:
        return {
            "generated_text": self.generated_text,
            "model_identifier": self.model_identifier,
            "finish_reason": self.finish_reason,
            "usage": self.usage.to_record() if self.usage else None,
            "provider_name": self.provider_name,
        }


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    """Application-level answer wrapper: answers, never verdicts.

    Separates the raw model response (``LLMResponse``) from the
    application-facing answer value, carrying the prompt and tenant
    as internal invocation metadata and leaving explicit room for a
    future answer-validation layer (citation validation, untrusted-
    output policy) WITHOUT claiming any compliance semantics.

    ``[E1]``-style references inside ``answer_text`` are UNTRUSTED
    model output — their presence proves nothing about actual
    citation correctness; validation belongs to a later boundary.
    """

    prompt: EvidencePrompt
    response: LLMResponse
    tenant_id: Any

    @property
    def answer_text(self) -> str:
        return self.response.generated_text

    @property
    def is_empty(self) -> bool:
        return self.response.is_empty

    def to_record(self) -> dict:
        return {
            "response": self.response.to_record(),
            "citations": [
                c.to_record() for c in self.prompt.citations],
            "prompt_is_empty": self.prompt.is_empty,
        }


@runtime_checkable
class LLMClient(Protocol):
    """Provider-independent LLM invocation contract.

    Implementations live in infrastructure and wrap exactly one
    provider SDK; the domain depends only on this protocol, never on
    a vendor SDK — mirroring the ``EmbeddingProvider`` convention.

    Contract:

    - receives the AUTHORITATIVE structured ``EvidencePrompt``
      (never a re-rendered copy; render only for provider transport,
      preserving the structured prompt alongside the invocation);
    - must not mutate prompt, citations, evidence, or provenance;
    - returns a canonical ``LLMResponse`` — never a provider object;
    - fail closed: configuration and malformed-response failures
      raise ``DomainValidationError``; provider/infrastructure
      failures raise ``LLMProviderError`` — never an empty success;
    - treats model output as untrusted data (no execution, no tools,
      no filesystem, no external actions);
    - no automatic retries (none exist project-wide; retries affect
      cost/latency/idempotency and must be designed deliberately).
    """

    def generate(
        self,
        prompt: EvidencePrompt,
        *,
        configuration: LLMGenerationConfig,
        tenant_id: Any = None,
    ) -> LLMResponse:
        ...


__all__ = [
    "GeneratedAnswer",
    "LLMClient",
    "LLMGenerationConfig",
    "LLMProviderError",
    "LLMResponse",
    "LLMUsage",
    "MAX_TEMPERATURE",
]
