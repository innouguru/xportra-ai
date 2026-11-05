import hashlib
import json
import re
import unittest
from types import SimpleNamespace
from uuid import UUID

from xportra.domain.errors import LLMProviderError
from xportra.domain.ingestion import (
    RegulatoryRequirementExtractionError,
    RegulatoryRequirementExtractionService,
)
from xportra.domain.llm import LLMGenerationConfig, LLMResponse
from xportra.infrastructure.llm import ScriptedLLMClient

ARTIFACT_ID = UUID("11111111-2222-3333-4444-555555555555")
SOURCE_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
DOCUMENT_ID = UUID("99999999-8888-7777-6666-555555555555")
MODEL = "scripted-regulatory-model"
CONFIGURATION = LLMGenerationConfig(
    model_identifier=MODEL,
    temperature=0.0,
    max_output_tokens=4096,
)


def requirement(
    quote,
    *,
    title=None,
    requirement_type="obligation",
    category="obligation",
    page_reference=None,
    section_reference=None,
    product_category=None,
    effective_date=None,
    actor=None,
    condition=None,
    threshold=None,
):
    return {
        "title": title or quote,
        "description": quote,
        "requirement_type": requirement_type,
        "category": category,
        "supporting_quote": quote,
        "page_reference": page_reference,
        "section_reference": section_reference,
        "product_category": product_category,
        "effective_date": effective_date,
        "actor": actor,
        "condition": condition,
        "threshold": threshold,
    }


def response(requirements):
    return LLMResponse(
        generated_text=json.dumps({"requirements": requirements}),
        model_identifier=MODEL,
    )


def document(text, structure=None):
    return {
        "id": DOCUMENT_ID,
        "artifact_id": ARTIFACT_ID,
        "source_id": SOURCE_ID,
        "normalized_text": text,
        "normalized_content": {
            "structure": structure or [{
                "kind": "section",
                "order": 0,
                "heading": "Export obligations",
                "text": text,
            }]
        },
    }


def extractor(responses=None, failures=None):
    client = ScriptedLLMClient(
        responses=responses,
        failures=failures,
    )
    return RegulatoryRequirementExtractionService(
        llm_client=client,
        configuration=CONFIGURATION,
    ), client


class FakeRequirementRepository:
    def __init__(self):
        self.rows = {}

    def list_for_document(self, document_id):
        return list(self.rows.get(str(document_id), {}).values())

    def create(self, **values):
        row = {"id": values["id"], **values}
        self.rows.setdefault(
            str(values["normalized_document_id"]), {}
        )[str(row["id"])] = row
        return row


