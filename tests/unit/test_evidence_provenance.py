"""Phase 5.9 — Evidence Provenance Chain Audit tests.

Audits the end-to-end provenance contract across the Phase 4/5
boundaries:

```text
EvidenceDocument / EvidenceChunk   (Phase 4.0–4.2 identity)
        ↓
EvidenceRetrievalResult            (Phase 5.1 — provenance carrier)
        ↓
HybridRetrievalCandidate           (Phase 5.4 — by reference)
        ↓
RankedEvidenceResult               (Phase 5.5 — by reference)
        ↓
SelectedEvidence / EvidenceContextSelection (Phase 5.7 — by reference)
```

Establishes: canonical identity (derived uuid5 document/chunk ids +
sha256 content fingerprint), field preservation at every transition,
object-identity preservation, validation ownership per layer, and a
complete retrieval → hybrid → ranking → context traceability test
through the real Phase 5.6/5.8 pipelines.

Fakes only — no live Qdrant, no embeddings, no LLM, no network.
No production code was modified for this audit.
"""

import unittest
from uuid import NAMESPACE_URL, UUID, uuid5

from xportra.domain.evidence_chunking import (
    EvidenceChunk,
    EvidenceChunkingService,
    stable_chunk_id,
)
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
)
from xportra.domain.evidence_context_pipeline import (
    EvidenceContextPipeline,
)
from xportra.domain.evidence_corpus import (
    EvidenceDocument,
    content_fingerprint,
    stable_document_id,
)
from xportra.domain.errors import DomainValidationError
from xportra.domain.evidence_hybrid import (
    ComposedHybridEvidenceRetriever,
    HybridRetrievalCandidate,
)
from xportra.domain.evidence_pipeline import EvidenceRetrievalPipeline
from xportra.domain.evidence_ranking import (
    DeterministicEvidenceRanker,
)
from xportra.domain.evidence_retrieval import (
    EvidenceRetrievalQuery,
    EvidenceRetrievalResult,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TENANT = TenantContext(TENANT_ID)

SOURCE_ID = "sonsa/cert-guide"
VERSION = "2024.1"
MODEL = "test-embed-model"
DIMS = 4

DOC_CONTENT = (
    "Exporters must file Form NXP before shipment.\n"
    "\n"
    "Inspection requirements apply to regulated products.\n"
)


def make_document(**overrides):
    kwargs = dict(
        title="Certification Guide",
        content=DOC_CONTENT,
        source_type="guidance",
        source_id=SOURCE_ID,
        document_version=VERSION,
    )
    kwargs.update(overrides)
    return EvidenceDocument.create(TENANT, **kwargs)


def make_chunks(document=None):
    return EvidenceChunkingService().chunk(
        document or make_document(), tenant_id=TENANT)


def chunk_to_retrieval_result(chunk_record, *, score=0.9):
    """The Phase 4.4 index payload → Phase 5.1 result (faithful shape)."""
    return EvidenceRetrievalResult(
        tenant_id=chunk_record["tenant_id"],
        chunk_id=chunk_record["chunk_id"],
        document_id=chunk_record["document_id"],
        chunk_index=chunk_record["chunk_index"],
        content=chunk_record["content"],
        content_fingerprint=chunk_record["content_fingerprint"],
        source_id=chunk_record["source_id"],
        source_type=chunk_record["source_type"],
        source_location=chunk_record["source_location"],
        document_version=chunk_record["document_version"],
        embedding_model=MODEL,
        embedding_dimensions=DIMS,
        score=score,
    )


def make_result(**overrides):
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"),
        document_id=stable_document_id(TENANT_ID, SOURCE_ID, VERSION),
        chunk_index=0,
        content="Exporters must file Form NXP.",
        content_fingerprint=content_fingerprint(
            "Exporters must file Form NXP."),
        source_id=SOURCE_ID,
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version=VERSION,
        embedding_model=MODEL,
        embedding_dimensions=DIMS,
        score=0.9,
    )
    base.update(overrides)
    return EvidenceRetrievalResult(**base)


