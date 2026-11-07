# ADR 0001: Minimal Technology Stack for ReguLens Vertical Slice

## Status
Approved (Architecture Decision for Phase 0B / Phase 1)

## Date
2026-11-07

## Context
ReguLens is a regulatory-intelligence and export-readiness assistance SaaS designed to help manufacturers and exporters identify destination market requirements, verify supporting documents, identify gaps, and generate traceable compliance research reports.

Per `AGENTS.md` (Rule 15: Minimal Technology) and `.agents/rules/QUALITY_GATES.md` (Section 5: Technology Gate), the system must start from the fewest moving parts that deliver the approved scope:
> "Start from: a web app, a backend API, PostgreSQL, private file storage. Do not add Redis, Celery or another queue, pgvector or semantic search, or separate services unless you show a real need for the approved scope. For each component beyond the baseline, give the written justification required by QUALITY_GATES.md section 5. Also list notable components you rejected and why."

The initial scope approved for the Vertical Slice (Phase 2) is a single commodity and trade lane: **Fresh Egyptian Valencia Oranges (CN 0805 10) exported to the European Union**.

## Options Considered

### Option 1: Microservices with Distributed Task Queues and Vector Database (Original Spec in `docs/SPEC_MODULES.md`)
- **Frontend:** Next.js (TypeScript)
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL with `pgvector`
- **Asynchronous Tasks:** Celery + Redis broker
- **Search:** Hybrid BM25 full-text + vector similarity embeddings
- **File Storage:** AWS S3 / Supabase Storage
- **Evaluation:**
  - *Pros:* High theoretical scalability, decoupled services, early semantic search.
  - *Cons:* Severe operational complexity (5 independent runtime containers/processes to maintain, monitor, and deploy), premature optimization for a single-product slice, complex local dev setup, high infrastructure cost, unnecessary vector search overhead when regulatory applicability for the slice is deterministically driven by CN codes (0805 10) and official regulatory act criteria.

### Option 2: Unified TypeScript Monorepo (Next.js App Router Full-Stack)
- **Frontend & API:** Next.js 15 (Node.js runtime / TypeScript)
- **Database:** PostgreSQL with Prisma / Drizzle ORM
- **Task Queue:** Node.js background timers / in-process execution
- **Evaluation:**
  - *Pros:* Single language, single runtime deployment.
  - *Cons:* Python has a vastly superior ecosystem for document extraction, PDF parsing (e.g. `pypdf`, `pdfplumber`), tabular regulatory data manipulation, and legal NLP compared to Node.js. Forcing regulatory document parsing and report generation into Node.js increases library fragility and limits downstream AI extraction tooling.

### Option 3: Clean Two-Tier Minimal Baseline (Approved)
- **Web App:** Next.js (React 19, TypeScript, Tailwind CSS, shadcn/ui, `next-intl` for Arabic RTL/English LTR)
- **Backend API:** Python 3.12+ with FastAPI, Pydantic v2, and SQLAlchemy 2.0 (asyncio)
- **Database:** PostgreSQL 16+ (relational schema, Row Level Security for tenant isolation, built-in Full-Text Search via `tsvector`/`GIN`)
- **Private File Storage:** S3-compatible object storage (MinIO for local dev/test; Cloudflare R2 / AWS S3 for production) accessed strictly via server-side signed URLs
- **Background Tasks:** PostgreSQL-backed task queue (`FOR UPDATE SKIP LOCKED`) executed by a lightweight worker thread inside the FastAPI backend service
- **AI Integration:** Abstract server-side provider adapter (supporting OpenAI / Google Gemini) with strict deterministic fallback, operating solely on retrieved text

## Decision
Adopt **Option 3 (Clean Two-Tier Minimal Baseline)**:
1. **Frontend:** Next.js (TypeScript) hosting the UI, user workflows, and RTL/LTR localization.
2. **Backend API:** FastAPI (Python) hosting all domain logic, regulatory rule evaluations, document text extraction, report generation, and AI provider integration.
3. **Database:** PostgreSQL 16 with native `tsvector` full-text search. No `pgvector` in the Vertical Slice.
4. **File Storage:** S3-compatible private object storage with zero public bucket access.
5. **Worker:** In-process lightweight transactional job poller over PostgreSQL task table (`FOR UPDATE SKIP LOCKED`). No Redis, No Celery.

