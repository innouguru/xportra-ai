# Xportra AI — Remaining Blockers

**Audit Date:** 2026-10-31
**Type:** Prioritized blocker list from whole-project audit

---

## P0 — Critical Blockers (Prevent Primary Product Workflow)

### P0-1: No Production Deployment or Live Verification

- **Severity:** P0
- **Affected Functionality:** All workflows
- **Files/Services:** Entire application
- **Evidence:** No deployment has been attempted; no production environment exists; no live verification of any workflow end-to-end.
- **Business Impact:** The system cannot be used by real exporters. No real-world validation of any functionality.
- **Recommended Correction:** Deploy to staging environment with full configuration verification.
- **Dependencies:** All other blockers must be resolved first.
- **Blocks Core Workflow:** Yes

### P0-2: External AI Services Unverified

- **Severity:** P0
- **Affected Functionality:** Evidence evaluation, compliance reasoning, RAG answers, document processing
- **Files/Services:** xportra/infrastructure/, xportra/domain/evidence_retrieval.py, xportra/application/rag_application.py
- **Evidence:** Code exists for Qdrant, OpenAI, Anthropic integration but no live connection has been verified. No API keys configured in test environment.
- **Business Impact:** Evidence cannot be evaluated against regulatory requirements without working AI services. Compliance assessment is non-functional without verified AI.
- **Recommended Correction:** Configure staging environment with real AI provider credentials and verify end-to-end.
- **Dependencies:** Staging deployment (P0-1).
- **Blocks Core Workflow:** Yes

---

## P1 — Major Blockers (Core Capability Missing, Disconnected, or Unreliable)

### P1-1: Regulatory Catalog Frontend Not Exercised End-to-End

- **Severity:** P1
- **Affected Functionality:** Regulatory requirement determination for shipments
- **Files/Services:** frontend/src/features/shipment/ShipmentInfoPage.tsx, xportra/api/catalog.py, xportra/application/regulatory_catalog_service.py
- **Evidence:** Frontend integration recently added but not tested with real shipment data. No automated frontend tests for catalog display.
- **Business Impact:** Exporters cannot verify that correct requirements are retrieved for their shipments.
- **Recommended Correction:** Add frontend tests for catalog integration; verify with real shipment data.
- **Dependencies:** P0-1 (staging deployment).
- **Blocks Core Workflow:** Yes

### P1-2: Compliance Assessment Integration Unverified

- **Severity:** P1
- **Affected Functionality:** Compliance assessment for shipments
- **Files/Services:** xportra/application/assessments.py, frontend/src/features/assessment/, frontend/src/features/requirements/RequirementsPage.tsx
- **Evidence:** Assessment engine exists but its trigger from the frontend and integration with catalog requirements is not verified.
- **Business Impact:** Exporters cannot obtain compliance assessments for their shipments.
- **Recommended Correction:** Verify assessment trigger flow end-to-end; connect catalog requirements to assessment.
- **Dependencies:** P1-1 (catalog integration).
- **Blocks Core Workflow:** Yes

### P1-3: Evidence Evaluation Against Requirements Unverified

- **Severity:** P1
- **Affected Functionality:** Evidence evaluation, missing evidence identification
- **Files/Services:** xportra/application/evidence.py, xportra/domain/evidence_sufficiency.py, frontend/src/features/evidence/
- **Evidence:** Evidence upload works but evaluation against regulatory requirements depends on AI services (P0-2) and assessment integration (P1-2).
- **Business Impact:** Exporters cannot determine if their evidence is adequate.
- **Recommended Correction:** Verify evidence evaluation flow after AI services are operational.
- **Dependencies:** P0-2, P1-2.
- **Blocks Core Workflow:** Yes

### P1-4: Production Migrations Not Applied

- **Severity:** P1
- **Affected Functionality:** Database schema (publication, retry, wording correction, artifact-optional jobs)
- **Files/Services:** migrations/030_*.sql through migrations/033_*.sql
- **Evidence:** Migrations 030-033 exist but have not been applied to any production database. Note in CURRENT_STATE.md: "migrations 030-033 must be applied in order when deployment is authorized."
- **Business Impact:** Regulatory publication, retry, and wording correction features would fail in production.
- **Recommended Correction:** Apply migrations in order during deployment.
- **Dependencies:** P0-1 (deployment authorization).
- **Blocks Core Workflow:** Yes (for regulatory features)