class FakeSemanticRetriever:
    """Phase 5.1 EvidenceRetriever double over canned results."""

    def __init__(self, results):
        self.results = list(results)

    def retrieve(self, query, *, tenant_id, scope=None):
        return self.results[: query.top_k]


class FakeLexicalIndex:
    """Phase 5.4 EvidenceLexicalIndex double over canned results."""

    def __init__(self, results):
        self.results = list(results)

    def find_lexical(self, terms, *, tenant_id, top_k, scope=None):
        return self.results[:top_k]


# ----------------------------------------------------------------------
# Canonical provenance identity (derived, deterministic)
# ----------------------------------------------------------------------


class TestCanonicalIdentity(unittest.TestCase):
    """Document/chunk identity is derived, not assigned."""

    def test_document_id_is_deterministic_uuid5(self):
        doc_id = stable_document_id(TENANT_ID, SOURCE_ID, VERSION)
        expected = uuid5(
            NAMESPACE_URL,
            ":".join(["xportra:evidence-document", TENANT_ID.hex,
                      SOURCE_ID, VERSION]),
        )
        self.assertEqual(doc_id, expected)
        self.assertEqual(
            stable_document_id(TENANT_ID, SOURCE_ID, VERSION), doc_id)

    def test_document_id_binds_tenant_source_and_version(self):
        base = stable_document_id(TENANT_ID, SOURCE_ID, VERSION)
        self.assertNotEqual(
            base, stable_document_id(OTHER_TENANT_ID, SOURCE_ID, VERSION))
        self.assertNotEqual(
            base, stable_document_id(TENANT_ID, "other/source", VERSION))
        self.assertNotEqual(
            base, stable_document_id(TENANT_ID, SOURCE_ID, "2024.2"))

    def test_chunk_id_is_deterministic_uuid5(self):
        doc_id = stable_document_id(TENANT_ID, SOURCE_ID, VERSION)
        fp = content_fingerprint("some content")
        chunk_id = stable_chunk_id(TENANT_ID, doc_id, 0, fp)
        expected = uuid5(
            NAMESPACE_URL,
            ":".join(["xportra:evidence-chunk", TENANT_ID.hex,
                      doc_id.hex, "0", fp]),
        )
        self.assertEqual(chunk_id, expected)
        self.assertEqual(
            stable_chunk_id(TENANT_ID, doc_id, 0, fp), chunk_id)

    def test_chunk_id_binds_tenant_document_index_and_fingerprint(self):
        doc_id = stable_document_id(TENANT_ID, SOURCE_ID, VERSION)
        fp = content_fingerprint("some content")
        base = stable_chunk_id(TENANT_ID, doc_id, 0, fp)
        self.assertNotEqual(base, stable_chunk_id(TENANT_ID, doc_id, 1, fp))
        self.assertNotEqual(
            base, stable_chunk_id(TENANT_ID, doc_id, 0,
                                  content_fingerprint("other content")))

    def test_fingerprint_is_deterministic_sha256_of_content(self):
        fp = content_fingerprint("Exporters must file Form NXP.")
        self.assertEqual(
            fp, content_fingerprint("Exporters must file Form NXP."))
        self.assertNotEqual(fp, content_fingerprint("Exporters must file NXP."))

    def test_document_versions_never_collapse(self):
        # Distinct versions produce distinct document identities even
        # for identical content — version preservation by construction.
        v1 = make_document(document_version="2024.1")
        v2 = make_document(document_version="2024.2")
        self.assertNotEqual(v1.document_id, v2.document_id)