## Component Justifications (Quality Gates Section 5)

| Component | In Baseline? | Evidence of Need | Infrastructure & Operational Cost | Removal / Alternative Path |
|---|---|---|---|---|
| **Web App (Next.js)** | Yes | Core requirement: B2B multi-tenant interface, bilingual RTL/LTR document upload and review journey. | Low: single Node.js runtime container. | Replaced only by static client + SPA, but SSR/routing benefits justify Next.js. |
| **Backend API (FastAPI)** | Yes | Core requirement: Deterministic regulatory evaluation, Python PDF parsing, document processing, and AI orchestration. | Low: single Python async service. | Consolidated into Next.js API routes (inferior Python document library support). |
| **PostgreSQL 16** | Yes | Core requirement: Relational integrity, tenant RLS isolation, immutable audit logs, ACID transactional safety. | Standard managed database tier. | Baseline component. |
| **Private File Storage (S3-compatible)** | Yes | Core requirement: Secure storage of exporter commercial invoices, phytosanitary certificates, and lab reports. | Minimal: storage per GB, zero fixed server cost. | Baseline component. |

## Explicitly Rejected Components for Vertical Slice

1. **Redis & Celery / RabbitMQ:**
   - *Reason for Rejection:* The Vertical Slice processes low-volume documents (a single orange export consignment involves 4-6 documents: Phytosanitary Certificate, EUR.1, Pesticide MRL Lab Test, Bill of Lading, Invoice). Adding Redis and Celery introduces external daemon dependencies, broker monitoring, network partitioning failure modes, and operational overhead without any throughput necessity.
   - *Alternative:* A PostgreSQL transactional queue table (`jobs`) using `SELECT ... FOR UPDATE SKIP LOCKED` handles async PDF generation and document parsing natively within PostgreSQL transactions with zero extra infrastructure.
2. **Vector Database / `pgvector`:**
   - *Reason for Rejection:* The regulatory requirements for Egyptian Valencia Oranges are governed by specific, identifiable EU legal acts (Regulation (EU) 2016/2031, Regulation (EU) 2019/2072, Regulation (EU) 2019/1793 as amended by Regulation (EU) 2026/194, Regulation (EC) No 396/2005, and Decision No 1/2024). Applicability is determined by deterministic rules matching CN code (0805 10 00), origin (Egypt), and commodity type. Vector similarity search risks hallucinations, fuzzy matches, and ungrounded retrieval. Standard PostgreSQL full-text search (`tsvector` + English/Arabic dictionary) is completely sufficient for text lookup.
3. **Microservices Architecture:**
   - *Reason for Rejection:* Premature decomposition adds distributed network latency, cross-service authentication overhead, distributed tracing requirements, and deployment complexity. A modular monolith within FastAPI separates concerns while running in a single cohesive service.

## Consequences
- **Positive:**
  - Extremely fast local setup and CI execution (only requires Node, Python, and PostgreSQL).
  - Strict compliance with `AGENTS.md` minimal technology rule.
  - Zero risk of broker desynchronization between Redis and PostgreSQL.
  - Robust Python data ecosystem for parsing regulatory PDFs and phytosanitary certificates.
- **Negative / Trade-offs:**
  - High-concurrency batch processing (e.g., thousands of simultaneous document uploads) will eventually require offloading to dedicated worker processes in Phase 3 or 4.
  - Two language environments (TypeScript for frontend, Python for backend) require maintaining two package manifests (`package.json` and `pyproject.toml`).

## Reversal Path
If throughput demands in Phase 3 exceed single-process async worker capabilities, the PostgreSQL task table interface can be swapped for a distributed message queue (e.g., Celery/Redis or AWS SQS) without modifying business logic interfaces.
