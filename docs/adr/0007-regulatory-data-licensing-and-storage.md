# ADR 0007: Regulatory Data Licensing, Source Archival, and Copyright Boundaries

## Status
Approved (Draft, requires qualified legal review)

## Date
2026-11-07

## Context
ReguLens ingests, indexes, displays, and quotes official legal acts, standards, and regulatory circulars.

Per `AGENTS.md`:
- **Rule 2:** Every regulatory claim shown to a user carries a citation to an official source record (URL, authority, reference, last-verified date).
- **Rule 9:** No claimed integration that does not exist. The source registry reports honest status.
- **Rule 14:** Terms of service, liability limits, privacy documents and data-licensing conclusions may be drafted but must be marked "draft, requires qualified legal review".

Different regulatory bodies operate under fundamentally different intellectual property and copyright regimes:
1. **European Union Official Legislation (EUR-Lex / Official Journal):** Governed by European Commission Decision 2011/833/EU on the reuse of Commission documents. Generally permits commercial and non-commercial reuse, reproduction, and translation provided the source is acknowledged and the original meaning is not distorted.
2. **Harmonised Standards (CEN / CENELEC / ISO):** Standards referenced under EU directives/regulations (such as EN 14682:2014 under GPSR) are subject to strict copyright owned by the standardization organizations (CEN/CENELEC). Despite the CJEU *Malamud* judgment (Case C-588/21 P) concerning public access to documents, standards bodies maintain that commercial databases cannot redistribute, scrape, or republish the complete proprietary text of European standards without licensing agreements.
3. **Egyptian Official Gazette & Government Circulars:** Public administrative acts published by the Egyptian Ministry of Agriculture and Land Reclamation (MALR), General Organization for Export and Import Control (GOEIC), or Central Administration of Plant Quarantine (CAPQ).
4. **International Standards & Guidelines (Codex Alimentarius, IPPC, EPPO):** UN/FAO/WHO public publications, subject to specific attribution and non-endorsement terms.

ReguLens must establish a strict data storage policy that respects copyright boundaries while satisfying Rule 2 (traceability via exact citations).

## Options Considered

### Option 1: Full-Text Mirroring of Everything
- Download and host full PDFs and full texts of all regulations, standards, and circulars in ReguLens storage and serve them directly.
- *Pros:* Offline availability.
- *Cons:* Severe intellectual property infringement liability, especially regarding CEN/CENELEC standards. Massive storage footprint. Legal exposure for redistributing copyrighted technical standards.

### Option 2: Link-Only Architecture
- Store only URLs and titles. Never store local snapshots, excerpts, or cached text.
- *Pros:* Zero copyright risk.
- *Cons:* Violates Rule 2 and Quality Gate criteria. URLs experience link rot, EUR-Lex anchors change, and mechanical citation validation (checking that a quoted span exists in an archived text) becomes impossible.

### Option 3: Tiered Archival Policy (Approved)
- Implement a 3-tier regulatory data storage architecture:
  - **Tier 1 (Official Public Legislation - EUR-Lex, Official Gazettes):** Store full official HTML/XML snapshots, compute SHA-256 integrity hashes, quote specific text spans, and deep-link to the official permalink (CELEX/ELI).
  - **Tier 2 (Harmonised & Technical Standards - CEN/CENELEC/ISO):** Store ONLY metadata: standard reference code (e.g. `EN 14682:2014`), official OJ publication citation (`OJ C 335, 09.10.2015`), publication date, title, scope summary from the official Commission summary list, and link to national standardization body stores (e.g. EOS, DIN, BSI). **NEVER store or redistribute the proprietary standard full text.**
  - **Tier 3 (Government Circulars & Guidance):** Store official reference number, issuing authority, issue date, summarized instructions, and direct link or archival copy where permitted by public domain rules.

## Decision
Adopt **Option 3 (Tiered Archival Policy)**:

### 1. Storage & Quoting Rules by Source Category

| Source Category | Permitted Local Storage | Quoting in UI / Reports | Permitted Links |
|---|---|---|---|
| **EU Regulations & Directives** (e.g. Reg 2016/2031, Reg 2019/1793) | Full text HTML/XML snapshot, SHA-256 hash, legal metadata. | Direct verbatim quotation of articles, recitals, and annexes with attribution. | Direct ELI/CELEX permalink to EUR-Lex. |
| **EU Commission Implementing Decisions** | Full text snapshot, metadata. | Verbatim quotation of articles and annex tables. | EUR-Lex permalink. |
| **Harmonised Standards** (e.g. EN 14682:2014) | Metadata ONLY (code, title, publication date, legal effect date, OJ notice reference). **NO full text.** | Reference to standard title and official presumption of safety under Art 7(1)(a) GPSR. **NO reproduction of technical text.** | Link to Commission Summary List and European Standards Organizations catalogs. |
| **Bilateral Trade Agreements** (e.g. EU-Egypt Association Agreement / Decision No 1/2024) | Full text snapshot of Official Journal publication. | Verbatim quotation of origin rules, list rules, and movement certificate forms. | EUR-Lex Official Journal permalink. |
| **Egyptian Official Authority Decisions** (GOEIC, CAPQ) | Decree number, issuing minister/head, date of publication, summarized operational requirements. | Short factual summary of official requirements; verbatim excerpt if official public text. | Official portal link or reference to Egyptian Official Gazette issue number. |

### 2. Attribution Notice Requirement
Every exported report or screen displaying EU legislative excerpts must include the standard European Commission attribution statement:
> "Contains European Union public sector information reproduced under Commission Decision 2011/833/EU. ReguLens is an independent compliance assistance service and is not endorsed by or affiliated with the European Union or any government authority."

### 3. Legal Review Prerequisite
Per `AGENTS.md` Rule 14, this policy is classified as:
> **Draft, requires qualified legal review.** A qualified intellectual property attorney must review these data licensing conclusions before any commercial release.

## Consequences
- **Positive:**
  - Complete legal protection against copyright claims from standards bodies (CEN/CENELEC).
  - Absolute mechanical traceability for EU public legislation.
  - Zero risk of link-rot breaking regulatory audits.
- **Negative / Trade-offs:**
  - Users seeking the exact engineering dimensions of cords/drawstrings in EN 14682 must be directed to purchase the standard from an official standard distributor; ReguLens cannot reproduce the proprietary diagrams.

## Reversal Path
If formal licensing agreements are established with CEN/CENELEC or national standards bodies in Phase 4, the standard storage tier can be upgraded to allow authorized licensed text previews.
