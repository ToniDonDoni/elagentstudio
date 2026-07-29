# OMP Spec-Driven TDD entrypoint

@./SKILL.md
@./SKILL-ORCHESTRATOR.md
@./references/JOURNAL.md
@./references/STAGES.md
@./references/IMPLEMENTATION-PLAN.md

Run the primary Oh My Pi agent as the Spec-Driven TDD orchestrator.

Use native OMP `task` subagents, `hub`, `agent://`, `history://`, asynchronous
job delivery, and dedicated git worktree branches.

After reviewed TASKS, create and independently review
`.sddtdd_skill/IMPLEMENTATION-PLAN.md` using the canonical implementation-plan
schema. Do not launch RED, GREEN, test, code, or implementation work before
`IMPLEMENTATION_PLAN_REVIEW: PASS` and the following process gate. Every
RED/GREEN delegation must match exactly one reviewed plan row and one `TASKS.md`
task id.

Do not integrate an implementation branch before independent review passes.
Implementation workers create or use dedicated worktrees and return committed
branch evidence. A separate synchronous MERGE implementer integrates one
reviewed branch at a time and resolves conflicts in reviewed plan order.

For every delegated implementer task, explicitly require:

- `skills/spec-driven-tdd/SKILL-IMPLEMENTER.md`
- `skills/spec-driven-tdd/ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`
- `skills/spec-driven-tdd/references/IMPLEMENTATION-PLAN.md` when planning or executing RED/GREEN work
- the task-specific committed ancestry
- the matching reviewed implementation-plan row for RED/GREEN work

For every delegated independent review, explicitly require:

- `skills/spec-driven-tdd/SKILL-REVIEWER.md`
- `skills/spec-driven-tdd/ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`
- `skills/spec-driven-tdd/references/IMPLEMENTATION-PLAN.md` for `IMPLEMENTATION_PLAN_REVIEW` and downstream review
- the exact reviewed commit and task-specific committed ancestry

OMP discovers project `WATCHDOG.md` separately for the advisor. Do not import
advisor policy into the primary-agent context.

Keep orchestration, implementation, independent review, and advisor watchdog
roles separate.
