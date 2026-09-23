"""Provider-neutral LLM infrastructure seam (Phase 5.11).

The smallest infrastructure boundary necessary to make the domain
``LLMClient`` contract concretely usable and testable WITHOUT any
vendor SDK or live API:

- ``LLMSettings`` — credential/model configuration from the canonical
  environment schema (``LLM_API_KEY`` secret, ``LLM_MODEL``), following
  the ``DatabaseSettings.from_environment`` pattern. Secrets are held
  here only — they never enter domain contracts.
- ``LLMProviderError`` re-export — the error translation this layer
  owns (mirroring ``VectorStoreError``).
- ``ScriptedLLMClient`` — a deterministic, provider-neutral
  ``LLMClient`` implementation for tests and local wiring: it holds a
  script of canned ``LLMResponse`` values and an optional failure
  sequence. It performs NO network I/O, NO SDK usage, and NO
  filesystem access; it exists so the domain boundary can be exercised
  end to end without a live provider. Concrete vendor adapters
  (OpenAI/Anthropic/OpenRouter) are deliberately deferred — none is
  introduced in this phase.

Credentials: ``LLMSettings.from_environment()`` reads the canonical
``LLM_API_KEY`` (secret) and ``LLM_MODEL`` variable names from
``docs/architecture/environment-schema.md``. The API key is stored
only on the settings object and is never placed on responses, answers,
prompts, or any domain value object.
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Mapping

import httpx

from xportra.domain.errors import DomainValidationError, LLMProviderError
from xportra.domain.llm import (
    GeneratedAnswer,
    LLMClient,
    LLMGenerationConfig,
    LLMResponse,
    LLMUsage,
)
from xportra.domain.evidence_prompt import EvidencePrompt

logger = logging.getLogger(__name__)

#: OpenRouter (TB-5) OpenAI-compatible endpoint. The default lives
#: here at the infrastructure layer; deployments may override it via
#: the canonical ``LLM_BASE_URL`` variable (see
#: ``RAGInfrastructureConfig``). No other provider is implemented.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

#: Provider identity recorded on ``LLMResponse.provider_name``.
OPENROUTER_PROVIDER_NAME = "openrouter"

#: Explicit finite default for one provider attempt (seconds).
#: Overridable via the canonical ``LLM_TIMEOUT_SECONDS`` variable.
DEFAULT_LLM_TIMEOUT_SECONDS = 60.0

__all__ = [
    "DEFAULT_LLM_TIMEOUT_SECONDS",
    "LLMConfigurationError",
    "LLMSettings",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_PROVIDER_NAME",
    "OpenRouterLLMClient",
    "ScriptedLLMClient",
]


class LLMConfigurationError(RuntimeError):
    """Raised when canonical LLM environment configuration is missing."""


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """Canonical LLM environment configuration (secret-holder only).

    ``api_key`` is a secret: it is accepted from the environment (or an
    explicit mapping, for tests), stored solely on this frozen object,
    and never copied into domain contracts, responses, or answers.
    It is excluded from the repr so tracebacks and logs cannot leak
    it (Phase 5.16 security audit).
    """

    api_key: str = field(repr=False)
    model_identifier: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "LLMSettings":
        values = os.environ if environment is None else environment
        api_key = values.get("LLM_API_KEY", "").strip()
        model = values.get("LLM_MODEL", "").strip()
        if not api_key:
            raise LLMConfigurationError("LLM_API_KEY is required")
        if not model:
            raise LLMConfigurationError("LLM_MODEL is required")
        return cls(api_key=api_key, model_identifier=model)


class ScriptedLLMClient:
    """Deterministic provider-neutral ``LLMClient`` (no I/O, no SDK).

    Returns scripted ``LLMResponse`` values in order and raises the
    scripted exceptions in order, so every domain failure semantic
    (provider failure, timeout, authentication, malformed response)
    is testable without live credentials. It never mutates the prompt,
    never retries, never executes model output, and stores no secrets.
    """

    def __init__(self, responses=None, failures=None):
        self._responses = list(responses or [])
        self._failures = list(failures or [])
        self.calls: list[dict] = []

    def generate(
        self,
        prompt: EvidencePrompt,
        *,
        configuration: LLMGenerationConfig,
        tenant_id=None,
    ) -> LLMResponse:
        self.calls.append({
            "prompt": prompt,
            "configuration": configuration,
            "tenant_id": tenant_id,
        })
        if self._failures:
            failure = self._failures.pop(0)
            if isinstance(failure, LLMProviderError):
                raise failure
            raise LLMProviderError("generate", failure)
        if self._responses:
            return self._responses.pop(0)
        raise LLMProviderError(
            "generate", RuntimeError("no scripted LLM response available"))


def answer_from_response(
    prompt: EvidencePrompt,
    response: LLMResponse,
    *,
    tenant_id,
) -> GeneratedAnswer:
    """Wrap a canonical response into the application answer value.

    The answer boundary seam: a thin, fail-closed composition that
    binds the authoritative prompt, the untrusted model response, and
    internal tenant metadata into a ``GeneratedAnswer``. Performs no
    citation validation and no compliance reasoning — the future
    answer-validation layer belongs elsewhere.
    """
    if not isinstance(prompt, EvidencePrompt):
        raise DomainValidationError("an EvidencePrompt is required")
    if not isinstance(response, LLMResponse):
        raise DomainValidationError("an LLMResponse is required")
    return GeneratedAnswer(
        prompt=prompt, response=response, tenant_id=tenant_id)


def _provider_headers(api_key: str) -> dict[str, str]:
    """Per-request auth headers (the shared client carries no secret)."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _user_content(prompt: EvidencePrompt) -> str:
    """Deterministic provider translation of the structured prompt.

    Preserves the information need, the evidence context, citation
    labels, and evidence ordering exactly — derived field by field
    from the authoritative ``EvidencePrompt``, never summarized,
    truncated, reordered, or rewritten. Tenant identity is never
    included (it travels as internal invocation metadata only).
    """
    evidence = prompt.evidence_context or (
        "(no evidence matched the information need)"
    )
    return "\n".join([
        prompt.question_heading + ":",
        prompt.information_need,
        "",
        prompt.evidence_heading + ":",
        evidence,
    ])


