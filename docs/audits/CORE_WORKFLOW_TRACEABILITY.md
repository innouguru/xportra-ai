# Xportra AI — Core Workflow Traceability Matrix

**Audit Date:** 2026-10-31
**Type:** Traceability matrix connecting product requirements to implementation

---

## 1. Authentication and Organization Management

| Requirement | Frontend | API | Service | Database | Tests | Verification |
|---|---|---|---|---|---|---|
| User registration | RegisterPage.tsx | POST /organizations/register | OrganizationRegistrationService | xportra.users, xportra.tenants, xportra.user_tenant_memberships | test_organization_registration_api.py | Unit tested |
---

## 2. Shipment Management

| Requirement | Frontend | API | Service | Database | Tests | Verification |
|---|---|---|---|---|---|---|
| Create shipment | NewShipmentPage.tsx | POST /compliance/workflows/start | ComplianceWorkflowService | xportra.shipments, xportra.compliance_workflows | test_shipment_intake.py | Unit tested |
| Shipment listing | ShipmentsPage.tsx | GET /compliance/shipments | ShipmentRepository | xportra.shipments | test_shipment_listing.py | Unit tested |
| Shipment detail | ShipmentInfoPage.tsx | GET /compliance/shipments/{id} | ShipmentRepository | xportra.shipments | test_shipment_listing.py | Unit tested |
| Auto-save (session) | WorkflowContext.tsx | N/A (client-side) | N/A | sessionStorage | N/A | Not automated |
| Resume incomplete | ShipmentsPage.tsx | GET /compliance/shipments | ShipmentRepository | xportra.shipments | test_shipment_listing.py | Unit tested |
| Shipment profile (product, origin, destination) | NewShipmentPage.tsx | POST /compliance/workflows/start | ComplianceWorkflowService | xportra.shipments | test_shipment_intake.py | Unit tested |
| Adaptive questions | NewShipmentPage.tsx | N/A (client-side) | N/A | N/A | N/A | Manual only |
| Status transitions | ShipmentWorkspacePage.tsx | POST /compliance/workflows/{id}/... | ComplianceWorkflowService | xportra.compliance_workflows | test_compliance_workflow.py | Unit tested |
| Finalization | ShipmentWorkspacePage.tsx | POST /compliance/workflows/{id}/finalize | ComplianceWorkflowService | xportra.compliance_workflows (is_closed) | test_workflow_closure.py | Unit tested |
| Immutability after completion | ShipmentWorkspacePage.tsx | All mutation endpoints | ComplianceWorkflowService | xportra.compliance_workflows | test_workflow_closure.py | Unit tested |
| User login (magic link) | SignInPage.tsx | Supabase auth | SupabaseTokenVerifier | Supabase auth.users | test_auth.py | Unit tested |
| User login (password) | SignInPage.tsx | Supabase auth | SupabaseTokenVerifier | Supabase auth.users | test_auth.py | Unit tested |
| Session restoration | AuthContext.tsx | GET /identity/me | TenantMembershipResolver | xportra.users | test_auth.py | Unit tested |
| Organization creation | OrganizationRegistrationPage.tsx | POST /organizations/register | OrganizationRegistrationService | xportra.tenants, xportra.exporters | test_organization_registration_api.py | Unit tested |
| Tenant isolation | All pages | All endpoints | TenantContext | All tables (tenant_id) | test_shipment_intake.py, test_shipment_listing.py | Unit tested |
| Role enforcement | All pages | require_permission() | AuthorizationService | xportra.user_tenant_memberships | test_auth.py, test_regulatory_catalog.py | Unit tested |
| Staff grants | RegulatoryAdminPage.tsx | Global staff endpoints | GlobalStaffGrantService | xportra.global_staff_grants | test_global_staff.py | Unit tested |
---

## 3. Regulatory Knowledge and Ingestion

