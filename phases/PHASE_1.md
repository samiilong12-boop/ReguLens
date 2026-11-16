# Phase 1: Minimal Technical Foundation

**Gate 1 Status:** READY FOR FOUNDER SIGN-OFF — Packages A, B, and C implemented in Draft PRs (#1, #2, #3); test suite expanded to 119 tests (including 21 document lifecycle integration tests and 45 PostgreSQL 16 RLS security tests); CI configuration disclosure documented; awaiting final founder sign-off.  
**Entry Condition:** Gate B status is READY FOR FOUNDER SIGN-OFF — final founder review pending.  
**Read First:** `AGENTS.md`, `.agents/rules/TEAM_WORKFLOW.md`, `.agents/rules/QUALITY_GATES.md`, `phases/ROADMAP.md`, and the approved documents and ADRs from Phase 0B (`docs/PRODUCT_REQUIREMENTS.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/DATABASE_SCHEMA.md`, `docs/SECURITY_ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, `docs/TEST_STRATEGY.md`, `docs/adr/0002-multi-tenant-isolation-and-rls.md`, `docs/adr/0008-gcp-compatibility-and-security-preservation.md`). Do the start-of-session check.

**Goal:** Build and verify a minimal, secure, and testable multi-tenant technical foundation (authentication, tenant discovery, token-bound tenant switching, PostgreSQL RLS isolation, private file storage, audit basics, and CI) supporting the approved Vertical Slice without application business logic.

---

## 1. Scope Breakdown: Current Implementation & Verification Status

In accordance with `.agents/rules/TEAM_WORKFLOW.md`, the phase scope is explicitly categorized into four distinct factual states:

### 1.1. Implemented & CI-Verified Work
- **Package A (Multi-Tenant RLS Session Context & GUC Enforcement):**
  - Transaction-local GUC configuration (`app.current_tenant_id`, `app.current_user_id`) using `set_config(..., true)`.
  - PostgreSQL connection checkout/checkin listener with reset (`RESET ALL`) on pool checkout.
  - Defensive `SessionLocal` guard raising `RuntimeError` if invoked without explicit tenant/user context.
  - Alembic migrations `0001_initial_schema` and `0002_rls_policies`.
  - Implemented in `apps/api/app/db/session.py` and `apps/api/app/api/deps.py`; preserved in Draft PR #1.
- **Package B (Token-Bound Tenant Switching & Live Role Demotion Protection):**
  - User membership discovery endpoint `GET /auth/memberships` operating under user-scoped RLS policies.
  - Token-bound tenant switching endpoint `POST /auth/switch-tenant` validating active user and tenant status before issuing a tenant-scoped access token.
  - Dynamic membership role verification via `get_current_tenant_user` and `require_owner` preventing privilege escalation from stale JWT role claims.
  - User-scoped RLS policies on `tenants` and `tenant_users` via Alembic migration `0003_membership_rls_policies`.
  - Bidirectional migration downgrade/upgrade cycle verification (`0003` -> `0002` -> `0003`).
  - Implemented in `apps/api/app/api/v1/endpoints/auth.py` and `apps/api/app/api/deps.py`; preserved in Draft PR #2.
- **Package C (Private File Storage Pipeline & Upload Security):**
  - Pluggable storage abstraction (`StorageService` with `MemoryStorageService`, `LocalStorageService`, `S3StorageService`) isolating files by tenant under `tenants/{tenant_id}/quarantine/` and `tenants/{tenant_id}/documents/`.
  - Two-phase upload lifecycle: upload initiation (`POST /api/v1/documents/initiate-upload`) generating 15-minute presigned upload URLs with `PENDING_VALIDATION` status, followed by upload finalization (`POST /api/v1/documents/{id}/finalize-upload`).
  - Server-side file validation (`file_validation.py`): hard 25MB file size limit (`MAX_DOCUMENT_SIZE_BYTES`), magic-byte file signature validation (`application/pdf`, `image/png`, `image/jpeg`, `image/tiff`), and SHA-256 payload integrity hash verification.
  - Malware scanning subsystem (`scanner.py`): `BaseMalwareScanner`, `ClamAVScanner` connecting via streaming TCP protocol, and `MockMalwareScanner` detecting standard EICAR test string.
  - Fail-safe invariant: scanner errors/timeouts raise `ScannerUnavailableError` (HTTP 503 Service Unavailable), never silently marking unscanned files as clean. Malware detection rejects upload (HTTP 422), purges file from quarantine storage, and sets status to `QUARANTINED`.
  - Secure authenticated download (`GET /api/v1/documents/{id}/download-url`): generates 15-minute presigned download URLs strictly for documents with `status == "AVAILABLE"` and `quarantine_key is None`. Rejects unvalidated or infected files with HTTP 403 Forbidden.
  - Authorized document deletion (`DELETE /api/v1/documents/{id}`): Owner/Admin only; purges object from storage backend and deletes database row.
  - Sanitized audit logging (`audit.py`): logs document upload, download URL generation, failure, and deletion events while automatically redacting presigned URLs, query tokens, and authorization headers.
  - Alembic migration `0004_document_storage_fields.py` adding storage fields, nullable `consignment_id`, `idx_documents_status`, with full bidirectional downgrade/upgrade test.
  - Implemented in `apps/api/app/services/`, `apps/api/app/api/v1/endpoints/documents.py`, `apps/api/alembic/versions/0004_document_storage_fields.py`; preserved in Draft PR #3.
- **Automated Test Execution:**
  - 119 total tests passing locally: 53 unit tests, 21 document lifecycle integration tests, 45 PostgreSQL 16 RLS security and migration cycle tests.
  - 100% pass rate with zero skips and zero failures.

### 1.2. Requirements Not Yet Implemented
- **CI Quality Gate Pipeline Enhancements:**
  - Ruff linting and formatting step.
  - MyPy static type-checking step.
  - Frontend lint, type-check, and build steps.
  - Automated dependency vulnerability scanning step.

### 1.3. Requirements Not Yet Independently Verified
- **Independent External Review:** Reviews conducted to date are automated CI pipeline checks and agent self-reviews. No independent external third-party human security audit has taken place (`QUALITY_GATES.md` Section 1).
- **Tenant Isolation Verification Scope (Distinguishing Catalog vs. Behavioral Testing):**
  - **Catalog Policy Verification:** Verified via `test_catalog_all_rls_policies_contain_nullif`, confirming that all 13 tenant policies and 2 user policies in PostgreSQL system catalogs (`pg_policies`) enforce `NULLIF`.
  - **Behavioral Isolation Tests:** Automated cross-tenant CRUD tests currently execute on: `products`, `consignments`, `documents`, `background_jobs`, `tenant_users`, and `tenants`. Other tenant-owned child tables (e.g., `consignment_items`, `document_analyses`) are protected by composite foreign keys and catalog policies, but do not yet have dedicated standalone behavioral CRUD isolation tests. Therefore, 100% behavioral isolation is NOT claimed across all tables.

### 1.4. Founder Actions Still Pending
- **Gate B Formal Approval:** Final founder written sign-off approving the Phase 0B deliverables, the first vertical slice, and the quantitative acceptance targets (`Requires founder action`).
- **Gate 1 Formal Approval:** Final founder written sign-off upon Package C completion and Draft PR #3 review (`Requires founder action`).
- **Legal Review:** Review of `docs/PRIVACY_POLICY_DRAFT.md` and `docs/DATA_RETENTION_POLICY.md` by a qualified attorney (`Requires founder action`).
- **Trade Expert Engagement:** Identification and contracting of a qualified human agricultural trade compliance expert for Phase 2 golden dataset verification (`Requires founder action`).

---

## 2. Accurate CI Limitations Disclosure

Direct inspection of `.github/workflows/phase1-ci.yml` establishes the following operational profile:

| Check Category | Current CI Status | CI Workflow Evidence (`.github/workflows/phase1-ci.yml`) |
|---|---|---|
| **Backend Pytest Suite** | **PRESENT & ENFORCED** | Job `test-phase1-rls`, Step `Execute complete test suite` running `uv run pytest -c pyproject.toml -v -rs --junit-xml=test-results.xml` (lines 103–111). |
| **PostgreSQL 16 Service & RLS Tests** | **PRESENT & ENFORCED** | Service container `postgres:16-alpine` (lines 22–34), provisioning via `scripts/init_db_roles.sql` (lines 49–53), XML gate asserting ≥44 RLS tests and 0 skips (lines 113–200). |
| **Ruff (Python Linting)** | **NOT CURRENTLY RUN** | Zero occurrences in `.github/workflows/phase1-ci.yml`. No linting step configured. |
| **MyPy (Static Type-Checking)** | **NOT CURRENTLY RUN** | Zero occurrences in `.github/workflows/phase1-ci.yml`. No type-checking step configured. |
| **Frontend Lint** | **NOT CURRENTLY RUN** | Zero frontend jobs or steps configured in CI workflow. |
| **Frontend Type-Check** | **NOT CURRENTLY RUN** | Zero frontend TypeScript checking steps configured in CI workflow. |
| **Frontend Build** | **NOT CURRENTLY RUN** | Zero frontend build steps configured in CI workflow. |
| **Dependency Vulnerability Scanning** | **NOT CURRENTLY CONFIGURED** | Zero vulnerability scanning tools (such as `pip-audit`, `npm audit`, `trivy`, or `dependabot`) configured in workflow. |

*Note: In accordance with task constraints, these missing CI checks are accurately documented as unresolved quality gate gaps and are NOT implemented in this documentation task.*

---

## 3. Strict Non-Goals (Out of Scope for Phase 1)

1. **Vertical Slice Business Logic (Phase 2):** Product profile creation, trade lane selection, regulatory rule evaluation, AI document parsing, gap analysis, and PDF report generation.
2. **External Customs / Portals:** TRACES NT, CAPQ, customs filing servers, or external trade databases (`AGENTS.md` Rule 9).
3. **Payment & Subscriptions:** Stripe, PayPal, Paymob, or subscription billing infrastructure (deferred to Phase 3 per `phases/ROADMAP.md`).
4. **Public User Registration / Self-Service Invites:** SMTP/SendGrid email delivery workflows for self-serve signups (deferred to Phase 2/3).
5. **Distributed Queues / Caches:** Redis, Celery, RabbitMQ, Kafka, or Elasticsearch (rejected per `docs/adr/0001-minimal-technology-stack.md` and `docs/adr/0006-minimal-background-jobs-without-distributed-queues.md`).

---

## 4. Work Packages Summary

| Work Package | Focus Area | Status | Repository Evidence |
|---|---|---|---|
| **Package A** | Multi-Tenant RLS Session Context & GUC Enforcement | **COMPLETED** (In Draft PR #1) | `apps/api/app/db/session.py`, `apps/api/app/api/deps.py`, Alembic `0001` & `0002`, tests in `tests/security/test_tenant_isolation.py`. Draft PR #1 open, unmerged. |
| **Package B** | Token-Bound Tenant Switching & Live Role Authorization | **COMPLETED** (In Draft PR #2) | `apps/api/app/api/v1/endpoints/auth.py`, `apps/api/app/api/deps.py`, Alembic `0003`, integration tests in `tests/integration/test_fastapi_tenant_authorization.py`, migration cycle test `tests/test_migrations.py`. CI Run #43624757872 (82 passed, 0 failed). Draft PR #2 open, unmerged. |
| **Package C** | Private File Storage Pipeline & Upload Security | **COMPLETED** (In Draft PR #3) | `apps/api/app/services/storage.py`, `file_validation.py`, `scanner.py`, `audit.py`, `endpoints/documents.py`, Alembic `0004`, 21 integration tests in `tests/integration/test_document_lifecycle.py`, 4 unit test suites. Draft PR #3 open, unmerged. |

---

## 5. Measurable Exit Criteria for Gate 1 Closure

1. **Automated Test Coverage & Green CI:** 100% automated test pass rate across unit, integration, and security test suites in GitHub Actions CI with zero skips or failures (110+ tests target).
2. **Tenant Isolation Verification:** Automated test suite proves RLS isolation across tenant-bound tables under `app_user` unprivileged role, clearly distinguishing catalog inspection from behavioral testing.
3. **Negative Authorization & Role Enforcement:** Live database role checks verified; stale JWT role escalation rejected; cross-tenant access returns HTTP 403 or 404.
4. **Migration Downgrade & Upgrade Integrity:** Automated test proves clean rollback and re-application of all Alembic migrations (`0001` -> `0002` -> `0003` -> `0004` -> `0003` -> `0004`) without data loss or residual state.
5. **Private Storage Pipeline (Package C):** Presigned URL generation, upload validation (MIME magic-bytes, SHA-256, 25MB cap), fail-safe antivirus checks, authenticated download URLs, and deletion fully implemented and verified with 21 lifecycle tests.
6. **CI Pipeline Completion:** CI gaps (Ruff, MyPy, frontend validation, dependency scanning) documented and addressed.
7. **Zero High/Critical Vulnerabilities:** Dependency and SAST audits show zero unresolved high or critical vulnerabilities.
8. **Draft PR Governance:** PR #1, PR #2, and PR #3 reviewed, merged into base branches only with explicit founder approval; `master` remains protected.
9. **Written Founder Sign-Off:** Gate 1 end-of-phase report delivered; explicit written founder approval obtained before Phase 2 initiation.

---

## 6. Process & Quality Gate

- Follow `.agents/rules/TEAM_WORKFLOW.md` for all tasks.
- Gate: write the end-of-phase report in the format of `.agents/rules/QUALITY_GATES.md` section 1, state whether the review was independent, then STOP and wait for the founder's explicit written approval before starting Phase 2.
