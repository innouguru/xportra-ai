# Xportra AI — Recommended Completion Roadmap

**Audit Date:** 2026-10-31
**Type:** Dependency-aware implementation roadmap to close identified blockers

---

## Principle

This roadmap closes the identified blockers with the **smallest sensible changes**. It does not propose rebuilding working functionality. Each phase builds on the previous one. No phase should be skipped.

---

## Phase 1: Staging Environment and Live Verification (P0)

**Goal:** Establish a running staging environment and verify all external service connections.

**Tasks:**
1. Deploy backend to staging (FastAPI + worker) with environment variables configured
2. Deploy frontend to staging (Vite build) with API base URL pointing to staging backend
3. Apply migrations 030-033 to staging database
4. Configure Supabase auth with staging project
5. Configure Qdrant instance for staging
6. Configure AI provider API keys (OpenAI/Anthropic) for staging
7. Configure storage (Supabase Storage or local) for evidence uploads
8. Verify health check endpoint responds
9. Verify worker starts and is authorized (GRANT_MANAGE grant for worker actor)

**Deliverables:** Running staging environment, all external service connections verified, migration application confirmed

**Dependencies:** None (first phase)
**Estimated Effort:** Medium

---

## Phase 2: End-to-End Workflow Verification (P1)

**Goal:** Verify the complete exporter workflow with real data in staging.

**Tasks:**
1. Register a test exporter account and organization
2. Create a shipment with product, origin, destination
3. Verify regulatory catalog returns applicable requirements for the shipment
4. Verify missing scope fields fail closed (no unconfirmed requirements shown)
5. Upload evidence documents for regulatory requirements
6. Verify document processing (extraction, chunking, indexing)
7. Verify evidence evaluation against requirements
8. Verify compliance assessment generation
9. Verify progress tracking and missing evidence identification
10. Finalize shipment and verify historical report
11. Verify immutability after finalization

**Deliverables:** Documented end-to-end workflow verification, bug fixes for any discovered issues, updated test coverage for verified flows

**Dependencies:** Phase 1
**Estimated Effort:** Medium-Large

---

## Phase 3: Compliance Assessment Integration (P1)

**Goal:** Connect compliance assessment to the exporter workflow and catalog requirements.

**Tasks:**
1. Verify assessment trigger from frontend (AssessmentPage.tsx)
2. Connect catalog requirements to assessment input
3. Verify assessment uses correct shipment scope
4. Verify assessment evaluates available evidence
5. Verify assessment identifies missing/inadequate evidence
6. Verify assessment updates when evidence changes
7. Verify assessment history preservation

**Deliverables:** Verified assessment integration, updated frontend assessment page if needed, assessment trigger documentation

**Dependencies:** Phase 2
**Estimated Effort:** Medium

---

## Phase 4: Evidence Evaluation Verification (P1)

**Goal:** Verify evidence evaluation against regulatory requirements with real documents.

**Tasks:**
1. Upload real regulatory documents (PDFs, etc.) as evidence
2. Verify document extraction and processing
3. Verify evidence-to-requirement matching
4. Verify evidence sufficiency evaluation
5. Verify contradiction detection
6. Verify uncertainty preservation
7. Verify evidence replacement and re-analysis

**Deliverables:** Verified evidence evaluation flow, bug fixes for document processing issues, updated evidence tests with real documents

**Dependencies:** Phase 2, Phase 3
**Estimated Effort:** Medium

---

## Phase 5: Historical Report and Finalization Verification (P1)

**Goal:** Verify historical report generation and finalization immutability.

**Tasks:**
1. Complete a full shipment workflow end-to-end
2. Finalize the shipment
3. Verify historical report displays correctly
4. Verify report traceability (requirements, evidence, assessment)
5. Verify immutability (no modifications after finalization)
6. Verify report reproducibility (same results on re-access)

**Deliverables:** Verified historical report flow, documentation of finalization process, immutability verification evidence

**Dependencies:** Phase 2, Phase 3, Phase 4
**Estimated Effort:** Small-Medium
---

## Phase 6: Security and Performance (P2)

**Goal:** Ensure the application is secure and performs adequately.

**Tasks:**
1. Conduct security audit (authorization boundaries, tenant isolation, input validation)
2. Conduct penetration testing (if authorized)
3. Conduct load testing with realistic concurrent users
4. Verify CORS configuration in production
5. Review and fix any security findings
6. Configure monitoring, logging, and alerting
7. Set up error reporting (Sentry or equivalent)

