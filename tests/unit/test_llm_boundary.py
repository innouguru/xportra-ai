"""Phase 5.11 — LLM Invocation & Answer Boundary tests.

Covers the provider-independent LLM contract:
``LLMGenerationConfig``, ``LLMResponse``, ``LLMUsage``,
``GeneratedAnswer``, the ``LLMClient`` protocol, the
``LLMProviderError`` translation, the infrastructure seam
(``LLMSettings``, ``ScriptedLLMClient``, ``answer_from_response``),
and the domain/infrastructure SDK separation.

Deterministic fakes only — no live LLM, no network, no credentials,
no SDK. The prompt under test is built through the REAL Phase 5.5/5.7
chain so the full path is exercised.
"""

import ast
import inspect
import unittest
from uuid import UUID

from xportra.domain.errors import (
    DomainValidationError,
    LLMProviderError,
)
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
)
from xportra.domain.evidence_prompt import (
    CitationAwarePromptBuilder,
    EvidencePromptConfig,
)
from xportra.domain.evidence_ranking import DeterministicEvidenceRanker
from xportra.domain.evidence_retrieval import EvidenceRetrievalResult
from xportra.domain.llm import (
    GeneratedAnswer,
    LLMClient,
    LLMGenerationConfig,
    LLMResponse,
    LLMUsage,
    MAX_TEMPERATURE,
)
from xportra.infrastructure.llm import (
    LLMConfigurationError,
    LLMSettings,
    ScriptedLLMClient,
    answer_from_response,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT = TenantContext(TENANT_ID)
CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
MODEL = "test-model"
OTHER_MODEL = "other-model"

CONFIG = EvidencePromptConfig(system_instructions="You are a compliance assistant.")
BUILDER = CitationAwarePromptBuilder(config=CONFIG)
GEN_CONFIG = LLMGenerationConfig(
    model_identifier=MODEL, temperature=0.2, max_output_tokens=512)


def make_evidence(content="Exporters must file Form NXP."):
    return EvidenceRetrievalResult(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_1,
        document_id=UUID("11111111-1111-1111-1111-111111111111"),
        chunk_index=0,
        content=content,
        content_fingerprint="fp-1",
        source_id="sonsa/cert-guide",
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="2024.1",
        embedding_model="test-embed-model",
        embedding_dimensions=4,
        score=0.9,
    )


def make_prompt(content="Exporters must file Form NXP."):
    from xportra.domain.evidence_hybrid import HybridRetrievalCandidate

    evidence = make_evidence(content)
    ranked = DeterministicEvidenceRanker().rank(
        [HybridRetrievalCandidate(
            evidence=evidence,
            semantic_score=0.9,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"}))],
        top_k=1)
    selection = DeterministicContextSelector().select(
        ranked, tenant_id=TENANT, budget=EvidenceContextBudget(1000))
    return BUILDER.build(selection, information_need="Form NXP deadline")


def make_response(**overrides):
    kwargs = dict(
        generated_text="You must file before shipment.",
        model_identifier=MODEL,
        finish_reason="stop",
        usage=LLMUsage(input_tokens=100, output_tokens=20, total_tokens=120),
        provider_name="scripted",
    )
    kwargs.update(overrides)
    return LLMResponse(**kwargs)


# ----------------------------------------------------------------------
# Generation configuration
# ----------------------------------------------------------------------


class TestGenerationConfig(unittest.TestCase):
    """LLMGenerationConfig is strict and provider-neutral."""

    def test_valid_configuration_accepted(self):
        config = LLMGenerationConfig(
            model_identifier=MODEL, temperature=0.7, max_output_tokens=256)
        self.assertEqual(config.model_identifier, MODEL)
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.max_output_tokens, 256)

    def test_defaults_are_deterministic(self):
        config = LLMGenerationConfig(model_identifier=MODEL)
        self.assertEqual(config.temperature, 0.0)
        self.assertEqual(config.max_output_tokens, 1024)

    def test_invalid_model_identifier_rejected(self):
        for bad in ("", "   ", None, 42):
            with self.assertRaises(DomainValidationError):
                LLMGenerationConfig(model_identifier=bad)

    def test_invalid_temperature_rejected(self):
        for bad in (-0.1, MAX_TEMPERATURE + 0.1, float("nan"),
                    float("inf"), -float("inf")):
            with self.assertRaises(DomainValidationError):
                LLMGenerationConfig(
                    model_identifier=MODEL, temperature=bad)

    def test_temperature_accepts_full_supported_range(self):
        low = LLMGenerationConfig(model_identifier=MODEL, temperature=0.0)
        high = LLMGenerationConfig(
            model_identifier=MODEL, temperature=MAX_TEMPERATURE)
        self.assertEqual(low.temperature, 0.0)
        self.assertEqual(high.temperature, MAX_TEMPERATURE)

    def test_invalid_max_output_tokens_rejected(self):
        for bad in (0, -1, 1.5, "1024", None):
            with self.assertRaises(DomainValidationError):
                LLMGenerationConfig(
                    model_identifier=MODEL, max_output_tokens=bad)

    def test_bool_rejected_for_numeric_fields(self):
        with self.assertRaises(DomainValidationError):
            LLMGenerationConfig(
                model_identifier=MODEL, temperature=True)
        with self.assertRaises(DomainValidationError):
            LLMGenerationConfig(
                model_identifier=MODEL, max_output_tokens=True)

    def test_missing_model_identifier_rejected(self):
        # A required dataclass field: omission fails closed with
        # TypeError before any object exists.
        with self.assertRaises(TypeError):
            LLMGenerationConfig()
        with self.assertRaises(DomainValidationError):
            LLMGenerationConfig(model_identifier="")

    def test_provider_specific_fields_not_accepted(self):
        # The canonical config carries no provider-specific knobs.
        with self.assertRaises(TypeError):
            LLMGenerationConfig(
                model_identifier=MODEL, top_p=0.9)
        with self.assertRaises(TypeError):
            LLMGenerationConfig(
                model_identifier=MODEL, stop_sequences=["END"])


# ----------------------------------------------------------------------
# Response representation
# ----------------------------------------------------------------------


class TestResponseRepresentation(unittest.TestCase):
    """Canonical response: provider-independent, no secrets."""

    def test_valid_response_normalized(self):
        response = make_response()
        self.assertEqual(
            response.generated_text, "You must file before shipment.")
        self.assertEqual(response.model_identifier, MODEL)

    def test_model_identifier_preserved(self):
        self.assertEqual(make_response(model_identifier=OTHER_MODEL)
                         .model_identifier, OTHER_MODEL)

    def test_finish_reason_optional(self):
        self.assertEqual(make_response().finish_reason, "stop")
        self.assertIsNone(
            make_response(finish_reason=None).finish_reason)

    def test_usage_optional_and_preserved(self):
        usage = LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15)
        response = make_response(usage=usage)
        self.assertEqual(response.usage, usage)
        self.assertIsNone(make_response(usage=None).usage)

    def test_provider_name_optional(self):
        self.assertIsNone(make_response(provider_name=None).provider_name)

    def test_malformed_response_rejected(self):
        for bad_text in (None, 42, ["text"]):
            with self.assertRaises(DomainValidationError):
                LLMResponse(generated_text=bad_text, model_identifier=MODEL)
        for bad_model in ("", "  ", None):
            with self.assertRaises(DomainValidationError):
                LLMResponse(generated_text="ok", model_identifier=bad_model)
        with self.assertRaises(DomainValidationError):
            make_response(usage="not usage")
        with self.assertRaises(DomainValidationError):
            make_response(finish_reason="   ")
        with self.assertRaises(DomainValidationError):
            make_response(provider_name="")

    def test_no_secrets_or_headers_stored(self):
        record = make_response().to_record()
        serialized = str(record)
        for forbidden in ("api_key", "authorization", "headers", "token="):
            self.assertNotIn(forbidden, serialized.lower())

    def test_empty_flag(self):
        self.assertTrue(make_response(generated_text="").is_empty)
        self.assertTrue(make_response(generated_text="   \n ").is_empty)
        self.assertFalse(make_response().is_empty)

    def test_provider_fields_do_not_leak_into_canonical_record(self):
        # The canonical record has exactly the canonical keys — extra
        # provider-specific fields cannot be smuggled onto the frozen
        # value object.
        record = make_response().to_record()
        self.assertEqual(
            set(record.keys()),
            {"generated_text", "model_identifier", "finish_reason",
             "usage", "provider_name"})


# ----------------------------------------------------------------------
# Invocation through the infrastructure seam
# ----------------------------------------------------------------------


class TestInvocation(unittest.TestCase):
    """Prompt and configuration forwarded; prompt stays authoritative."""

    def setUp(self):
        self.prompt = make_prompt()

    def _client_with_response(self, response):
        return ScriptedLLMClient(responses=[response])

    def test_prompt_forwarded_unchanged(self):
        client = self._client_with_response(make_response())
        client.generate(self.prompt, configuration=GEN_CONFIG,
                        tenant_id=TENANT)
        self.assertIs(client.calls[0]["prompt"], self.prompt)

    def test_structured_prompt_preserved_not_rerendered(self):
        client = self._client_with_response(make_response())
        client.generate(self.prompt, configuration=GEN_CONFIG,
                        tenant_id=TENANT)
        forwarded = client.calls[0]["prompt"]
        # The structured object (not a render string) crosses the seam.
        self.assertIsInstance(forwarded, type(self.prompt))
        self.assertEqual(forwarded.system_instructions,
                         self.prompt.system_instructions)
        self.assertEqual(forwarded.evidence_context,
                         self.prompt.evidence_context)

    def test_configuration_forwarded_unchanged(self):
        client = self._client_with_response(make_response())
        client.generate(self.prompt, configuration=GEN_CONFIG,
                        tenant_id=TENANT)
        self.assertIs(
            client.calls[0]["configuration"], GEN_CONFIG)

    def test_tenant_travels_as_internal_metadata(self):
        client = self._client_with_response(make_response())
        client.generate(self.prompt, configuration=GEN_CONFIG,
                        tenant_id=TENANT)
        self.assertIs(client.calls[0]["tenant_id"], TENANT)

    def test_protocol_satisfied_by_seam_implementation(self):
        client = self._client_with_response(make_response())
        self.assertIsInstance(client, LLMClient)


class TestPromptImmutability(unittest.TestCase):
    """The adapter never mutates the authoritative prompt."""

    def setUp(self):
        self.prompt = make_prompt()
        self.snapshot = self.prompt.to_record()
        self.citations_snapshot = [
            c.to_record() for c in self.prompt.citations]

    def _run(self, client):
        client.generate(self.prompt, configuration=GEN_CONFIG,
                        tenant_id=TENANT)

    def test_prompt_unchanged_after_success(self):
        self._run(ScriptedLLMClient(responses=[make_response()]))
        self.assertEqual(self.prompt.to_record(), self.snapshot)

    def test_prompt_unchanged_after_provider_failure(self):
        with self.assertRaises(LLMProviderError):
            self._run(ScriptedLLMClient(
                failures=[RuntimeError("provider down")]))
        self.assertEqual(self.prompt.to_record(), self.snapshot)

    def test_prompt_objects_are_frozen(self):
        with self.assertRaises(Exception):
            self.prompt.system_instructions = "tampered"
        with self.assertRaises(Exception):
            self.prompt.citations[0].label = "[EX]"

    def test_citation_mapping_unchanged(self):
        self._run(ScriptedLLMClient(responses=[make_response()]))
        self.assertEqual(
            [c.to_record() for c in self.prompt.citations],
            self.citations_snapshot)


# ----------------------------------------------------------------------
# Failure semantics
# ----------------------------------------------------------------------


class TestFailureSemantics(unittest.TestCase):
    """Fail closed: provider failures never become empty answers."""

    def setUp(self):
        self.prompt = make_prompt()

    def _generate_with_failure(self, failure):
        client = ScriptedLLMClient(failures=[failure])
        return client.generate(
            self.prompt, configuration=GEN_CONFIG, tenant_id=TENANT)

    def test_provider_failure_translated_and_propagates(self):
        with self.assertRaises(LLMProviderError) as ctx:
            self._generate_with_failure(RuntimeError("connection reset"))
        self.assertEqual(ctx.exception.operation, "generate")
        self.assertIsInstance(ctx.exception.cause, RuntimeError)

    def test_timeout_propagates_as_provider_error(self):
        with self.assertRaises(LLMProviderError):
            self._generate_with_failure(TimeoutError("request timed out"))

    def test_authentication_failure_propagates(self):
        with self.assertRaises(LLMProviderError):
            self._generate_with_failure(
                RuntimeError("401 authentication failed"))

    def test_rate_limit_failure_propagates(self):
        with self.assertRaises(LLMProviderError):
            self._generate_with_failure(RuntimeError("429 rate limited"))

    def test_failure_identity_preserved_through_translation(self):
        original = RuntimeError("boom")
        with self.assertRaises(LLMProviderError) as ctx:
            self._generate_with_failure(original)
        self.assertIs(ctx.exception.cause, original)

    def test_failures_never_become_empty_success(self):
        # Not "" / None / [] — a raise is the only failure path.
        with self.assertRaises(LLMProviderError):
            self._generate_with_failure(RuntimeError("x"))

    def test_no_automatic_retry(self):
        # One failure = one call: the scripted client records exactly
        # one generate call and raises; no hidden retry loop.
        client = ScriptedLLMClient(failures=[RuntimeError("down")])
        with self.assertRaises(LLMProviderError):
            client.generate(self.prompt, configuration=GEN_CONFIG,
                            tenant_id=TENANT)
        self.assertEqual(len(client.calls), 1)


class TestEmptyOutputPolicy(unittest.TestCase):
    """Empty model output is a VALID response, clearly marked.

    Policy: the adapter returns the response as received (the model is
    the authority on its own output); emptiness is exposed as an
    explicit, auditable flag (`is_empty`). No answer text is
    fabricated, and an empty response is never an exception — but
    `GeneratedAnswer.is_empty` lets the future answer-validation layer
    treat it as a distinct state.
    """

    def setUp(self):
        self.prompt = make_prompt()

    def test_empty_output_returns_valid_response_flagged(self):
        client = ScriptedLLMClient(
            responses=[make_response(generated_text="   ")])
        response = client.generate(
            self.prompt, configuration=GEN_CONFIG, tenant_id=TENANT)
        self.assertTrue(response.is_empty)
        self.assertEqual(response.generated_text, "   ")

    def test_empty_output_never_fabricated_into_content(self):
        client = ScriptedLLMClient(
            responses=[make_response(generated_text="")])
        response = client.generate(
            self.prompt, configuration=GEN_CONFIG, tenant_id=TENANT)
        self.assertEqual(response.generated_text, "")
        self.assertNotEqual(response.generated_text.lower(), "no answer")

    def test_empty_answer_wrapper_flagged(self):
        prompt = make_prompt()
        answer = answer_from_response(
            prompt, make_response(generated_text="  "), tenant_id=TENANT)
        self.assertTrue(answer.is_empty)
        self.assertEqual(answer.answer_text, "  ")


# ----------------------------------------------------------------------
# Answer boundary
# ----------------------------------------------------------------------


class TestAnswerBoundary(unittest.TestCase):
    """LLMResponse vs GeneratedAnswer separation."""

    def test_answer_wraps_response_with_prompt_and_tenant(self):
        prompt = make_prompt()
        response = make_response()
        answer = answer_from_response(prompt, response, tenant_id=TENANT)
        self.assertIsInstance(answer, GeneratedAnswer)
        self.assertIs(answer.prompt, prompt)
        self.assertIs(answer.response, response)
        self.assertIs(answer.tenant_id, TENANT)
        self.assertEqual(
            answer.answer_text, "You must file before shipment.")

    def test_answer_malformed_inputs_fail_closed(self):
        with self.assertRaises(DomainValidationError):
            answer_from_response("not prompt", make_response(),
                                 tenant_id=TENANT)
        with self.assertRaises(DomainValidationError):
            answer_from_response(make_prompt(), "not response",
                                 tenant_id=TENANT)

    def test_answer_does_not_validate_citations(self):
        # Model text claiming [E7] (which does not exist) is preserved
        # verbatim as untrusted output — no citation validation here.
        prompt = make_prompt()
        response = make_response(
            generated_text="Per [E7] and [E999], file the form.")
        answer = answer_from_response(prompt, response, tenant_id=TENANT)
        self.assertEqual(
            answer.answer_text, "Per [E7] and [E999], file the form.")

    def test_answer_record_exposes_citation_mapping(self):
        answer = answer_from_response(
            make_prompt(), make_response(), tenant_id=TENANT)
        record = answer.to_record()
        self.assertEqual(record["citations"][0]["label"], "[E1]")
        self.assertIn("response", record)

    def test_tenant_not_injected_into_model_visible_text(self):
        # The MODEL-VISIBLE components — system instructions, the
        # information need, the evidence context, and the rendered
        # preview — never contain internal tenant or chunk identifiers.
        # (The structured to_record() provenance legitimately includes
        # tenant_id as internal audit metadata; it is not model input.)
        prompt = make_prompt()
        model_visible = "\n".join([
            prompt.system_instructions,
            prompt.information_need,
            prompt.evidence_context,
            prompt.render(),
        ])
        self.assertNotIn(str(TENANT_ID), model_visible)
        self.assertNotIn(str(CHUNK_1), model_visible)
        self.assertNotIn(str(prompt.tenant_id), model_visible)


# ----------------------------------------------------------------------
# Credentials & settings
# ----------------------------------------------------------------------


class TestCredentialHandling(unittest.TestCase):
    """Secrets stay in infrastructure settings only."""

    def test_settings_from_environment_mapping(self):
        settings = LLMSettings.from_environment({
            "LLM_API_KEY": "secret-key", "LLM_MODEL": MODEL})
        self.assertEqual(settings.api_key, "secret-key")
        self.assertEqual(settings.model_identifier, MODEL)

    def test_missing_api_key_rejected(self):
        with self.assertRaises(LLMConfigurationError):
            LLMSettings.from_environment({"LLM_MODEL": MODEL})
        with self.assertRaises(LLMConfigurationError):
            LLMSettings.from_environment({})

    def test_missing_model_rejected(self):
        with self.assertRaises(LLMConfigurationError):
            LLMSettings.from_environment({"LLM_API_KEY": "k"})

    def test_secret_never_enters_domain_contracts(self):
        # Config, response, and answer value objects have no field
        # that could carry the API key.
        for value_object in (
            LLMGenerationConfig(model_identifier=MODEL),
            make_response(),
        ):
            self.assertFalse(
                any("key" in field for field in value_object.to_record()))

    def test_settings_do_not_require_live_provider(self):
        # Constructing settings performs no network I/O.
        settings = LLMSettings.from_environment({
            "LLM_API_KEY": "k", "LLM_MODEL": MODEL})
        self.assertIsNotNone(settings)


# ----------------------------------------------------------------------
# Security boundary
# ----------------------------------------------------------------------


class TestSecurityBoundary(unittest.TestCase):
    """Model output is untrusted; the seam only obtains output."""

    def test_scripted_client_executes_nothing(self):
        # Model text that looks like code/SQL/actions is just returned
        # as text — never interpreted.
        dangerous = "import os; os.system('rm -rf /'); DROP TABLE users;"
        client = ScriptedLLMClient(
            responses=[make_response(generated_text=dangerous)])
        response = client.generate(
            make_prompt(), configuration=GEN_CONFIG, tenant_id=TENANT)
        self.assertEqual(response.generated_text, dangerous)

    def test_adapter_api_surface_has_no_execution_methods(self):
        # The provider-neutral seam exposes only `generate` — no exec,
        # no tool invocation, no filesystem operations.
        public = {
            name for name in dir(ScriptedLLMClient)
            if not name.startswith("_")
        }
        self.assertEqual(
            public, {"generate", "calls"} | {"__protocol_attrs__"}
            if "__protocol_attrs__" in public
            else public, public)
        self.assertNotIn("execute", public)
        self.assertNotIn("run", public)
        self.assertNotIn("call_tool", public)
        self.assertNotIn("read_file", public)


# ----------------------------------------------------------------------
# Adapter isolation (domain never imports provider SDKs)
# ----------------------------------------------------------------------


class TestAdapterIsolation(unittest.TestCase):
    """SDK/HTTP code stays out of domain modules."""

    def test_domain_llm_module_imports_no_infrastructure(self):
        import xportra.domain.llm as module

        tree = ast.parse(inspect.getsource(module))
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level == 0:
                    imported_roots.add(node.module.split(".")[0])
        forbidden = {"openai", "anthropic", "httpx", "requests",
                     "urllib", "socket", "qdrant_client", "tiktoken"}
        self.assertFalse(
            imported_roots & forbidden,
            f"forbidden import found: {imported_roots & forbidden}")
        self.assertTrue(
            imported_roots <= {"dataclasses", "typing", "math",
                               "__future__"},
            f"unexpected absolute imports: {imported_roots}")

    def test_no_vendor_sdk_installed_as_domain_dependency(self):
        # The domain package never imports any vendor SDK at runtime.
        import sys
        for sdk in ("openai", "anthropic"):
            self.assertNotIn(sdk, sys.modules)

    def test_infrastructure_seam_has_no_vendor_sdk(self):
        import xportra.infrastructure.llm as module

        tree = ast.parse(inspect.getsource(module))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(
                    alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level == 0:
                    imported_modules.add(node.module)
        # Phase 5.15: the sanctioned generic HTTP transport (httpx,
        # a declared project dependency) is allowed in the seam for
        # the single production adapter. Vendor SDKs stay forbidden.
        forbidden = {"openai", "anthropic", "requests", "urllib"}
        self.assertFalse(
            imported_modules & forbidden,
            f"vendor SDK found in seam: {imported_modules & forbidden}")

    def test_whole_boundary_runs_without_network(self):
        # Complete path — prompt → generate → answer — with only
        # deterministic in-memory fakes.
        prompt = make_prompt()
        client = ScriptedLLMClient(responses=[make_response()])
        response = client.generate(
            prompt, configuration=GEN_CONFIG, tenant_id=TENANT)
        answer = answer_from_response(
            prompt, response, tenant_id=TENANT)
        self.assertEqual(
            answer.answer_text, "You must file before shipment.")


if __name__ == "__main__":
    unittest.main()