| Requirement | Frontend | API | Service | Database | Tests | Verification |
|---|---|---|---|---|---|---|
| Source registration | RegulationAdminPage.tsx | POST /regulatory/sources | RegulatorySourceIntakeService | xportra.regulatory_sources, xportra.regulatory_ingestion_jobs | test_regulatory_source_intake.py | Unit tested |
| Authority management | RegulationAdminPage.tsx | GET/POST /regulatory/authorities | AuthorityRepository | xportra.regulatory_authorities | test_regulatory_authorities_endpoint.py | Unit tested |
| Document upload | RegulationAdminPage.tsx | POST /regulatory/sources/{id}/artifacts | RegulatoryArtifactStorageService | xportra.regulatory_artifacts | test_regulatory_artifact_storage.py | Unit tested |
| Candidate extraction | Worker (background) | N/A (worker) | RegulatoryCandidateExtractionService | xportra.regulatory_requirements | test_regulatory_candidate_extraction.py | Unit tested |
| Manual candidate entry | RegulationAdminPage.tsx | N/A (manual) | RegulatoryCandidateExtractionService | xportra.regulatory_requirements | test_regulatory_publication_eligibility.py | Unit tested |
| Retry failed jobs | RegulationAdminPage.tsx | POST /regulatory/ingestion-jobs/{id}/retry | RegulatoryIngestionJobRepository | xportra.regulatory_ingestion_jobs | test_regulatory_job_retry_endpoint.py | Unit tested |
| Stage A review | RegulationAdminPage.tsx | POST /regulatory/candidates/{id}/stage-a | RegulatoryStageAReviewService | xportra.regulatory_stage_a_reviews | test_regulatory_stage_a_review.py | Unit tested |
| Stage B review | RegulationAdminPage.tsx | POST /regulatory/candidates/{id}/stage-b | RegulatoryStageBReviewService | xportra.regulatory_stage_b_reviews | test_regulatory_stage_b_review.py | Unit tested |
| Wording correction | RegulationAdminPage.tsx | POST /regulatory/candidates/{id}/stage-a (corrected_requirement_text) | RegulatoryStageAReviewService | xportra.regulatory_requirement_wording_corrections | test_regulatory_stage_a_review.py | Unit tested |
| Source withdrawal | RegulationAdminPage.tsx | POST /regulatory/sources/{id}/withdrawal | RegulatorySourceIntakeService | xportra.regulatory_sources, xportra.regulatory_review_flags | test_regulatory_source_intake.py | Unit tested |
| Publication | RegulationAdminPage.tsx | N/A (eligibility check) | RegulatoryPublicationEligibilityService | xportra.regulatory_requirements (status=published) | test_regulatory_publication_eligibility.py | Unit tested |
| End-to-end workflow | N/A (integration test) | All above | All above | All above | test_regulatory_full_workflow_postgresql.py | Integration tested (3/3 pass) |

---

## 4. Regulatory Requirement Determination

| Requirement | Frontend | API | Service | Database | Tests | Verification |
|---|---|---|---|---|---|---|
| Catalog retrieval | ShipmentInfoPage.tsx | GET /catalog/requirements | RegulatoryCatalogService | xportra.regulatory_requirements, xportra.regulatory_requirement_applicability | test_regulatory_catalog.py (8 tests) | Unit tested |
| Scope filtering (product, origin, destination) | ShipmentInfoPage.tsx | GET /catalog/requirements?product=&origin_country=&destination_country= | RegulatoryCatalogService | xportra.regulatory_requirement_applicability (context_fingerprint) | test_regulatory_catalog.py | Unit tested |
| Fail-closed on missing scope | ShipmentInfoPage.tsx | N/A (frontend) | N/A (frontend) | N/A | None (no frontend tests) | Not tested |
| Exclusion of unpublished | N/A (backend) | GET /catalog/requirements | RegulatoryCatalogService | xportra.regulatory_requirements (status=published) | test_regulatory_catalog.py | Unit tested |
| Exclusion of withdrawn/superseded | N/A (backend) | GET /catalog/requirements | RegulatoryCatalogService | xportra.regulatory_sources (status=active) | test_regulatory_catalog.py | Unit tested |
| Exclusion of pending flags | N/A (backend) | GET /catalog/requirements | RegulatoryCatalogService | xportra.regulatory_review_flags | test_regulatory_catalog.py | Unit tested |
| Unknown applicability handling | ShipmentInfoPage.tsx | GET /catalog/requirements | RegulatoryCatalogService | xportra.regulatory_requirement_applicability | test_regulatory_catalog.py | Unit tested |
---

## 5. Compliance Workflow

| Requirement | Frontend | API | Service | Database | Tests | Verification |
|---|---|---|---|---|---|---|
| View applicable requirements | RequirementsPage.tsx | GET /compliance/... | ComplianceWorkflowService | xportra.compliance_workflows | test_compliance_workflow.py | Unit tested |
| Record applicability outcome | RequirementsPage.tsx | POST /compliance/... | ComplianceWorkflowService | xportra.compliance_workflows | test_compliance_workflow.py | Unit tested |
| Evidence submission | EvidenceWorkspacePage.tsx | POST /compliance-evidence | ComplianceEvidenceService | xportra.compliance_evidence | test_compliance_workflow.py | Unit tested |
| Evidence-requirement association | EvidenceWorkspacePage.tsx | POST /compliance-evidence/{id}/requirements | ComplianceEvidenceService | xportra.evidence_requirement_links | test_compliance_workflow.py | Unit tested |
| Assessment trigger | AssessmentPage.tsx | POST /compliance/.../analyze | ComplianceAnalysisService | xportra.compliance_analysis_results | test_compliance_analysis_report.py | Unit tested |
| Progress tracking | WorkspaceOverview.tsx | GET /compliance/shipments | ComplianceWorkflowService | xportra.compliance_workflows | test_compliance_case_readiness.py | Unit tested |
| Finalization | WorkspacePage.tsx | POST /compliance/workflows/{id}/finalize | ComplianceWorkflowService | xportra.compliance_workflows (is_closed) | test_workflow_closure.py | Unit tested |
| Historical report | HistoricalReportPage.tsx | GET /compliance/shipments/{id} | ComplianceWorkflowService | xportra.compliance_workflows, xportra.compliance_analysis_results | test_workflow_history.py | Unit tested |

---

## 6. Evidence Management and Document Intelligence

