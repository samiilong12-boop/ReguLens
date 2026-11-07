# ReguLens Phase Roadmap (founder-approved order)

This file is the only place that defines phase order. `docs/DEVELOPMENT_ROADMAP.md` adds milestones and exit details inside this order and never reorders phases. Each gate needs the founder's explicit written approval.

| Step | What | Output | Gate |
|---|---|---|---|
| Step 0 | Founder tests that Antigravity actually loads `AGENTS.md` and `.agents/rules/` (ask it to list what it loaded; if it did not load them, instruct it to read them explicitly each session) | Confirmation | Founder |
| Phase 0A | Market and scope validation: research, regulatory source verification, product and market comparison, interview plan | 6 documents + decision report | Gate A: founder chooses scope |
| Founder actions | 5 to 10 real exporter interviews across agriculture and apparel; identify a qualified expert reviewer; start legal consultation | Real evidence | Feeds Gate A and B |
| Phase 0B | Product definition, minimal architecture, security, privacy drafts, test strategy, Vertical Slice definition | Documents + ADRs where needed | Gate B: founder approves plan and thresholds |
| Phase 1 | Minimal technical foundation: only what the slice needs (auth, organizations and roles, tenant isolation proven by tests, private file storage, audit basics, CI) | Working foundation + tests | Gate 1 |
| Phase 2 | **Vertical Slice** (below) | One complete, honest user journey | Gate 2: founder, with expert review results |
| Phase 3 and later | Expansion, ordered by evidence from the slice and the founder: more products and markets, the second sector if not yet covered, regulatory monitoring, subscriptions and billing, admin dashboard, hardening and launch preparation | Per-phase files | One gate per phase |

Phase 1 and later phase files are written after Gate B from `phases/PHASE_TEMPLATE.md`, because they depend on the approved architecture. `API_SPECIFICATION.md` is written at the start of Phase 2.

## The Vertical Slice (Phase 2)
One product and one market from the approved scope. The slice must prove the core claim: ReguLens can take a real product, derive its requirements from official sources, check its documents, and show gaps reliably.

Journey: create organization, add product, select destination market and confirm product characteristics, retrieve requirements supported by official sources, review each source and its verification date and lifecycle state, upload documents, run document and gap analysis, review missing information, generate a versioned PDF report.

Includes only what the journey needs. Excludes: monitoring, billing, admin dashboard, additional products or markets, and any module not on the journey.

Acceptance: `QUALITY_GATES.md` section 7. The slice is not accepted without a recorded expert review of a requirement sample and honest reporting of the measured metrics.

## Expansion principles (Phase 3 and later)
Add breadth only after the slice passes. Each expansion phase needs a phase file, measurable exit criteria and its own gate. Billing and pricing are not finalized without market evidence and a verified payment-provider option for the business structure and location. Do not assume any specific provider is available.
