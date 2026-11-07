# Phase 0B: Product, Architecture and Technical Planning (documentation only)

Entry condition: Gate A approved in writing by the founder, with the scope decision recorded in `docs/MVP_RECOMMENDATION.md` or the founder's written reply.
Read first: `AGENTS.md`, `.agents/rules/*`, `phases/ROADMAP.md`, and the approved Phase 0A documents. Do the start-of-session check and report what you loaded.

Goal: define the product and a minimal, secure, testable architecture sized to the approved scope, and plan the Vertical Slice.

## Hard limits
No application code, no dependency installs, no database initialization, no deployment. Documents and decisions only. Size every document to the approved scope: no generic boilerplate, no document longer than needed. Do not design for sectors, markets or features the founder did not approve; note future extension points in a few lines at most.

## Steps
1. **Inspect the repository.** Framework, structure, existing code, dependencies, database, deployment config, visible security weaknesses. If empty, say so.
2. **Minimal baseline.** Start from: a web app, a backend API, PostgreSQL, private file storage. Do not add Redis, Celery or another queue, pgvector or semantic search, or separate services unless you show a real need for the approved scope. For each component beyond the baseline, give the written justification required by `QUALITY_GATES.md` section 5. Also list notable components you rejected and why. Verify technology versions per `AGENTS.md`.
3. **Decisions.** Write an ADR only for decisions that matter for this scope. Consider at least these topics and either decide with an ADR or state briefly why no ADR is needed:
   - Authentication and who enforces tenant isolation (database policies, application layer, or both), and how privileged credentials stay out of request paths.
   - Where business logic lives (prefer one place).
   - How applicability rules are represented (data or code) and how a human expert can review or correct a rule without redeploying.
   - The evidence and citation model: how a claim links to a requirement, a regulation version, a source snapshot and a quoted span, and what "citation validated" means mechanically.
   - How source licensing limits what may be stored, shown or only linked.
   - Retention and deletion versus audit-log integrity.
   - Product behavior when the AI provider is down, slow or returns invalid output.
   - Handling two sectors in one codebase, only if the approved scope includes both.
4. **Documents** (exact names, in `docs/`):
   - `PRODUCT_REQUIREMENTS.md`: persona, jobs-to-be-done, approved scope, user stories and measurable acceptance criteria for the Vertical Slice, explicit non-goals, success metrics.
   - `SYSTEM_ARCHITECTURE.md`: components, data flow, deployment approach, failure modes, an estimate of run costs for the slice (hosting, storage, AI provider usage) with assumptions labeled as estimates, and the component justifications.
   - `DATABASE_SCHEMA.md`: only the entities the Vertical Slice needs, with relationships, tenant ownership, indexes, how legal records are versioned, and the isolation approach. Mermaid ERD.
   - `SECURITY_ARCHITECTURE.md`: controls per layer (auth, authorization, data, files, AI, secrets, audit).
   - `THREAT_MODEL.md`: threats per component and abuse cases (cross-tenant access, IDOR, prompt injection through documents, malicious uploads, SSRF in connectors, AI cost abuse), mitigations, residual risk.
   - `REGULATORY_DATA_POLICY.md`: source authority tiers, verification workflow, lifecycle states, licensing rules, update cadence, what happens when a source is missing.
   - `TEST_STRATEGY.md`: test levels, security tests, and the quantitative criteria from `QUALITY_GATES.md` section 4, with PROPOSED thresholds and a PROPOSED golden-dataset size and rationale, plus the expert-review plan (who, what sample, how recorded).
   - `DATA_RETENTION_POLICY.md` and `PRIVACY_POLICY_DRAFT.md`: short drafts (data inventory, purposes, processors, retention, transfer considerations, applicable laws to be checked such as GDPR and Egyptian data protection requirements). Each starts with "Draft, requires qualified legal review".
   - `DEVELOPMENT_ROADMAP.md`: milestones and exit criteria inside the phase order of `phases/ROADMAP.md`, never reordering it.
   - `OPEN_QUESTIONS.md` and `adr/`.
   - Not in this phase: `API_SPECIFICATION.md` (written at the start of Phase 2).
5. **Legal and expert review plan.** List what needs a human lawyer (terms of service, liability limits, privacy notice, data and source licensing, billing and tax questions) and which regulatory content needs expert review, with the suggested order. These are `Requires founder action`. Do not claim they are legally approved.

## Gate B: end-of-phase report
Use the format in `QUALITY_GATES.md` section 1 and include: repository assessment; the architecture and each component justification; the ADR list with trade-offs; the ERD summary; the top security risks; the source integration plan (what is realistic for the slice and what is not); the Vertical Slice definition; milestones; PROPOSED quantitative thresholds awaiting approval; legal and expert review needs; open questions needing the founder's decision, each with your recommendation.

Then STOP. Do not start Phase 1. Wait for the founder's explicit written approval.