def _optional_count(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise LLMProviderError(
            "generate",
            ValueError(f"provider usage field {name!r} is malformed"),
        )
    return value


def _response_to_canonical(
    data: object, configuration: LLMGenerationConfig
) -> LLMResponse:
    """Translate one provider payload into ``LLMResponse`` (fail closed).

    Every provider/network/shape failure in this phase becomes
    ``LLMProviderError`` — never an empty answer, ``None``, or
    ``[]``. Empty-string model output is preserved exactly per the
    Phase 5.11 contract (only ``None``/missing/non-string content
    is a failure).
    """
    if not isinstance(data, dict):
        raise LLMProviderError(
            "generate", ValueError("provider response is not an object")
        )
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMProviderError(
            "generate", ValueError("provider response has no choices")
        )
    first = choices[0]
    if not isinstance(first, dict):
        raise LLMProviderError(
            "generate", ValueError("provider choice is malformed")
        )
    message = first.get("message")
    if not isinstance(message, dict):
        raise LLMProviderError(
            "generate", ValueError("provider message is malformed")
        )
    content = message.get("content")
    if not isinstance(content, str):
        raise LLMProviderError(
            "generate",
            ValueError("provider response has no generated content"),
        )
    finish_reason = first.get("finish_reason")
    if finish_reason is not None and (
        not isinstance(finish_reason, str) or not finish_reason.strip()
    ):
        raise LLMProviderError(
            "generate", ValueError("provider finish reason is malformed")
        )
    usage = None
    raw_usage = data.get("usage")
    if raw_usage is not None:
        if not isinstance(raw_usage, dict):
            raise LLMProviderError(
                "generate", ValueError("provider usage is malformed")
            )
        usage = LLMUsage(
            input_tokens=_optional_count(
                raw_usage.get("prompt_tokens"), "prompt_tokens"),
            output_tokens=_optional_count(
                raw_usage.get("completion_tokens"), "completion_tokens"),
            total_tokens=_optional_count(
                raw_usage.get("total_tokens"), "total_tokens"),
        )
    raw_model = data.get("model")
    model_identifier = (
        raw_model
        if isinstance(raw_model, str) and raw_model.strip()
        else configuration.model_identifier
    )
    return LLMResponse(
        generated_text=content,
        model_identifier=model_identifier,
        finish_reason=finish_reason,
        usage=usage,
        provider_name=OPENROUTER_PROVIDER_NAME,
    )


class OpenRouterLLMClient:
    """The single production ``LLMClient`` (OpenRouter, TB-5).

    Speaks the provider's OpenAI-compatible chat-completions API
    over ``httpx`` (existing dependency — no vendor SDK). The
    transport is a small explicit boundary: an ``httpx.Client``
    may be injected (deterministic tests use ``MockTransport``);
    otherwise one client with the configured finite timeout is
    built for the adapter's lifetime.

    One ``generate`` call performs exactly one provider attempt —
    no retries, no fallback, no model substitution. Tenant
    identity is internal metadata only and never enters the
    provider-visible prompt. Model output is returned untrusted
    (citation validation stays in Phase 5.12).
    """

    def __init__(
        self,
        *,
        settings: LLMSettings,
        base_url: str = OPENROUTER_BASE_URL,
        timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not isinstance(settings, LLMSettings):
            raise DomainValidationError(
                "canonical LLM settings are required")
        if not isinstance(base_url, str) or not base_url.strip():
            raise DomainValidationError(
                "a provider base URL is required")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise DomainValidationError(
                "a finite positive request timeout is required")
        if http_client is not None and not isinstance(
                http_client, httpx.Client):
            raise DomainValidationError(
                "an httpx client is required")
        self._settings = settings
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = float(timeout_seconds)
        self._client = http_client or httpx.Client(
            timeout=self._timeout_seconds)
        self._owns_client = http_client is None

    @property
    def provider_name(self) -> str:
        return OPENROUTER_PROVIDER_NAME

    def close(self) -> None:
        """Release the owned HTTP client (no-op for injected ones)."""
        if self._owns_client:
            self._client.close()

    def generate(
        self,
        prompt: EvidencePrompt,
        *,
        configuration: LLMGenerationConfig,
        tenant_id=None,
    ) -> LLMResponse:
        if not isinstance(prompt, EvidencePrompt):
            raise DomainValidationError("an EvidencePrompt is required")
        if not isinstance(
                configuration, LLMGenerationConfig):
            raise DomainValidationError(
                "an LLMGenerationConfig is required")
        body = {
            "model": configuration.model_identifier,
            "messages": [
                {
                    "role": "system",
                    "content": prompt.system_instructions,
                },
                {"role": "user", "content": _user_content(prompt)},
            ],
            "temperature": configuration.temperature,
            "max_tokens": configuration.max_output_tokens,
        }
        url = self._base_url + "/chat/completions"
        started = time.perf_counter()
        try:
            response = self._client.post(
                url,
                json=body,
                headers=_provider_headers(self._settings.api_key),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            latency_ms = int(
                (time.perf_counter() - started) * 1000)
            logger.warning(
                "openrouter generate failed model=%s latency_ms=%d "
                "error=%s",
                configuration.model_identifier,
                latency_ms,
                type(exc).__name__,
            )
            raise LLMProviderError("generate", exc) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                "generate",
                ValueError("provider response is not valid JSON"),
            ) from exc
        result = _response_to_canonical(data, configuration)
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "openrouter generate ok model=%s latency_ms=%d "
            "finish_reason=%s empty=%s",
            result.model_identifier,
            latency_ms,
            result.finish_reason,
            result.is_empty,
        )
        return result