class RegulatoryRequirementExtractionTests(unittest.TestCase):
    def test_semantically_expresses_requirements_without_shall_or_must(self):
        quotes = [
            "Fresh consignments are accompanied by a phytosanitary certificate.",
            "Only packaging that prevents contamination is accepted for entry.",
            "Each consignment is inspected before release.",
        ]
        service, client = extractor([response([
            requirement(
                quotes[0],
                title="phytosanitary certificate",
                requirement_type="documentation",
                category="certification",
            ),
            requirement(
                quotes[1],
                title="packaging",
                requirement_type="obligation",
                category="packaging",
            ),
            requirement(
                quotes[2],
                title="inspected",
                requirement_type="inspection",
                category="inspection",
            ),
        ])])
        doc = document(
            "\n\n".join(quotes),
            structure=[{
                "kind": "section",
                "order": 3,
                "heading": "Import conditions",
                "text": "\n\n".join(quotes),
            }],
        )

        result = service.extract(doc)

        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(len(result.candidates), 3)
        self.assertEqual(len(client.calls), 1)
        self.assertFalse(any(
            re.search(r"\b(?:shall|must)\b", record["requirement_text"], re.I)
            for record in result.candidates
        ))
        self.assertEqual(
            result.candidates[1]["source_location"]["category"],
            "packaging",
        )

    def test_multiple_requirement_categories_preserve_source_context(self):
        quote = (
            "Exporters submit the inspection record when the shipment is "
            "delayed, and the authority examines the sealed package."
        )
        service, _ = extractor([response([
            requirement(
                quote,
                title="inspection record",
                requirement_type="documentation",
                category="reporting",
                section_reference="Article 8",
                page_reference=2,
                actor="Exporters",
                condition="when the shipment is delayed",
            )
        ])])
        doc = document(
            "Article 8\n" + quote,
            [{
                "kind": "section",
                "order": 8,
                "section_reference": "Article 8",
                "page_number": 2,
                "text": "Article 8\n" + quote,
            }],
        )

        result = service.extract(doc)
        candidate = result.candidates[0]

        self.assertEqual(candidate["actor"], "Exporters")
        self.assertEqual(
            candidate["condition_metadata"],
            {"condition": "when the shipment is delayed"},
        )
        self.assertEqual(candidate["source_location"]["page_reference"], 2)
        self.assertEqual(
            candidate["source_location"]["section_reference"], "Article 8"
        )
        self.assertIn(
            quote,
            candidate["source_location"]["supporting_quote"],
        )
        self.assertEqual(
            candidate["source_location"]["supporting_quote"], quote
        )
        self.assertEqual(
            candidate["source_location"]["quote_start_offset"],
            ("Article 8\n" + quote).index(quote),
        )
        self.assertEqual(
            candidate["source_location"]["quote_end_offset"],
            ("Article 8\n" + quote).index(quote) + len(quote),
        )
        self.assertEqual(
            candidate["source_location"]["quote_sha256"],
            hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            candidate["source_location"]["reference_status"],
            {"page": "verified", "section": "verified"},
        )

    def test_reference_status_distinguishes_omitted_and_unavailable_context(self):
        quote = "The exporter submits the inspection record."
        service, _ = extractor([response([requirement(quote)])])
        unavailable_service, _ = extractor([
            response([requirement(quote)])
        ])
        available_context = document(quote, [{
            "kind": "section",
            "order": 4,
            "section_reference": "Article 4",
            "page_number": 2,
            "text": quote,
        }])

        omitted = service.extract(available_context).candidates[0]
        unavailable = unavailable_service.extract(
            document(quote, [{"kind": "paragraph", "order": 0, "text": quote}])
        ).candidates[0]

        self.assertEqual(
            omitted["source_location"]["reference_status"],
            {
                "page": "not_returned_by_model",
                "section": "not_returned_by_model",
            },
        )
        self.assertEqual(
            unavailable["source_location"]["reference_status"],
            {
                "page": "unavailable_in_supplied_context",
                "section": "unavailable_in_supplied_context",
            },
        )

    def test_valid_empty_response_is_success_without_requirements(self):
        service, _ = extractor([response([])])

        result = service.extract(document("The authority publishes guidance."))

        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.rejected_candidate_count, 0)

    def test_malformed_json_is_failed_not_empty_success(self):
        service, _ = extractor([LLMResponse("{", MODEL)])

        result = service.extract(document("Importers present certificates."))

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.failed_chunks[0]["reason"], "malformed_json")

    def test_missing_fields_and_invalid_types_are_rejected(self):
        for invalid in (
            {"requirements": [{"title": "incomplete"}]},
            {"requirements": [requirement(
                "The exporter files Form A.",
                requirement_type=["documentation"],
            )]},
        ):
            with self.subTest(invalid=invalid):
                service, _ = extractor([
                    LLMResponse(json.dumps(invalid), MODEL)
                ])
                result = service.extract(
                    document("The exporter files Form A.")
                )
                self.assertEqual(result.outcome, "partial")
                self.assertEqual(result.candidates, ())
                self.assertEqual(result.rejected_candidate_count, 1)

    def test_unsupported_quote_is_rejected(self):
        service, _ = extractor([response([
            requirement("The exporter submits Form B.")
        ])])

        result = service.extract(document("The exporter files Form A."))

        self.assertEqual(result.outcome, "partial")
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.rejected_candidate_count, 1)

    def test_invented_page_reference_is_rejected(self):
        quote = "The shipment carries a phytosanitary certificate."
        service, _ = extractor([response([
            requirement(quote, page_reference=8)
        ])])
        doc = document(quote, [{
            "kind": "section",
            "page_number": 2,
            "text": quote,
        }])

        result = service.extract(doc)

        self.assertEqual(result.outcome, "partial")
        self.assertEqual(result.rejected_candidate_count, 1)

    def test_unsupported_optional_claims_are_rejected(self):
        quote = "The shipment carries a certificate."
        service, _ = extractor([response([
            requirement(
                quote,
                effective_date="1 January 2027",
            )
        ])])

        result = service.extract(document(quote))

        self.assertEqual(result.outcome, "partial")
        self.assertEqual(result.rejected_candidate_count, 1)

    def test_empty_model_response_is_failed(self):
        service, _ = extractor([LLMResponse("", MODEL)])

        result = service.extract(document("Fresh produce is inspected."))

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.failed_chunks[0]["reason"], "empty_response")

    def test_long_document_chunks_are_bounded_ordered_and_overlapping(self):
        text = "Regulatory provision. " * 800

        chunks = RegulatoryRequirementExtractionService._chunks(
            text, [{"kind": "section", "heading": "Controls", "text": text}]
        )

        self.assertGreater(len(chunks), 2)
        self.assertEqual([chunk.index for chunk in chunks],
                         list(range(1, len(chunks) + 1)))
        self.assertTrue(all(
            len(chunk.text) <= RegulatoryRequirementExtractionService.MAX_CHUNK_CHARS
            for chunk in chunks
        ))
        for first, second in zip(chunks, chunks[1:]):
            self.assertEqual(
                first.text[-RegulatoryRequirementExtractionService.CHUNK_OVERLAP_CHARS:],
                second.text[:RegulatoryRequirementExtractionService.CHUNK_OVERLAP_CHARS],
            )
            self.assertEqual(first.end - second.start,
                             RegulatoryRequirementExtractionService.CHUNK_OVERLAP_CHARS)

    def test_requirement_near_chunk_boundary_is_in_overlap(self):
        quote = "The shipment is accompanied by a certificate."
        text = ("source text " * 480) + quote + (" following text " * 250)
        chunks = RegulatoryRequirementExtractionService._chunks(
            text, [{"kind": "section", "text": text}]
        )
        containing = [
            chunk for chunk in chunks if quote in chunk.text
        ]

        self.assertGreaterEqual(len(containing), 1)
        self.assertTrue(all(
            text[chunk.start:chunk.end] == chunk.text
            for chunk in containing
        ))

    def test_duplicate_candidates_from_overlapping_chunks_are_deduplicated(self):
        quote = "The shipment is accompanied by a phytosanitary certificate."
        text = ("x " * 2850) + quote + (" y" * 1900)
        service, client = extractor([
            response([requirement(quote, title="phytosanitary certificate")]),
            response([requirement(quote, title="phytosanitary certificate")]),
        ])

        result = service.extract(document(text))

        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(result.candidates), 1)

    def test_chunk_failure_is_visible_as_partial(self):
        quote = "The exporter submits a certificate at the border."
        text = ("source text " * 650) + quote + (" further text " * 650)
        service, _ = extractor(
            responses=[response([requirement(
                quote,
                title="certificate",
                requirement_type="documentation",
                category="documentation",
            )]), response([]), response([])],
            failures=[LLMProviderError(
                "generate", TimeoutError("private timeout details")
            )],
        )

        result = service.extract(document(text))

        self.assertEqual(result.outcome, "partial")
        self.assertEqual(result.failed_chunks[0]["reason"], "timeout")
        self.assertEqual(len(result.candidates), 1)

    def test_rate_limit_and_api_errors_are_failed(self):
        failures = (
            (
                LLMProviderError(
                    "generate",
                    SimpleNamespace(response=SimpleNamespace(status_code=429)),
                ),
                "rate_limited",
            ),
            (LLMProviderError("generate", RuntimeError()), "llm_provider_error"),
        )
        for failure, expected_reason in failures:
            with self.subTest(reason=expected_reason):
                service, _ = extractor(
                    responses=[response([])],
                    failures=[failure],
                )
                result = service.extract(document("The shipment is inspected."))
                self.assertEqual(result.outcome, "failed")
                self.assertEqual(
                    result.failed_chunks[0]["reason"], expected_reason
                )

    def test_invalid_page_and_section_reference_types_are_rejected(self):
        quote = "The exporter presents a certificate."
        for invalid in (
            requirement(quote, page_reference=True),
            requirement(quote, section_reference=4),
        ):
            with self.subTest(invalid=invalid):
                service, _ = extractor([response([invalid])])
                result = service.extract(document(quote, [{
                    "kind": "section",
                    "page_number": 1,
                    "heading": "Certificates",
                    "text": quote,
                }]))
                self.assertEqual(result.outcome, "partial")
                self.assertEqual(result.rejected_candidate_count, 1)

    def test_prompt_marks_document_as_untrusted_and_uses_configured_model(self):
        quote = "The exporter submits the certificate."
        service, client = extractor([response([])])

        service.extract(document(quote))

        prompt = client.calls[0]["prompt"]
        self.assertIn("untrusted data", prompt.system_instructions)
        self.assertEqual(
            client.calls[0]["configuration"].model_identifier, MODEL
        )
        self.assertIn(quote, prompt.evidence_context)

    def test_missing_or_invalid_document_is_rejected(self):
        service, _ = extractor([response([])])
        with self.assertRaises(RegulatoryRequirementExtractionError):
            service.extract({})

        with self.assertRaises(RegulatoryRequirementExtractionError):
            service.extract(document(""))

    def test_repeated_processing_is_idempotent(self):
        quote = "The exporter submits the certificate."
        repository = FakeRequirementRepository()
        service, _ = extractor([response([requirement(
            quote, title="certificate"
        )])])
        service._repository = repository
        doc = document(quote)

        first = service.process(doc)
        second = service.process(doc)

        self.assertEqual(first, second)
        self.assertEqual(len(repository.list_for_document(DOCUMENT_ID)), 1)


if __name__ == "__main__":
    unittest.main()
