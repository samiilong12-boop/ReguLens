# Team Workflow

Do not merely "act as a team". Use explicit roles with handoffs and recorded outputs. Two loops exist: one for research work (Phase 0A) and one for build work (from Phase 0B onward, where it applies to design and later to code).

## Evidence labels (research and design documents)
Mark every substantive statement as one of: Verified fact (source, publication date, access date), Estimate (method stated), Assumption, Interpretation, Recommendation, or Could not verify. Do not mix them. If reliable data is unavailable, say so. Never invent TAM, SAM, SOM, revenue, customer counts, willingness-to-pay or competitor prices.

## Research loop (Phase 0A)
| Step | Role | Output |
|---|---|---|
| 1 | Researcher | Findings with source, publication date, access date, methodology, limitations |
| 2 | Source Verifier | Confirms each cited source was actually opened and says what is claimed; flags dead, paywalled or unreadable sources |
| 3 | Skeptical Reviewer | Challenges conclusions, separates fact from interpretation, assigns confidence levels |
| 4 | Product Lead | Turns findings into a recommendation and lists decisions the founder must make |

## Build loop (design and implementation work)
| Step | Role | Output |
|---|---|---|
| 1 | Product Lead | User story, acceptance criteria, explicit out-of-scope |
| 2 | Architect | Design note or ADR (only if the decision needs one), interfaces, data-model changes |
| 3 | Security Engineer | Threat check: abuse cases, data exposure, authorization, required controls |
| 4 | Engineers | Implementation behind the agreed interfaces |
| 5 | QA Engineer | Tests alongside the code: unit, integration, security, regression |
| 6 | Privacy Specialist | Data touched, retention, logging (when personal or customer data is involved) |
| 7 | Adversarial Reviewer | Checks against AGENTS.md, lists defects, blocks completion if any rule is broken |

## Independence
Verification and review steps (Source Verifier, Skeptical Reviewer, Security Engineer, QA, Adversarial Reviewer) should run in a separate session or agent that has not seen the author's reasoning. Do not claim independent review unless the environment actually provided it. If it did not, label the review "self-review, not independent" so the founder can arrange an external one.

## Human expertise and founder actions
Some work only a human can do: customer interviews, expert review of requirements, legal review, payment and business registration decisions. Do not simulate them. Mark the item "Requires founder action", prepare everything that helps the human do it (question lists, review samples, templates), and record the human's real results when the founder provides them.

## Definition of Done
Acceptance criteria met, tests pass (where code exists), evidence labels present, security check recorded, docs updated, no AGENTS.md rule violated.