class TestChunkingIdentityInvariants(unittest.TestCase):
    """Owner of the content↔fingerprint invariant: Phase 4.2 chunking."""

    def test_chunking_produces_identity_coherent_chunks(self):
        document = make_document()
        for record in make_chunks(document):
            self.assertEqual(record["tenant_id"], TENANT_ID)
            self.assertEqual(record["document_id"], document.document_id)
            self.assertEqual(record["source_id"], SOURCE_ID)
            self.assertEqual(record["document_version"], VERSION)
            self.assertEqual(
                record["content_fingerprint"],
                content_fingerprint(record["content"]))
            self.assertEqual(
                record["chunk_id"],
                stable_chunk_id(
                    record["tenant_id"],
                    record["document_id"],
                    record["chunk_index"],
                    record["content_fingerprint"],
                ),
            )

    def test_chunk_rejects_content_fingerprint_mismatch(self):
        # New content + old fingerprint is unconstructible at the
        # owning boundary.
        with self.assertRaises(DomainValidationError):
            EvidenceChunk(
                tenant_id=TENANT_ID,
                chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"),
                document_id=stable_document_id(TENANT_ID, SOURCE_ID, VERSION),
                chunk_index=0,
                content="Rewritten content.",
                content_fingerprint=content_fingerprint("Original content."),
                source_id=SOURCE_ID,
                source_type="guidance",
                start_offset=0,
                end_offset=18,
            )

    def test_document_rejects_identity_mismatch(self):
        # A document_id not derived from tenant+source+version is
        # unconstructible — identity cannot drift.
        with self.assertRaises(DomainValidationError):
            EvidenceDocument(
                tenant_id=TENANT_ID,
                document_id=UUID("99999999-9999-9999-9999-999999999999"),
                title="Guide",
                content=DOC_CONTENT,
                source_type="guidance",
                source_id=SOURCE_ID,
                document_version=VERSION,
            )


# ----------------------------------------------------------------------
# Provenance preservation at every transition (object + field identity)
# ----------------------------------------------------------------------


class TestTransitionReferenceIdentity(unittest.TestCase):
    """Every Phase 5 transition wraps by reference — never copies."""

    def test_candidate_references_retrieval_result(self):
        evidence = make_result()
        candidate = HybridRetrievalCandidate(
            evidence=evidence,
            semantic_score=0.9,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"}),
        )
        self.assertIs(candidate.evidence, evidence)

    def test_ranked_result_references_candidate_evidence(self):
        evidence = make_result()
        candidate = HybridRetrievalCandidate(
            evidence=evidence,
            semantic_score=0.9,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"}),
        )
        ranked = DeterministicEvidenceRanker().rank(
            [candidate], top_k=1)[0]
        self.assertIs(ranked.evidence, evidence)

    def test_selected_evidence_references_ranked_result(self):
        ranked = DeterministicEvidenceRanker().rank(
            [HybridRetrievalCandidate(
                evidence=make_result(),
                semantic_score=0.9,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}))],
            top_k=1)
        selection = DeterministicContextSelector().select(
            ranked, tenant_id=TENANT, budget=EvidenceContextBudget(1000))
        self.assertIs(selection.selected_items[0].ranked, ranked[0])
        self.assertIs(selection.selected_items[0].ranked.evidence,
                      ranked[0].evidence)

    def test_one_evidence_object_survives_all_transitions(self):
        evidence = make_result()
        candidate = HybridRetrievalCandidate(
            evidence=evidence,
            semantic_score=0.9,
            lexical_score=2.0,
            retrieval_sources=frozenset({"semantic", "lexical"}),
        )
        ranked = DeterministicEvidenceRanker().rank([candidate], top_k=1)
        selection = DeterministicContextSelector().select(
            ranked, tenant_id=TENANT, budget=EvidenceContextBudget(1000))
        self.assertIs(
            selection.selected_items[0].ranked.evidence, evidence)


