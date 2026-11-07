# Quality Gates

## 1. Gate protocol (every phase)
1. The agent finishes the phase deliverables and writes the end-of-phase report.
2. A review is performed against AGENTS.md and this file. It is independent if the environment allows; otherwise the report says it was a self-review.
3. The founder reads the report and the review, then approves in writing, requests changes, or stops.
4. Only explicit written approval opens the next phase.

End-of-phase report contents: work completed; files created or modified; evidence gathered; decisions made; tests performed and results; known limitations; risks; outstanding questions; recommended next phase. Give each deliverable exactly one status: Complete, Partially complete, Blocked, Requires founder decision, or Requires founder action.

## 2. Research gates (Phase 0A)
- Every statistic and factual claim has source, publication date and access date, with methodology and limitations where relevant.
- Incompatible trade classifications are never combined. Worldwide exports are never presented as EU exports.
- Facts, estimates, assumptions, interpretations and recommendations are labeled separately.
- Customer validation is claimed only from real interviews or other credible evidence. Without them the report states "not validated".
- A source is marked "verified" only if the agent opened it. API availability is claimed only from official documentation. Terms of use and licensing are recorded before any integration is proposed.

## 3. Human review gates
- **Expert review.** Before any requirement set is relied on commercially, a qualified human reviews a sample against official sources. The sample size, the reviewer's qualifications and the result are recorded in `docs/TEST_STRATEGY.md` and the end-of-phase report. Findings are never presented as expert-verified before this happens.
- **Legal review.** Terms of service, liability limits, privacy notices and data-licensing conclusions are drafts until a qualified lawyer reviews them. Gate reports list them as "draft, requires qualified legal review".

## 4. Quantitative acceptance criteria
Define these metrics in `docs/TEST_STRATEGY.md`, measured on an expert-verified golden dataset:
- Citation validity: share of cited claims whose citation resolves to a retrieved official source record.
- Citation support: share of cited claims whose quoted source text, checked by a human on a sample, actually supports the claim.
- Requirement extraction accuracy: precision and recall against the expert-verified set, plus the rate of missing requirements.
- Unsupported-claim rate: invented or unsupported requirements shown to users. Any occurrence is a defect under AGENTS.md rule 1.
- Source freshness: age of the last successful verification per source, and visibility of stale sources.

The agent proposes threshold values and the golden-dataset size with rationale, marked PROPOSED. Values become binding only after the founder approves them in writing. The agent never finalizes them itself.

## 5. Technology gate
Component justification is part of the architecture review. Each component beyond the minimal baseline (web app, backend API, PostgreSQL, private file storage) needs a written justification: the evidence of need, cost, operational burden and how it can be removed. Rejected components are listed with the reason.

## 6. Build gates (from the foundation phase onward)
- CI runs lint, type-check, unit, integration and security tests on every change.
- Tenant-isolation tests exist for every table and endpoint that holds customer data.
- Every endpoint has an authorization test for each role, including negative cases.
- No finding is shown without a citation; a test enforces this.
- Source-failure test: simulate a connector outage and assert a visible degraded state.
- Prompt-injection test set (documents containing instructions) must not alter behavior.
- Accessibility basics: keyboard navigation, contrast, RTL parity.
- Nothing is called complete because its interface exists. A feature is complete only when its behavior works and its tests pass.

## 7. Vertical Slice acceptance
The Vertical Slice (see `phases/ROADMAP.md`) is accepted only when all hold for the approved product and market:
1. A user can complete the journey end to end: create organization, add product, select market, receive requirements, review official sources, upload documents, see gaps, generate a PDF report.
2. Every requirement shown has a traceable official source with visible lifecycle state and verification date.
3. Document analysis reports findings with evidence and uncertainty and never labels a requirement "compliant".
4. The report carries the mandatory disclaimer and a version.
5. Tenant isolation is proven by tests.
6. A qualified human reviewed a sample of the requirements and the result is recorded.
7. The metrics in section 4 were measured against the founder-approved thresholds and the results are reported honestly, including failures.
