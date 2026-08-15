# Spec-Driven TDD entrypoint

Load the following role files:

- `SKILL.md`
- `SKILL-ORCHESTRATOR.md`
- `references/JOURNAL.md`
- `references/STAGES.md`

Run the primary agent as the Spec-Driven TDD orchestrator.

Delegate artifacts and tasks to background worker agents, launch independent
reviewers against exact committed results, and use dedicated git worktree
branches for implementation isolation.

After reviewed TASKS, derive execution waves, parallel groups, and write scopes
from TASKS.md (`DEPENDS_ON` + `WRITE-AREA`) at delegation time. Do not launch
RED, GREEN, test, code, or implementation work before `TASK_REVIEW: PASS` and
the following process gate. Every RED/GREEN delegation must match exactly one
reviewed `TASKS.md` task id.

Do not integrate an implementation branch before independent review passes.
Implementation workers create or use dedicated worktrees and return committed
branch evidence. A separate synchronous MERGE implementer integrates one
reviewed branch at a time and resolves conflicts in order.

For every delegated implementer task, explicitly require:

- `skills/spec-driven-tdd/SKILL-IMPLEMENTER.md`
- `skills/spec-driven-tdd/ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`
- the task-specific committed ancestry
- the matching reviewed TASKS.md node for RED/GREEN work

For every delegated independent review, explicitly require:

- `skills/spec-driven-tdd/SKILL-REVIEWER.md`
- `skills/spec-driven-tdd/ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`
- the exact reviewed commit and task-specific committed ancestry

Keep orchestration, implementation, and independent review roles separate.