class TestFieldPreservationAcrossChain(unittest.TestCase):
    """All provenance fields survive candidate → ranked → selected."""

    def _run_chain(self, evidence):
        candidate = HybridRetrievalCandidate(
            evidence=evidence,
            semantic_score=0.9,
            lexical_score=3.0,
            retrieval_sources=frozenset({"semantic", "lexical"}),
        )
        ranked = DeterministicEvidenceRanker().rank([candidate], top_k=1)
        selection = DeterministicContextSelector().select(
            ranked, tenant_id=TENANT, budget=EvidenceContextBudget(1000))
        return ranked[0], selection.selected_items[0]

    def test_full_provenance_field_equality(self):
        evidence = make_result()
        ranked, selected = self._run_chain(evidence)
        final = selected.ranked.evidence
        for field in (
            "tenant_id", "chunk_id", "document_id", "chunk_index",
            "content", "content_fingerprint", "source_id", "source_type",
            "source_location", "document_version", "embedding_model",
            "embedding_dimensions",
        ):
            self.assertEqual(
                getattr(final, field), getattr(evidence, field),
                f"provenance field lost in transition: {field}")

    def test_scores_and_sources_preserved(self):
        evidence = make_result()
        ranked, selected = self._run_chain(evidence)
        self.assertEqual(ranked.semantic_score, 0.9)
        self.assertEqual(ranked.lexical_score, 3.0)
        self.assertEqual(
            ranked.retrieval_sources, frozenset({"semantic", "lexical"}))
        self.assertEqual(selected.ranked.semantic_score, 0.9)
        self.assertEqual(selected.ranked.lexical_score, 3.0)
        self.assertEqual(
            selected.ranked.retrieval_sources,
            frozenset({"semantic", "lexical"}))

    def test_rank_position_and_key_preserved(self):
        evidence = make_result()
        ranked, selected = self._run_chain(evidence)
        self.assertEqual(ranked.rank_position, 1)
        self.assertEqual(selected.rank_position, ranked.rank_position)
        self.assertEqual(selected.ranked.ranking_key, ranked.ranking_key)

    def test_content_fingerprints_equal_throughout(self):
        evidence = make_result()
        ranked, selected = self._run_chain(evidence)
        self.assertEqual(
            evidence.content_fingerprint,
            ranked.evidence.content_fingerprint)
        self.assertEqual(
            evidence.content_fingerprint,
            selected.ranked.evidence.content_fingerprint)


class TestImmutabilityOfChainObjects(unittest.TestCase):
    """Frozen values: provenance cannot be mutated in place."""

    def test_retrieval_result_is_frozen(self):
        evidence = make_result()
        with self.assertRaises(Exception):
            evidence.content = "tampered"

    def test_ranked_result_is_frozen(self):
        ranked = DeterministicEvidenceRanker().rank(
            [HybridRetrievalCandidate(
                evidence=make_result(),
                semantic_score=0.9,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}))],
            top_k=1)
        with self.assertRaises(Exception):
            ranked[0].rank_position = 99

    def test_context_selection_does_not_mutate_evidence(self):
        evidence = make_result()
        ranked = DeterministicEvidenceRanker().rank(
            [HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=0.9,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}))],
            top_k=1)
        snapshot = ranked[0].to_record()
        DeterministicContextSelector().select(
            ranked, tenant_id=TENANT, budget=EvidenceContextBudget(1000))
        self.assertEqual(ranked[0].to_record(), snapshot)


# ----------------------------------------------------------------------
# Validation ownership: each invariant fails closed at its owning layer
# ----------------------------------------------------------------------


