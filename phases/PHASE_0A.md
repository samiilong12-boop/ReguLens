# Phase 0A: Market and Scope Validation (research only)

Read first: `AGENTS.md`, `.agents/rules/TEAM_WORKFLOW.md`, `.agents/rules/QUALITY_GATES.md`, `phases/ROADMAP.md`. Do the start-of-session check in `AGENTS.md` and report what you loaded.

Goal: give the founder enough real evidence to decide the first-release scope (sector or sectors, products, EU destination markets, first customer profile), or to decide not to proceed.

## Hard limits
No application code. No dependency installs. No database. No deployment. No architecture documents or ADRs (that is Phase 0B). Keep every document as short as the evidence allows; do not pad. Only the six documents below are required.

## Context
- Origin: Egypt. Destination: European Union, evaluated country by country, not as one identical market. Distinguish EU-wide rules, national implementation, destination-country authorities, product-specific rules and import procedures.
- Industry A, agriculture and food: fresh Egyptian oranges; frozen Egyptian strawberries.
- Industry B, clothing and textiles: ready-made garments; fabrics and textiles. Do not assume all textile products share the same obligations (consider finished garments, fabrics, children's clothing).
- Do not assume every requirement applies to every product. Applicability depends on product characteristics, processing status, intended use and destination.
- US, UK, GCC and other markets are future opportunities only. Spend at most one short paragraph on them.

## Work packages

### 1. Market research
Egyptian agricultural and textile/clothing exports to the EU: trends, destination countries, product categories, exporter profiles, industry structure, regulatory complexity, current compliance workflows, operational problems, alternatives. Prefer official and credible sources (for example UN Comtrade, ITC Trade Map, Eurostat, European Commission, Access2Markets, Egyptian government bodies and export councils, industry associations). Record source, publication date, access date, methodology and limitations. Verify that you can actually open each source; say which ones you could not.

### 2. Customer research (Requires founder action)
The agent cannot interview anyone. Deliver:
- A target customer and user map (manufacturers, exporters, food processors, export managers, QA managers, regulatory affairs staff, consultants, documentation teams).
- An interview guide with at least 10 targeted questions covering: how requirements are identified today, who does it, time spent, hard-to-get documents, where mistakes happen, causes of delay, rejection and cost, tools used, and whether the company would pay for a dedicated solution.
- A plan for 5 to 10 real interviews across both sectors, a recording template, and a synthesis template.
- A short list of the evidence the founder should collect, such as shipment rejections or delays and the documents most often missing.

State clearly: the market is NOT validated until real interview evidence exists. When the founder supplies interview notes, record them faithfully and separate what customers said from your interpretation. Never invent interview results, quotes, customer counts or willingness to pay.

### 3. Competitor research
Verify before including. Candidates to check for relevance (do not assume they compete in this niche): RegASK, Assent, Sphera, SAP Global Trade Services, Adherent, regulatory consultants, export documentation providers, and manual research on government websites. Compare target customers, industries, regulatory coverage, document handling, AI features, monitoring, source traceability, geographic coverage, integrations, public pricing, weaknesses and gaps. If prices are not public, write "unavailable". Propose a realistic differentiation, labeled as a recommendation.

### 4. Regulatory source verification
For each initial product-destination combination, identify authoritative sources. Candidates: EUR-Lex, European Commission portals including food safety, Access2Markets, EFSA, RASFF, TRACES where applicable, NANDO where applicable, ECHA, relevant national authorities in the destination countries, and Egyptian authorities and export councils for origin-side documents.
For every source record: name, responsible authority, official URL, jurisdiction, relevant product categories, what information it provides, whether an API, feed or downloadable dataset exists (confirmed from official documentation only), access restrictions, terms of use and licensing, update frequency if known, integration feasibility, and last verification date.
Rules: no unauthorized scraping or violation of terms; no reproduction of paid standards such as ISO texts; never claim an API exists without confirming it in official documentation. Output uses the status vocabulary Integrated / Partial / Manual only / Not supported, with "feasible after verification" noted where applicable. Nothing is "Integrated" in Phase 0A.

### 5. Product comparison
Compare the four products on: export relevance, EU market opportunity, regulatory complexity, regulatory data availability, document requirements, customer pain intensity, competitive intensity, MVP feasibility, potential willingness to pay (mark "unknown" without evidence), and availability of pilot customers (mark "unknown" without evidence). Use a transparent scoring method, show the inputs, give a confidence level per conclusion, and do not let scores replace evidence.

### 6. Human expert identification (Requires founder action)
Propose the profile of the qualified human (export, customs or regulatory-compliance expert) who will review requirement samples, what the review would involve, and a rough sample outline. Do not invent named experts.

## Deliverables (in `docs/`, exactly these names)
1. `MARKET_RESEARCH.md`
2. `CUSTOMER_RESEARCH.md` (customer map, interview guide, interview plan, templates, and a section for recorded interview results, empty until the founder provides them)
3. `COMPETITOR_ANALYSIS.md`
4. `REGULATORY_SOURCES.md`
5. `PRODUCT_COMPARISON.md`
6. `MVP_RECOMMENDATION.md` (recommendation, the risks that matter, unresolved issues, what the founder must do, and the decision options below)

## Gate A: founder decision report
Finish with a concise report in the format of `QUALITY_GATES.md` section 1, and present these decision options with your recommendation and confidence:
- One agricultural product and one textile product as the starting pair.
- One sector only, if the evidence favors it.
- Not proceeding yet, if validation is insufficient.
Also list the destination EU markets and the first customer profile you recommend, and which items remain unvalidated.

Then STOP. Do not start Phase 0B. Wait for the founder's explicit written approval.