### P1-5: Worker Authorization Not Configured

- **Severity:** P1
- **Affected Functionality:** Background regulatory ingestion processing
- **Files/Services:** xportra/application/regulatory_ingestion_worker.py, xportra/application/global_staff.py
- **Evidence:** Worker requires REGULATORY_WORKER_ACTOR_USER_ID with active GRANT_MANAGE grant. Not configured in test environment; worker skips execution fail-closed.
- **Business Impact:** Regulatory sources cannot be processed automatically without worker authorization.
- **Recommended Correction:** Configure worker actor user ID with GRANT_MANAGE grant in production.
- **Dependencies:** P0-1, P1-4.
- **Blocks Core Workflow:** Yes (for regulatory ingestion)

### P1-6: Historical Report Reproducibility Unverified

- **Severity:** P1
- **Affected Functionality:** Historical compliance reports
- **Files/Services:** frontend/src/features/shipment/HistoricalReportPage.tsx, xportra/application/result_store.py
- **Evidence:** Historical report page exists but reproducibility with real data not verified.
- **Business Impact:** Exporters cannot rely on historical compliance records.
- **Recommended Correction:** Verify historical report generation and retrieval with real completed shipments.
- **Dependencies:** P1-2 (assessment integration).
- **Blocks Core Workflow:** Yes
---

## P2 — Important (Product Can Function but Significant Weaknesses)

### P2-1: No PDF Report Generation

- **Severity:** P2
- **Affected Functionality:** Report export and sharing
- **Files/Services:** No PDF generation service found in codebase
- **Evidence:** Historical reports are web-based only. No PDF export functionality.
- **Business Impact:** Exporters cannot share or archive compliance reports in standard format.
- **Recommended Correction:** Implement PDF generation for compliance reports.
- **Dependencies:** P1-6.
- **Blocks Core Workflow:** No

### P2-2: Shipment Editing Limited

- **Severity:** P2
- **Affected Functionality:** Shipment data correction
- **Files/Services:** frontend/src/features/shipment/NewShipmentPage.tsx, xportra/api/shipments.py (no edit endpoint found)
- **Evidence:** No explicit "edit shipment" endpoint or UI found. Shipments can be created but not modified after creation.
- **Business Impact:** Exporters cannot correct shipment information after creation.
- **Recommended Correction:** Add shipment edit capability with appropriate validation.
- **Dependencies:** None.
- **Blocks Core Workflow:** No

### P2-3: No Penetration Testing

- **Severity:** P2
- **Affected Functionality:** Security
- **Files/Services:** Entire application
- **Evidence:** No security testing has been performed. Authorization logic exists but has not been tested against real attack scenarios.
- **Business Impact:** Potential security vulnerabilities may exist undetected.
- **Recommended Correction:** Conduct security audit and penetration testing.
- **Dependencies:** P0-1 (deployment).
- **Blocks Core Workflow:** No

### P2-4: No Load Testing

- **Severity:** P2
- **Affected Functionality:** Performance and scalability
- **Files/Services:** Entire application
- **Evidence:** No load testing has been performed.
- **Business Impact:** Performance under concurrent users is unknown.
- **Recommended Correction:** Conduct load testing with realistic user scenarios.
- **Dependencies:** P0-1 (deployment).
- **Blocks Core Workflow:** No

### P2-5: Frontend Test Environment Issues

- **Severity:** P2
- **Affected Functionality:** Frontend test reliability
- **Files/Services:** frontend/ test configuration
- **Evidence:** 426/622 frontend tests fail due to jsdom/environment configuration issues. Earlier report documented 582/583 passing with proper configuration.
- **Business Impact:** Frontend test coverage cannot be reliably verified.
- **Recommended Correction:** Fix test environment configuration (jsdom, browser APIs).
- **Dependencies:** None.
- **Blocks Core Workflow:** No
### P2-6: No Monitoring or Alerting

- **Severity:** P2
- **Affected Functionality:** Operational visibility
- **Files/Services:** xportra/api/health.py
- **Evidence:** Health check endpoint exists but no monitoring, logging aggregation, or alerting configured.
- **Business Impact:** Production issues cannot be detected or diagnosed promptly.
- **Recommended Correction:** Configure monitoring, logging, and alerting.
- **Dependencies:** P0-1 (deployment).
- **Blocks Core Workflow:** No

### P2-7: CORS Configuration Needs Production Verification