class TestValidationOwnership(unittest.TestCase):
    """Corruption is detected by the layer that owns the invariant."""

    def _ranked_with(self, evidence):
        return DeterministicEvidenceRanker().rank(
            [HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=0.9,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}))],
            top_k=1)

    def test_cross_tenant_evidence_detected_by_context_selector(self):
        # Tenant invariant owner at the context boundary: Phase 5.7.
        foreign = make_result(tenant_id=OTHER_TENANT_ID)
        ranked = self._ranked_with(foreign)
        with self.assertRaises(DomainValidationError):
            DeterministicContextSelector().select(
                ranked, tenant_id=TENANT,
                budget=EvidenceContextBudget(1000))

    def test_duplicate_chunk_identity_detected_by_ranker(self):
        # Duplicate-identity invariant owner during ranking: Phase 5.5.
        first = make_result(chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"))
        second = make_result(
            chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"),
            content_fingerprint=content_fingerprint("other"),
            content="other")
        with self.assertRaises(DomainValidationError):
            DeterministicEvidenceRanker().rank(
                [HybridRetrievalCandidate(
                    evidence=first, semantic_score=0.9, lexical_score=None,
                    retrieval_sources=frozenset({"semantic"})),
                 HybridRetrievalCandidate(
                     evidence=second, semantic_score=0.8, lexical_score=None,
                     retrieval_sources=frozenset({"semantic"}))],
                top_k=2)

    def test_duplicate_chunk_identity_detected_by_selector_too(self):
        ranked = self._ranked_with(make_result()) * 2
        with self.assertRaises(DomainValidationError):
            DeterministicContextSelector().select(
                ranked, tenant_id=TENANT,
                budget=EvidenceContextBudget(1000))

    def test_source_score_inconsistency_detected_at_candidate_boundary(self):
        # Retrieval-source invariant owner: Phase 5.4 candidate model.
        evidence = make_result()
        with self.assertRaises(DomainValidationError):
            HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=None,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}),
            )
        with self.assertRaises(DomainValidationError):
            HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=0.9,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic", "lexical"}),
            )

    def test_inconsistent_candidate_detected_by_ranker_defense(self):
        # Even a monkeypatched/pseudo-candidate fails closed at Phase 5.5.
        with self.assertRaises(DomainValidationError):
            DeterministicEvidenceRanker().rank(
                ["not a candidate"], top_k=1)

    def test_emptied_content_detected_by_context_selector(self):
        # Content-integrity invariant owner at selection: Phase 5.7.
        ranked = self._ranked_with(make_result())
        object.__setattr__(ranked[0].evidence, "content", "")
        with self.assertRaises(DomainValidationError):
            DeterministicContextSelector().select(
                ranked, tenant_id=TENANT,
                budget=EvidenceContextBudget(1000))

    def test_rank_order_violation_detected_by_context_selector(self):
        ranked = self._ranked_with(make_result())
        doctored = [ranked[0], ranked[0]]
        with self.assertRaises(DomainValidationError):
            DeterministicContextSelector().select(
                doctored, tenant_id=TENANT,
                budget=EvidenceContextBudget(1000))

    def test_malformed_provider_payload_detected_by_from_record(self):
        # Payload-integrity invariant owner at retrieval: Phase 5.1.
        record = make_result().to_record()
        record["tenant_id"] = "not-a-uuid"
        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalResult.from_record(record)
        record = make_result().to_record()
        record["source_type"] = "blog-post"
        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalResult.from_record(record)
        record = make_result().to_record()
        record["embedding_dimensions"] = 0
        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalResult.from_record(record)


# ----------------------------------------------------------------------
# End-to-end traceability: Phase 4 identity → Phase 5.8 context
# ----------------------------------------------------------------------


