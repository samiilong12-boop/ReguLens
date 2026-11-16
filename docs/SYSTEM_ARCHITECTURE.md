# ReguLens — System Architecture Document (Multi-Sector Corrected)

## Document Status
- **Current Phase:** Phase 1 — Minimal Technical Foundation (In Progress: Package A & Package B complete in Draft PRs; Package C pending)
- **Strategic Scope:** Multi-Sector Architecture supporting both **Sector 1 (Agriculture & Agri-food)** and **Sector 2 (Textiles & Apparel)** as the long-term platform vision.
- **Selected First Vertical Slice (Phase 2):** **Fresh Egyptian Valencia Oranges (CN `0805 10 00`) exported to the European Union (EU-27)**. Formally approved by the founder as the first vertical slice to prove end-to-end multi-regime regulatory discovery, gap analysis, and dossier compilation. The multi-sector strategy is preserved as the strategic expansion path for Phase 3 and beyond, subject to exporter validation and trade data.
- **Approved Acceptance Targets (Targets Approved by Founder; NOT Achieved Results):**
  - Citation Validity: 100%
  - Citation Support: ≥98%
  - Requirement Extraction Precision: ≥95%
  - Requirement Extraction Recall: ≥95%
  - Unsupported-Claim Rate: 0%
  - Source Freshness: 100% within defined thresholds, otherwise a visible degraded-status warning.
  - Golden Dataset: 25 curated, human-verified test cases.
- **Architectural Principle:** Minimal Technology (`AGENTS.md` Rule 15 & `QUALITY_GATES.md` Section 5)
- **Security Boundary Notice:** PostgreSQL Row Level Security (RLS) is an additional database-engine authorization boundary, NOT cryptographic tenant isolation.

---

## 1. System Overview & Component Topology

ReguLens is structured as a clean, modular two-tier baseline architecture designed to deliver the multi-sector user journey with minimal operational friction, high auditability, and zero unneeded external services.

```mermaid
graph TD
    subgraph ClientBrowser ["Client Web Application"]
        UI["Next.js 15 (React 19, TypeScript)"]
        Locale["next-intl (Arabic RTL / English LTR)"]
        Query["TanStack Query (Client State)"]
    end

    subgraph ServerBackend ["Application & API Service (FastAPI)"]
        API["FastAPI 0.115+ (Python 3.12)"]
        AuthMiddleware["Tenant & Auth Session Context (Transaction-Local)"]
        DomainLogic["Multi-Sector Regulatory & Gap Analysis Engine"]
        AIAdapter["AIProviderAdapter (Gemini / OpenAI with Regex Fallback)"]
        WorkerLoop["PostgreSQL Job Poller (asyncio, SKIP LOCKED)"]
        PDFGen["Report Generator (WeasyPrint / Jinja2)"]
    end

    subgraph DataTier ["Data & Object Storage Tier"]
        DB[("PostgreSQL 16+")]
        RLS["Row Level Security (FORCE RLS on 12 Tables)"]
        JobsTable["background_jobs (SKIP LOCKED)"]
        Storage["Private S3 Object Storage (MinIO / R2)"]
    end

    subgraph ExternalServices ["External Systems (Controlled Boundary)"]
        AI_API["External LLM API (Google GenAI / OpenAI)"]
        EUR_LEX["EUR-Lex / Official Gazettes (Reference Snapshots)"]
    end

    UI -->|HTTPS / REST / JSON| API
    API --> AuthMiddleware
    AuthMiddleware --> DomainLogic
    DomainLogic -->|SQLAlchemy 2.0 (asyncio)| DB
    DB --- RLS
    DB --- JobsTable
    DomainLogic -->|Pre-signed URLs / S3 SDK| Storage
    WorkerLoop -->|Polls SKIP LOCKED| JobsTable
    WorkerLoop --> PDFGen
    WorkerLoop --> AIAdapter
    AIAdapter -->|Strict System Boundary| AI_API
    DomainLogic -.->|Periodic Metadata Verification| EUR_LEX
```

---

## 2. Multi-Sector Core Platform Architecture

1. **Shared Foundation:** Tenant isolation, user authentication, RBAC, document storage, background job queues, audit logging, and human expert verification are 100% sector-agnostic.
2. **Extensible Product Model:** Products share core attributes (`name`, `sector`, `hs_code`, `origin_country`), while sector-specific attributes (scientific name for fruit, fibre composition for apparel) are stored in structured `attributes JSONB`.
3. **Decoupled Regulatory Modules:** Applicability rules evaluate sector-specific criteria without hardcoding agricultural assumptions into the textile engine or vice versa.

