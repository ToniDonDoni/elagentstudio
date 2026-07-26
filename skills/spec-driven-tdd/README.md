# Spec-Driven TDD for Oh My Pi

## Add to a project

In the project-root `AGENTS.md`:

```markdown
@skills/spec-driven-tdd/AGENTS.md
```

In the project-root `WATCHDOG.md` or `.omp/WATCHDOG.md`:

```markdown
@skills/spec-driven-tdd/WATCHDOG.md
```

OMP loads `AGENTS.md` into the primary-agent context and discovers
`WATCHDOG.md` separately for the advisor.

Enable asynchronous subagents and the advisor in OMP. Implementation workers
must use dedicated git worktree branches. Do not automatically integrate worker
results before independent review passes. Every integration commit must then
pass a separate mandatory `MERGE_REVIEW` before downstream use.

## Files

- `SKILL.md` — shared workflow policy.
- `SKILL-ORCHESTRATOR.md` — primary-agent dispatcher and process gates.
- `SKILL-IMPLEMENTER.md` — artifact, RED/GREEN, correction, and merge work.
- `SKILL-REVIEWER.md` — independent committed-state review.
- `SKILL-WATCHDOG.md` — advisor process supervision.
- `AGENTS.md` — primary-agent entrypoint.
- `WATCHDOG.md` — advisor entrypoint.
- `tests/verify_evidence.py` — CI verifier for required journal/runtime evidence.
- `tests/test_verify_evidence.py` — positive and negative verifier tests.

## Example

```text
Use the Spec-Driven TDD workflow to add a health-check endpoint.

Requirements:
- GET /health returns HTTP 200 and JSON {"status":"ok"}.
- Add an end-to-end test that proves the running application behavior.
- Keep unrelated APIs unchanged.

Run as the orchestrator. Create and review SPEC, ARCHITECTURE, and TASKS;
perform reviewed RED/GREEN in a dedicated worktree branch; independently review
the worker commit before merging; independently review the exact integration
commit; then run post-integration regression and final review.
```
