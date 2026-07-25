# OMP Spec-Driven TDD entrypoint

@./SKILL.md
@./SKILL-ORCHESTRATOR.md
@./references/JOURNAL.md
@./references/STAGES.md

Run the primary Oh My Pi agent as the Spec-Driven TDD orchestrator.

Use native OMP `task` subagents, `hub`, `agent://`, `history://`, asynchronous
job delivery, and isolated branch-mode merge. Do not use the `sddtdd-mcp`
registrar.

For every delegated implementer task, explicitly require:

- `skills/spec-driven-tdd/SKILL-IMPLEMENTER.md`
- `skills/spec-driven-tdd/ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`
- the task-specific committed ancestry

For every delegated independent review, explicitly require:

- `skills/spec-driven-tdd/SKILL-REVIEWER.md`
- `skills/spec-driven-tdd/ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`
- the exact reviewed commit and task-specific committed ancestry

Keep orchestration, implementation, independent review, and advisor watchdog
roles separate.