| Requirement | Frontend | API | Service | Database | Tests | Verification |
|---|---|---|---|---|---|---|
| Evidence upload | EvidenceUploadPage.tsx | POST /evidence-uploads | EvidenceUploadApplicationService | xportra.evidence_documents, xportra.evidence_uploads | test_phase_10_4_evidence_upload.py | Unit tested |
| File validation | EvidenceUploadPage.tsx | POST /evidence-uploads | EvidenceUploadApplicationService | N/A | test_phase_10_4_evidence_upload.py | Unit tested |
| Private storage | N/A (backend) | N/A (backend) | EvidenceObjectStore | File system / Supabase Storage | test_phase_10_4_evidence_upload.py | Unit tested |
| Document extraction | N/A (backend) | N/A (background) | EvidenceDocumentIngestionService | xportra.evidence_documents | test_evidence_document_ingestion.py | Unit tested |
| Evidence-to-requirement matching | EvidenceWorkspacePage.tsx | POST /compliance-evidence/{id}/requirements | ComplianceEvidenceService | xportra.evidence_requirement_links | test_compliance_workflow.py | Unit tested |
| Evidence sufficiency | N/A (backend) | N/A (analysis) | EvidenceSufficiencyService | xportra.compliance_analysis_results | test_evidence_sufficiency.py | Unit tested |
| Evidence history | EvidenceWorkspacePage.tsx | GET /compliance-evidence | ComplianceEvidenceService | xportra.compliance_evidence | test_compliance_workflow.py | Unit tested |
| Re-analysis | WorkspacePage.tsx | POST /compliance/.../analyze | ComplianceAnalysisService | xportra.compliance_analysis_results | test_compliance_analysis_report.py | Unit tested |

---

## 7. AI, Retrieval and RAG

| Requirement | Frontend | API | Service | Database | Tests | Verification |
|---|---|---|---|---|---|---|
| Document chunking | N/A (backend) | N/A (background) | EvidenceChunkingService | xportra.evidence_chunks | test_evidence_chunking.py | Unit tested |
| Embedding generation | N/A (backend) | N/A (background) | EmbeddingService | xportra.evidence_embeddings | test_evidence_indexing.py | Unit tested (mocked) |
| Vector search (Qdrant) | N/A (backend) | N/A (background) | QdrantRetrievalService | Qdrant (external) | test_evidence_hybrid_retrieval.py | Unit tested (mocked) |
| Hybrid retrieval | N/A (backend) | POST /rag/query | RAGApplicationService | N/A | test_rag_api_boundary.py | Unit tested (mocked) |
| RAG answer generation | AskXportraButton | POST /rag/query | RAGApplicationService | N/A | test_rag_composition.py | Unit tested (mocked) |
| Citation validation | N/A (backend) | POST /rag/query | AnswerValidationService | N/A | test_answer_validation.py | Unit tested |
| Compliance reasoning | N/A (backend) | N/A (analysis) | ComplianceReasoningService | xportra.compliance_analysis_results | test_compliance_reasoning.py | Unit tested |
---

## 8. Finalization and Reporting

| Requirement | Frontend | API | Service | Database | Tests | Verification |
|---|---|---|---|---|---|---|
| Finalization prerequisites | WorkspacePage.tsx | POST /compliance/workflows/{id}/finalize | ComplianceWorkflowService | xportra.compliance_workflows | test_workflow_closure.py | Unit tested |
| Immutability after completion | All pages | All mutation endpoints | ComplianceWorkflowService | xportra.compliance_workflows (is_closed) | test_workflow_closure.py | Unit tested |
| Historical report access | HistoricalReportPage.tsx | GET /compliance/shipments/{id} | ComplianceWorkflowService | xportra.compliance_workflows, xportra.compliance_analysis_results | test_workflow_history.py | Unit tested |
| Report traceability | HistoricalReportPage.tsx | GET /compliance/shipments/{id} | ComplianceWorkflowService | xportra.compliance_analysis_results | test_workflow_history.py | Unit tested |
| PDF generation | N/A | N/A | N/A | N/A | N/A | Not implemented |

---

## 9. External Dependencies

| Dependency | Purpose | Status | Verification |
|---|---|---|---|
| Supabase (Auth) | User authentication, JWT verification | Configured | Unit tested (mocked) |
| Supabase (Database) | PostgreSQL hosting | Configured | Integration tested (isolated) |
| Supabase (Storage) | Evidence file storage | Configured | Unit tested (mocked) |
| Qdrant | Vector search for RAG | Configured | Unit tested (mocked) |
| OpenAI | Embeddings, LLM reasoning | Configured | Unit tested (mocked) |
| Anthropic | LLM reasoning (alternative) | Configured | Unit tested (mocked) |
| Vite | Frontend build | Configured | Build verified (earlier) |

---

## 10. Verification Status Legend

- **Implemented**: Relevant code exists in the repository.
- **Connected**: Frontend, API, services, and persistence are wired together.
- **Tested**: Automated tests demonstrate the expected behavior.
- **Operationally Verified**: The functionality has been demonstrated in the intended running environment with real data.

**Important:** Mocked tests do NOT constitute operational verification. Live external service connections have not been verified.