**Deliverables:** Security audit report, load test results, monitoring and alerting configuration, performance baseline

**Dependencies:** Phase 1, Phase 2
**Estimated Effort:** Medium-Large

---

## Phase 7: Production Deployment (P0/P1)

**Goal:** Deploy to production with all verified components.

**Tasks:**
1. Apply migrations 030-033 to production database
2. Configure production environment variables
3. Deploy backend to production
4. Deploy frontend to production
5. Configure production Supabase auth
6. Configure production worker authorization
7. Verify health checks in production
8. Conduct production smoke test
9. Document deployment procedure
10. Set up rollback procedure

**Deliverables:** Production deployment, deployment documentation, rollback procedure, production smoke test results

**Dependencies:** Phase 1-6
**Estimated Effort:** Medium

---

## Phase 8: Post-Deployment Verification (P1)

**Goal:** Verify all functionality in production.

**Tasks:**
1. Register a real test account in production
2. Complete a full shipment workflow in production
3. Verify all external service connections in production
4. Verify regulatory ingestion worker in production
5. Verify monitoring and alerting in production
6. Document any production-specific issues

**Deliverables:** Production verification report, production issue log, updated documentation

**Dependencies:** Phase 7
**Estimated Effort:** Small-Medium

---

## Phase 9: Minor Improvements (P2/P3)

**Goal:** Address non-blocking improvements.

**Tasks:**
1. Fix frontend test environment configuration (P2-5)
2. Add frontend tests for catalog integration (P3-4)
3. Implement PDF report generation (P2-1, P3-3)
4. Add shipment editing capability (P2-2)
5. Implement code splitting for large chunks (P3-2)
6. Fix RegisterPage test storage expectation (P3-1)
7. Add monitoring dashboard

**Deliverables:** Improved test reliability, PDF report generation, shipment editing, better bundle size

**Dependencies:** Phase 7, Phase 8
**Estimated Effort:** Medium

---

## Dependency Graph

Phase 1 (Staging) -> Phase 2 (E2E Verification) -> Phase 3 (Assessment Integration)
                                                          |
                                                          v
Phase 4 (Evidence Evaluation) -> Phase 5 (Historical Reports)
                                                          |
                                                          v
Phase 6 (Security/Performance) -> Phase 7 (Production Deployment)
                                                          |
                                                          v
Phase 8 (Post-Deployment Verification) -> Phase 9 (Minor Improvements)

---

## What Should NOT Be Rebuilt

The following capabilities are well-implemented and should be preserved:

1. **Domain layer** (xportra/domain/) — Clean business logic, tested
2. **Application layer** (xportra/application/) — Comprehensive use cases
3. **Persistence layer** (xportra/persistence/) — Repository pattern, tenant isolation
4. **API boundary** (xportra/api/) — Clean FastAPI boundary, authorization
5. **Regulatory governance** — Two-stage review, publication, withdrawal, wording correction
6. **Frontend workspace** — Complete React application with auth, shipments, compliance
7. **Test infrastructure** — 2,300+ unit tests, integration test framework
8. **Database schema** — 33 migrations with rollback scripts
9. **Authorization model** — Tenant isolation, role-based permissions, staff grants

---

## Critical Path

The critical path to production is:

**Phase 1 -> Phase 2 -> Phase 3 -> Phase 7 -> Phase 8**

Phases 4, 5, 6, and 9 can be partially parallelized but should not be skipped.

The minimum viable production deployment requires Phases 1, 2, 3, 7, and 8.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| External AI services fail in production | Medium | High | Verify in staging first; implement fallbacks |
| Database migration issues | Low | High | Test migrations in staging; have rollback scripts |
| Performance under load | Unknown | Medium | Conduct load testing before production |
| Security vulnerabilities | Unknown | High | Conduct security audit before production |
| User adoption challenges | Medium | Medium | User testing and feedback collection |

---

## Conclusion

The Xportra AI codebase is substantial and well-architected. The primary blockers are operational (deployment, live verification) rather than architectural. The recommended approach is to verify the system in staging with real data before attempting production deployment, following the phased roadmap above.

**Estimated total effort to production readiness:** 4-8 weeks (depending on team size and external service availability).