# ReguLens — Open Questions & Decision Log

## Document Status
- **Current Phase:** Phase 0B — Technical Architecture & MVP Definition
- **Purpose:** Central inventory of unresolved regulatory, product, technical, and legal ambiguities, each paired with the safest recommended default assumption (`AGENTS.md` Working Agreements).
- **Rule:** Continue with the safest assumption; never assume unsafely and silently. Items requiring human action are marked `Requires founder action` or `Requires founder decision`.

---

## 1. Domain & Regulatory Open Questions

### Q-REG-01: Procedural Relationship between CHED-PP and CHED-D for Egyptian Citrus
- **Context:** Egyptian Valencia Oranges are subject both to plant health certification (Phytosanitary Certificate + CHED-PP under Regulation (EU) 2016/2031 & 2019/2072) and enhanced official food safety controls for pesticide residues (10% check rate + CHED-D under Regulation (EU) 2019/1793 as amended by Regulation (EU) 2026/194).
- **Ambiguity:** Does an EU border control post (BCP) process a single split consignment notification within TRACES NT, or are two distinct CHED filings (one CHED-PP and one CHED-D) required from the EU import agent for every single container?
- **Recommended Default:** Present both CHED-PP and CHED-D as distinct, non-substitutable regulatory tracks in the checklist. Do not assume one replaces the other. Provide citations for both regimes and advise exporters that their EU clearing agent must verify BCP operational protocol.
- **Status:** Requires founder action (Expert reviewer validation during Phase 2).

