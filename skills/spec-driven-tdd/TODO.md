# Spec-Driven TDD TODO

These are observed process risks for the OMP-native workflow. This file records
observations; normative requirements live in the skill and role policies.

## 1. Event-driven review

The orchestrator must launch a reviewer as soon as one implementer result is
ready instead of waiting for a whole wave or batch.

## 2. No process shortcuts

Cost or convenience is not permission to skip independent review, committed
evidence, worktree isolation, or post-integration tests.

## 3. Dispatcher-only orchestrator

After `FAIL`, the orchestrator delegates correction to an implementer. After
`NEEDS_CLARIFICATION`, it asks the user and pauses affected work. After
`BLOCKED`, it records and surfaces the blocker. It never edits the result itself.

## 4. Dedicated implementation worktrees

Parallel implementers must use separate worktrees and branches with safe write
scopes. They must not write directly to the integration branch.

## 5. Review before merge

Implementation commits must remain unintegrated until independent review PASS.
A synchronous MERGE implementer then integrates one reviewed result at a time.

## 6. Conflict and post-integration evidence

Conflict resolution belongs to the MERGE implementer. Required tests must run
against the final integrated commit, not only inside the worker worktree.

## 7. Bounded execution

Potentially long tests, builds, application runs, and end-to-end checks need
explicit timeouts and targeted output capture.

## 8. Runtime audit quality

Every delegation/check should preserve actual OMP agent/job ids, exact prompts,
branch, commit, output/transcript references, verdict, and clean-state evidence.
The handoff/check logs must remain valid JSONL.

## 9. Scope changes

New user product requirements are appended to `SPEC-DRAFT.md` under `ADDITION:`,
journaled, committed, and routed through replanning and review from the earliest
affected stage.

## 10. Skill development hygiene

Edit the version-controlled source skill and install/sync it deliberately. Do
not mutate installed user-level skill copies during project execution.

## 11. Watchdog enforcement gap

Observed failure:

- the primary agent skipped reviewed RED and collapsed multiple reviewed task
  nodes into one monolithic subagent assignment;
- the watchdog recognized the violation in private reasoning but repeatedly
  selected unavailable `bash`;
- OMP quarantined those advisor turns, the model did not recover with the
  granted `read`/`grep`/`glob` tools, and no `advise` call reached the primary;
- the invalid workflow continued.

Possible root cause: the advisor model preferred shell inspection, while the
default advisor grant excluded `bash`. It then failed to handle the unavailable
tool error and never delivered its already-detected blocker.

Possible workaround: install the supplied project-root `WATCHDOG.yml`, which
grants `bash` alongside `read`, `grep`, and `glob`. Its instructions restrict
shell use to read-only inspection and require immediate `blocker` advice for
GREEN without reviewed RED or for coalescing multiple `TASKS.md` task ids into
one assignment.

This is only a workaround. A stronger fix should make the advisor recover from
tool denial, use granted tools, and ensure a valid `advise` call is not lost
because another tool call in the same turn is unavailable.