class TestEndToEndTraceability(unittest.TestCase):
    """Source document → selected evidence, traced field by field."""

    def test_chunk_survives_full_chain_through_pipelines(self):
        document = make_document()
        chunks = make_chunks(document)
        self.assertGreaterEqual(len(chunks), 2)
        results = [
            chunk_to_retrieval_result(record, score=1.0 - index * 0.1)
            for index, record in enumerate(chunks)
        ]

        retrieval_pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=ComposedHybridEvidenceRetriever(
                semantic_retriever=FakeSemanticRetriever(results),
                lexical_index=FakeLexicalIndex([]),
            ),
            ranker=DeterministicEvidenceRanker(),
        )
        pipeline = EvidenceContextPipeline(
            retrieval_pipeline=retrieval_pipeline,
            context_selector=DeterministicContextSelector(),
        )
        selection = pipeline.select_context(
            "Form NXP filing",
            tenant_id=TENANT,
            mode="semantic",
            context_budget=EvidenceContextBudget(10_000),
            top_k=len(results),
        )

        self.assertEqual(
            len(selection.selected_items), len(results))
        for position, item in enumerate(selection.selected_items, start=1):
            ranked = item.ranked
            evidence = ranked.evidence
            original = chunks[position - 1]
            # Trace back to the exact original chunk + document + source.
            self.assertEqual(evidence.tenant_id, TENANT_ID)
            self.assertEqual(evidence.document_id, document.document_id)
            self.assertEqual(
                evidence.document_version, document.document_version)
            self.assertEqual(evidence.chunk_id, original["chunk_id"])
            self.assertEqual(evidence.chunk_index, original["chunk_index"])
            self.assertEqual(evidence.source_id, document.source_id)
            self.assertEqual(evidence.source_type, document.source_type)
            self.assertEqual(
                evidence.content, original["content"])
            self.assertEqual(
                evidence.content_fingerprint,
                original["content_fingerprint"])
            self.assertEqual(
                evidence.content_fingerprint,
                content_fingerprint(evidence.content))
            # Ranking identity is explicit and consistent.
            self.assertEqual(ranked.rank_position, position)
            self.assertEqual(item.rank_position, position)
            self.assertIsNotNone(ranked.ranking_key)

    def test_versions_stay_distinct_through_the_chain(self):
        # Identical content under two versions is two distinct
        # provenance chains — never collapsed.
        v1_chunk = make_chunks(make_document(document_version="2024.1"))[0]
        v2_chunk = make_chunks(make_document(document_version="2024.2"))[0]
        self.assertNotEqual(v1_chunk["document_id"], v2_chunk["document_id"])
        self.assertEqual(
            v1_chunk["content_fingerprint"], v2_chunk["content_fingerprint"])

        results = [
            chunk_to_retrieval_result(v1_chunk, score=0.9),
            chunk_to_retrieval_result(v2_chunk, score=0.8),
        ]
        retrieval_pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=ComposedHybridEvidenceRetriever(
                semantic_retriever=FakeSemanticRetriever(results),
                lexical_index=FakeLexicalIndex([]),
            ),
            ranker=DeterministicEvidenceRanker(),
        )
        selection = EvidenceContextPipeline(
            retrieval_pipeline=retrieval_pipeline,
            context_selector=DeterministicContextSelector(),
        ).select_context(
            "Form NXP filing",
            tenant_id=TENANT,
            mode="semantic",
            context_budget=EvidenceContextBudget(10_000),
            top_k=2,
        )
        seen_documents = {
            item.ranked.evidence.document_id
            for item in selection.selected_items
        }
        self.assertEqual(len(seen_documents), 2)

    def test_selected_evidence_traces_to_authoritative_source_fields(self):
        # The final context carries everything a user-facing citation
        # boundary would need — source triple + document + version —
        # without claiming those fields ARE a legal citation.
        chunks = make_chunks()
        result = chunk_to_retrieval_result(chunks[0])
        ranked = DeterministicEvidenceRanker().rank(
            [HybridRetrievalCandidate(
                evidence=result,
                semantic_score=0.9,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}))],
            top_k=1)
        selection = DeterministicContextSelector().select(
            ranked, tenant_id=TENANT, budget=EvidenceContextBudget(10_000))
        final = selection.selected_items[0].ranked.evidence
        record = final.to_record()
        self.assertEqual(record["source_id"], SOURCE_ID)
        self.assertEqual(record["source_type"], "guidance")
        # source_location is optional in the Phase 4.0 contract — its
        # ABSENCE must be preserved as faithfully as its presence.
        self.assertIsNone(record["source_location"])
        self.assertEqual(record["document_version"], VERSION)
        self.assertIn("content_fingerprint", record)


if __name__ == "__main__":
    unittest.main()