---

## 3. Component Justification & Technology Selection (`QUALITY_GATES.md` § 5)

| Component | Status | Evidence of Need | Infrastructure & Operational Cost | Removal / Alternative Path |
|---|---|---|---|---|
| **Web Application (Next.js / TypeScript)** | Baseline | Multi-tenant B2B user experience, bilingual RTL/LTR layout management, SSR for fast initial loads, strict type safety. | Low: single Node.js runtime container or Vercel server. | Static SPA (Vite/React), but Next.js offers superior SSR and localized routing. |
| **Backend API (FastAPI / Python)** | Baseline | High-performance async Python backend; native access to Python document/PDF extraction libraries (`pdfplumber`, `pypdf`) and legal text parsing. | Low: single Python async service. | Express/NestJS (rejected due to weak native PDF parsing and data science tooling). |
| **Relational Database (PostgreSQL 16)** | Baseline | Relational integrity, ACID compliance, native Row Level Security (RLS) for tenant isolation, composite foreign keys, full-text search (`tsvector`). | Standard managed database tier. | Baseline component. |
| **Private File Storage (S3-compatible)** | Baseline | Secure storage of exporter commercial invoices, certificates, and lab reports. Signed temporary URLs prevent public exposure. | Storage pay-per-GB, zero fixed operational server cost. | Baseline component. |
| **In-Process Task Worker (`background_jobs`)** | Minimal | Non-blocking execution of PDF extraction, AI adapter requests, and report generation using PostgreSQL transactional queue (`SKIP LOCKED`). | Zero added server cost; runs within the backend process. | Redis + Celery (explicitly rejected for Slice due to extra daemon and broker sync risks). |

### Explicitly Rejected Components for Early Phases
1. **Redis & Celery / RabbitMQ:** Unnecessary infrastructure complexity for low-to-medium volume B2B document uploads. PostgreSQL `SKIP LOCKED` provides 100% transactional reliability without an extra broker container.
2. **`pgvector` / Vector Database:** Regulatory applicability is deterministic, governed by sector, HS code, origin, and attributes. Semantic vector similarity introduces hallucination and false-positive retrieval risks.
3. **Microservices:** Premature decomposition creates network serialization latency, distributed tracing overhead, and deployment fragility.

---

## 4. Bilingual Architecture (Arabic RTL / English LTR)

1. **Routing & Localization:** Handled by `next-intl` with locale prefixing (`/ar/...` and `/en/...`).
2. **Layout Mirroring:**
   - HTML document tag configured dynamically: `<html lang="ar" dir="rtl">` or `<html lang="en" dir="ltr">`.
   - Tailwind CSS logical properties utilized exclusively (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`) instead of hardcoded left/right directions.
   - Professional Arabic typography: `Cairo` for display headings and `IBM Plex Sans Arabic` for dense tabular and legal text.
3. **Legal Text Epistemic Separation:**
   - Official EU regulations are stored and presented in their authoritative authentic language (English).
   - Informational Arabic translations are machine-assisted and explicitly labeled:
     > *"الترجمة العربية استرشادية فقط؛ النص القانوني المعتمد هو النص الصادر في الجريدة الرسمية للاتحاد الأوروبي."*

---

## 5. Secure Document Storage & Upload Pipeline (Package C)

- **Storage Abstraction:** Provider-independent `StorageService` interface implemented across:
  - `MemoryStorageService`: In-memory dictionary storage with size checking for fast, isolated CI testing.
  - `LocalStorageService`: Development filesystem storage with strict path-traversal prevention.
  - `S3StorageService`: AWS S3 / MinIO object storage with mandatory SSL in production, presigned POST upload policies with `content-length-range` enforcement, and startup verification of Public Access Block configuration (`BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, `RestrictPublicBuckets`).
  - `GCSStorageService`: Google Cloud Storage adapter (GCP compatibility per ADR 0008) supporting signed URLs, bounded streaming reads, and verification of Uniform Bucket-Level Access (UBLA) and Public Access Prevention (PAP).
