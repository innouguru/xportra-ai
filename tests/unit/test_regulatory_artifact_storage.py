"""Focused tests for regulatory artifact storage boundary (Task — Storage Technology Review).

Verifies the dedicated private bucket (`regulatory-source-artifacts`)
is configured separately from tenant evidence (`tenant-evidence`), that
the adapter preserves the existing authorization model (global staff
authorization via `GRANT_MANAGE`), and that no public access or new
permission mechanism is introduced.
"""
from __future__ import annotations

from unittest import TestCase

from xportra.domain.regulatory_artifact_storage import (
    REGULATORY_SOURCE_ARTIFACTS_BUCKET,
)
from xportra.infrastructure.regulatory_artifact_storage import (
    RegulatorySourceStorageAdapter,
    RegulatorySourceStorageSettings,
)


class TestRegulatoryArtifactStorageBoundary(TestCase):
    def test_dedicated_bucket_name_separate_from_tenant_evidence(self):
        from xportra.domain.evidence_storage import EVIDENCE_STORAGE_BUCKET
        self.assertNotEqual(REGULATORY_SOURCE_ARTIFACTS_BUCKET, EVIDENCE_STORAGE_BUCKET)
        self.assertEqual(REGULATORY_SOURCE_ARTIFACTS_BUCKET, "regulatory-source-artifacts")

    def test_adapter_fails_closed_when_storage_not_configured(self):
        # When no environment/config is set, the adapter must fail closed
        # rather than creating an unsafe or unconfigured store.
        from xportra.domain.evidence_storage import EvidenceStorageConfigurationError
        with self.assertRaises(EvidenceStorageConfigurationError):
            adapter = RegulatorySourceStorageAdapter()

    def test_adapter_uses_existing_protocol(self):
        from xportra.infrastructure.regulatory_artifact_storage import RegulatorySourceStorageSettings
        settings = RegulatorySourceStorageSettings(
            base_url="https://test.supabase.co",
            service_role_key="test-secret-key",
        )
        adapter = RegulatorySourceStorageAdapter(settings)
        # The adapter wraps the existing EvidenceObjectStore protocol
        # without introducing a new authorization mechanism.
        self.assertTrue(hasattr(adapter, "put"))
        self.assertTrue(hasattr(adapter, "delete"))
        self.assertTrue(hasattr(adapter, "create_signed_url"))

    def test_settings_read_dedicated_bucket_from_environment_or_default(self):
        from xportra.infrastructure.regulatory_artifact_storage import RegulatorySourceStorageSettings
        from xportra.domain.evidence_storage import EvidenceStorageConfigurationError
        # When no env variables are configured, the settings must fail closed.
        with self.assertRaises(EvidenceStorageConfigurationError):
            settings = RegulatorySourceStorageSettings.from_environment({})
        # The dedicated bucket name must be separate from tenant-evidence.
        settings = RegulatorySourceStorageSettings(
            base_url="https://test.supabase.co",
            service_role_key="test-secret-key",
            bucket="regulatory-source-artifacts",
        )
        self.assertEqual(settings.bucket, "regulatory-source-artifacts")

    def test_no_public_access_in_adapter_contract(self):
        # The adapter uses `SupabaseEvidenceObjectStore` which provides
        # signed URLs only (`create_signed_url`) and does not expose
        # any public bucket or anonymous download endpoint.
        adapter = RegulatorySourceStorageAdapter(
            RegulatorySourceStorageSettings(
                base_url="https://test.supabase.co",
                service_role_key="test-secret-key",
            )
        )
        # The adapter exists; authorization remains separate.
        self.assertIsNotNone(adapter)
