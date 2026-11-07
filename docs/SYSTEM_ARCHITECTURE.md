# ReguLens — System Architecture Document (Multi-Sector Corrected)

## Document Status
- **Current Phase:** Phase 1 — Minimal Technical Foundation
- **Strategic Scope:** Multi-Sector Architecture supporting both **Sector 1 (Agriculture & Agri-food)** and **Sector 2 (Textiles & Apparel)**
- **Provisional Test Case:** Fresh Egyptian Valencia Oranges (CN `0805 10 00`) to EU serves strictly as a provisional engineering test case for early validation.
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

## 5. Security & Antivirus Status Disclosure

- **Storage Security:** 100% private S3 buckets; zero public URLs. Access granted exclusively via short-lived signed URLs (15 minutes).
- **Upload Validation:** Server-side magic-byte inspection (`python-magic`), 25MB file size limits, and randomized storage keys.
- **Antivirus Status:**
  - *Production Target:* ClamAV container daemon scanning uploaded streams before parsing.
  - *Development Limitation Notice:* In local developer environments without Docker, ClamAV is not installed. Safe parsing in an unprivileged process and strict magic-byte validation are enforced locally. Magic-byte checking is NOT claimed to be equivalent to antivirus scanning.
