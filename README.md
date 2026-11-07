# ReguLens Agent Kit

Instruction files for building ReguLens phase by phase with an AI coding agent (for example Google Antigravity). Nothing here is application code.

## Layout
```
AGENTS.md                         Constitution and standing rules, loaded every session (short)
REGULENS_MASTER_PROMPT.md         Background and product reference (not the entry point)
.agents/rules/TEAM_WORKFLOW.md    Research loop, build loop, evidence labels, independence, human actions
.agents/rules/QUALITY_GATES.md    Gate protocol, human review gates, quantitative criteria, Vertical Slice acceptance
phases/ROADMAP.md                 The phase order (the only place it is defined)
phases/PHASE_0A.md                Market and scope validation (research only)
phases/PHASE_0B.md                Product, architecture and technical planning (documents only)
phases/PHASE_TEMPLATE.md          Template for Phase 1 and later, written after Gate B
docs/SPEC_MODULES.md              Original module-level requirements (reference)
```

## Phase order
Step 0 (test the tool) then Phase 0A then Gate A (you choose scope) then Phase 0B then Gate B then Phase 1 (minimal foundation) then Phase 2 (Vertical Slice) then expansion. Details in `phases/ROADMAP.md`.

## How to use
1. Copy the contents into the root of your ReguLens project.
2. Step 0: open a new agent session and ask "List exactly which instruction files you loaded." Confirm `AGENTS.md` and the rules appear. If not, tell the agent to read them explicitly at the start of every session. Check your tool's documentation rather than assuming.
3. Send: "Read AGENTS.md and .agents/rules/*, then execute phases/PHASE_0A.md."
4. While Phase 0A runs or after it finishes, do the founder actions it lists: 5 to 10 real exporter interviews, find a qualified expert reviewer, start legal consultation.
5. Review the Gate A report with a separate session or reviewer if you can. Decide scope in writing. Then run Phase 0B the same way.
6. After Gate B, write `phases/PHASE_1.md` and later files from `PHASE_TEMPLATE.md`, one at a time.

## Things only a human can do
Customer interviews, expert review of requirements, legal review, payment and business-registration decisions, and approval of the numeric quality thresholds. The agent prepares materials for these and must not simulate them.