- **Private Storage Invariant:** 100% private bucket; zero public ACLs or public URLs. All client upload and download access operates exclusively through short-lived presigned URLs (15-minute expiry) or bounded API endpoints.
- **Transport Security:** Production and staging environments strictly require HTTPS/SSL (`S3_USE_SSL=True`); insecure `http://` endpoint URLs raise fail-closed configuration errors at startup.
- **Opaque Key Strategy:** User-supplied filenames are never used in object storage paths. Keys are strictly randomized and tenant-partitioned:
  - Quarantine: `tenants/{tenant_id}/quarantine/{opaque_uuid}`
  - Permanent: `tenants/{tenant_id}/documents/{opaque_uuid}`
- **Upload Size Enforcement & Memory Exhaustion Protection:**
  - Hard cap of **25 MB** (`MAX_DOCUMENT_SIZE_BYTES = 26,214,400`).
  - Enforced at upload transport level: S3 provider policy restricts uploads via `content-length-range` condition in presigned POST; for GCS where signed PUT URLs cannot enforce content-length policies at the provider boundary, `supports_direct_upload = False` and clients are directed to the authenticated server-mediated bounded streaming upload endpoint (`POST /api/v1/documents/{document_id}/upload-content`) which enforces byte bounds on Content-Length headers and streaming chunks before writing to quarantine.
  - During finalization, server inspects object metadata (`get_object_metadata`) to verify size *before* reading payload into memory, preventing memory exhaustion (DoS). Oversized objects in quarantine are safely deleted and rejected with HTTP 400.
- **Two-Phase Upload Lifecycle:**
  1. *Initiation (`POST /documents/initiate-upload`):* Requires Owner, Admin, or Compliance Officer role. Creates document record in `PENDING_UPLOAD` status and issues an upload transport payload (direct S3 presigned URL or server-mediated `/upload-content` endpoint with 15-minute expiry).
  2. *Client Upload:* Client streams bytes to the presigned quarantine URL (S3) or server-mediated endpoint (GCS).
  3. *Finalization & Validation (`POST /documents/{id}/finalize-upload`):* Server verifies size from metadata, fetches raw bytes with strict `max_bytes` limit, executes file signature inspection (magic-byte detection for approved MIME types: `application/pdf`, `image/png`, `image/jpeg`, `image/tiff`), and verifies SHA-256 checksum integrity.
  4. *Malware Scanning Subsystem:* Dispatches to `BaseMalwareScanner`:
     - *Clean Scan:* Atomically promotes object from quarantine to permanent storage, purges quarantine object, sets status to `AVAILABLE` and `antivirus_status` to `CLEAN`.
     - *Infected Scan (EICAR / Virus):* Deletes quarantined file immediately, sets status to `REJECTED`, `antivirus_status` to `INFECTED`, records virus signature, and returns HTTP 422.
     - *Scanner Unavailability / Error:* Fails safe with HTTP 503; document remains `QUARANTINED` and is NEVER marked clean or available.
- **Quarantine Retention & Pruning:** Abandoned quarantine objects older than 24 hours are safely purged by `purge_abandoned_quarantine_objects()` in `apps/api/app/services/cleanup.py`, operating strictly under tenant-scoped PostgreSQL RLS with live role verification (OWNER or ADMIN). Runnable via CLI (`python -m app.services.cleanup --tenant-id <UUID> --actor-user-id <UUID> --cutoff-hours 24`), preserving active uploads under 24 hours.
- **Secure Download Gate:** Presigned GET URLs (15-min expiry) are generated only for documents where `status == "AVAILABLE"` and `antivirus_status == "CLEAN"`. All unvalidated, quarantined, rejected, or infected documents return HTTP 403 Forbidden.
- **Audit Logging & Secret Redaction:** Append-only audit records are written on initiation, finalization, download URL generation, deletion, and cleanup events. All presigned URLs, query signatures, tokens, and passwords are sanitized before audit persistence.
- **Antivirus Engine Disclosure:**
  - *Production Target:* `ClamAVScanner` connecting over TCP (`zINSTREAM` protocol) with fail-closed timeout and connection error handling. Production/staging strictly rejects `MockMalwareScanner`.
  - *Testing / CI Engine:* `MockMalwareScanner` with built-in EICAR antivirus test signature detection and configurable failure simulation.
  - *Operational Notice:* Magic-byte checking is NOT claimed to be equivalent to antivirus scanning. Live ClamAV daemon connectivity and properly configured cloud buckets are required for production certification.