### Q-REG-02: Definitive Legal Status of EN 17394 (Children's Apparel Fasteners)
- **Context:** In Phase 0A research, EN 17394 (safety of children's clothing) was examined. Decision (EU) 2026/901 Annex I lists EN 14682:2014, but does not list EN 17394. Part 3 is designated as a Technical Specification (CEN/TS 17394-3:2021) in some catalogs and a standard in others.
- **Ambiguity:** Has any part of EN 17394 been harmonized under the GPSR with presumption of safety, or does it remain voluntary industry guidance?
- **Recommended Default:** Exclude EN 17394 from the Vertical Slice (since Slice is 100% focused on fresh oranges). In future apparel expansion (Phase 3), classify EN 17394 strictly as non-harmonized industry best practice, never claiming a formal GPSR presumption of safety.
- **Status:** Resolved for Slice; pending Phase 3 expansion.

### Q-REG-03: Consolidated Text Verification of Regulation (EU) 2019/2072 Annex XI
- **Context:** The local primary text examined in Phase 0A was the original 2019 publication (`OJ L 319, 10.12.2019`). Subsequent amendments may have altered specific commodity listings in Annex XI.
- **Ambiguity:** The exact current consolidated Annex XI listing for fresh citrus fruit requires verification against EUR-Lex live API.
- **Recommended Default:** In the Phase 2 regulatory seed data, cite the base regulation and note: *"Requirements verified against base Regulation (EU) 2019/2072; current consolidated annex requires expert confirmation."*
- **Status:** Requires founder action (Expert reviewer check).

---

## 2. Technical & Architectural Open Questions

### Q-TECH-01: Authentication Infrastructure: Custom JWT vs. Managed Auth (e.g. Supabase Auth)
- **Context:** The minimal architecture supports standard email/password authentication with JWTs stored in HttpOnly cookies. Managed providers like Supabase Auth offer built-in email verification and password resets.
- **Ambiguity:** Should Phase 1 build custom FastAPI JWT authentication or leverage Supabase Auth?
- **Recommended Default:** Use lightweight custom FastAPI JWT authentication with Argon2id and PostgreSQL-backed sessions. This eliminates external SaaS dependencies, guarantees complete local testability without cloud accounts, and adheres strictly to Rule 15 (Minimal Technology).
- **Status:** Recommended default approved; awaiting founder sign-off.

### Q-TECH-02: PDF Generation Library: WeasyPrint vs. ReportLab
- **Context:** Generating audit-grade PDF export dossiers with Arabic RTL typography and table borders.
- **Ambiguity:** WeasyPrint renders HTML+CSS directly to PDF (easy bilingual styling), but requires Cairo/Pango system binaries. ReportLab is pure Python but requires manual canvas coordinate layout.
- **Recommended Default:** Use WeasyPrint in the backend Docker container. HTML/CSS templating via Jinja2 allows identical bilingual design components to be shared with the web app, and Pango has mature Arabic HarfBuzz text shaping.
- **Status:** Recommended default adopted in `SYSTEM_ARCHITECTURE.md`.

### Q-TECH-03: Object Storage Provider for Local vs. Production
- **Context:** Exporters upload PDF certificates.
- **Ambiguity:** Local development needs S3-compatible storage without incurring cloud costs.
- **Recommended Default:** Use MinIO in local Docker Compose, and Cloudflare R2 or AWS S3 in production via standard `boto3` S3 client. S3 API compatibility ensures zero code changes between environments.
- **Status:** Recommended default adopted.

---

## 3. Product & Commercial Open Questions

### Q-PROD-01: Exporter Onboarding & Consignment Pricing Model
- **Context:** Exporters typically ship citrus in seasonal campaigns (November to April).
- **Ambiguity:** Will customers prefer a monthly SaaS subscription (e.g. \$200/month during season) or a per-consignment evaluation credit model (e.g. \$25 per export dossier evaluated)?
- **Recommended Default:** Defer all billing and payment code to Phase 3 per `phases/ROADMAP.md`. During Phase 2 Vertical Slice, provide free access to 5–10 test exporters to measure engagement and value before pricing.
- **Status:** Requires founder action (Customer interview findings).

### Q-PROD-02: Role of Human Expert in the Product Loop
- **Context:** `AGENTS.md` Rule 12 mandates human expert review before commercial reliance.
- **Ambiguity:** Is the human reviewer an in-house ReguLens specialist (Managed Service model) or the exporter's own internal compliance officer (SaaS Self-Serve model)?
- **Recommended Default:** Support both in the schema via the `Reviewer` role. For the Vertical Slice, the founder/expert reviewer acts as the platform reviewer; for enterprise exporters, their internal QA manager can be granted `Reviewer` permissions.
- **Status:** Recommended default adopted in `SECURITY_ARCHITECTURE.md`.

---

## 4. Legal & Regulatory Review Matrix (`Requires founder action`)

The following items strictly require qualified human legal or expert action before commercial launch:

| Item | Discipline Required | Specific Mandate | Priority |
|---|---|---|---|
| **Terms of Service & SaaS Agreement** | Qualified Commercial Lawyer (Egypt / UK) | Draft customer contract including complete liability limitation, indemnity against customs rejections, and explicit restatement of the verbatim disclaimer. | High (Before Phase 3) |
| **Privacy Policy & Cross-Border Data Transfer** | Qualified Privacy Attorney (GDPR / Egypt Law 151/2020) | Review `docs/PRIVACY_POLICY_DRAFT.md`; ensure compliance with Egyptian PDPC cross-border transfer requirements. | Medium (Before Phase 3) |
| **CEN/CENELEC Standards Copyright Notice** | Intellectual Property Lawyer | Review `docs/adr/0007-regulatory-data-licensing-and-storage.md` regarding metadata-only referencing of European standards. | Medium |
| **Agricultural Trade Expert Verification** | Agricultural Export Specialist (CAPQ or Exporter QA) | Review the 6 core regulatory requirements for fresh oranges and validate the 25 Golden Dataset test cases. | **CRITICAL** (Prerequisite for Gate 2 acceptance) |
| **Egyptian Business Registration & Tax Structure** | Egyptian Corporate Accountant / Lawyer | Determine commercial entity structure and tax status prior to selecting payment gateways. | High (Before Phase 3) |