- **Severity:** P2
- **Affected Functionality:** Frontend-backend communication in production
- **Files/Services:** xportra/api/runtime.py, xportra/api/app.py
- **Evidence:** CORS origins configured from environment but not verified in production.
- **Business Impact:** Frontend may not be able to communicate with backend in production.
- **Recommended Correction:** Verify CORS configuration in staging.
- **Dependencies:** P0-1 (deployment).
- **Blocks Core Workflow:** No

### P2-8: No Evidence of Live Document Processing

- **Severity:** P2
- **Affected Functionality:** Document extraction and processing
- **Files/Services:** xportra/domain/evidence_ingestion.py, xportra/application/evidence_document_ingestion.py
- **Evidence:** Document processing code exists but no live verification with real documents.
- **Business Impact:** Document extraction may fail with real-world documents.
- **Recommended Correction:** Test document processing with real regulatory documents.
- **Dependencies:** P0-2 (AI services).
- **Blocks Core Workflow:** No

---

## P3 — Minor (Non-Blocking Improvements)

### P3-1: Pre-existing Frontend Test Failure (RegisterPage)

- **Severity:** P3
- **Affected Functionality:** Registration page test
- **Files/Services:** frontend/src/features/auth/RegisterPage.test.tsx, frontend/src/app/pendingRegistration.ts
- **Evidence:** Test expects sessionStorage but implementation uses localStorage. Documented as pre-existing and unrelated to any milestone.
- **Business Impact:** None (test expectation mismatch, not a functional defect).
- **Recommended Correction:** Update test expectation or implementation to be consistent.
- **Dependencies:** None.
- **Blocks Core Workflow:** No

### P3-2: Large Chunk Advisory in Frontend Build

- **Severity:** P3
- **Affected Functionality:** Frontend bundle size
- **Files/Services:** frontend/vite.config.ts
- **Evidence:** Production build produces large chunks (advisory warning).
- **Business Impact:** Slightly slower initial load time.
- **Recommended Correction:** Implement code splitting for large chunks.
- **Dependencies:** None.
- **Blocks Core Workflow:** No

### P3-3: Missing PDF Report Generation

- **Severity:** P3
- **Affected Functionality:** Report export
- **Files/Services:** No PDF generation service found
- **Evidence:** Historical reports are web-based only.
- **Business Impact:** Minor inconvenience for report sharing.
- **Recommended Correction:** Implement PDF export for compliance reports.
- **Dependencies:** P1-6.
- **Blocks Core Workflow:** No

### P3-4: No Automated Frontend Tests for Catalog Integration

- **Severity:** P3
- **Affected Functionality:** Catalog display in shipment workflow
- **Files/Services:** frontend/src/features/shipment/ShipmentInfoPage.tsx
- **Evidence:** Catalog integration recently added but no dedicated frontend tests.
- **Business Impact:** Catalog display regressions may go undetected.
- **Recommended Correction:** Add frontend tests for catalog integration in ShipmentInfoPage.
- **Dependencies:** None.
- **Blocks Core Workflow:** No

---

## Summary Table

| ID | Severity | Blocks Core Workflow | Description |
|---|---|---|---|
| P0-1 | P0 | Yes | No production deployment or live verification |
| P0-2 | P0 | Yes | External AI services unverified |
| P1-1 | P1 | Yes | Catalog frontend not exercised end-to-end |
| P1-2 | P1 | Yes | Compliance assessment integration unverified |
| P1-3 | P1 | Yes | Evidence evaluation unverified |
| P1-4 | P1 | Yes | Production migrations not applied |
| P1-5 | P1 | Yes | Worker authorization not configured |
| P1-6 | P1 | Yes | Historical report reproducibility unverified |
| P2-1 | P2 | No | No PDF report generation |
| P2-2 | P2 | No | Shipment editing limited |
| P2-3 | P2 | No | No penetration testing |
| P2-4 | P2 | No | No load testing |
| P2-5 | P2 | No | Frontend test environment issues |
| P2-6 | P2 | No | No monitoring or alerting |
| P2-7 | P2 | No | CORS needs production verification |
| P2-8 | P2 | No | No live document processing |
| P3-1 | P3 | No | Pre-existing RegisterPage test failure |
| P3-2 | P3 | No | Large chunk advisory |
| P3-3 | P3 | No | Missing PDF generation |
| P3-4 | P3 | No | No automated frontend tests for catalog |