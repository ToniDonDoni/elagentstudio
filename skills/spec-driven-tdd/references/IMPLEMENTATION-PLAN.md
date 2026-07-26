# IMPLEMENTATION-PLAN.md Specification

The runtime artifact path is exactly:

```text
.sddtdd_skill/IMPLEMENTATION-PLAN.md
```

It is created after reviewed `TASKS.md` and independently reviewed before any
RED, GREEN, test, code, or implementation delegation.

## Canonical task block

Create exactly one block for every reviewed `TASKS.md` node that requires
automatically testable work:

```text
## PLAN-<TASK_ID>
TASK_ID: <exactly one TASKS.md task id>
DEPENDS_ON: <task ids or -->
WAVE: <positive integer>
PARALLEL_GROUP: <group name or SERIAL>
WRITE_SCOPE: <non-overlapping paths>
RED_ASSIGNMENT: <logical implementer assignment>
RED_COMMAND: <highest practical proving command>
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: <logical implementer assignment>
GREEN_REVIEW: REQUIRED
MERGE_ORDER: <positive integer>
POST_INTEGRATION_TESTS: <commands>
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT
```

`TASK_ID` must contain one id only. Commas, lists, ranges, multiple ids, or
phrases such as `all tasks` are forbidden.

Logical assignment names describe intended roles or lanes. Do not invent OMP
agent ids or job ids before `task()` returns them. Actual runtime ids belong in
`.sddtdd_skill/orchestrator.log`.

## Ordering rules

For each task block:

```text
RED assignment
→ RED_REVIEW: PASS
→ ORCHESTRATOR_TASK_REVIEW: PASS
→ GREEN assignment
→ GREEN_REVIEW: PASS
→ ORCHESTRATOR_TASK_REVIEW: PASS
→ serialized MERGE
→ MERGE_REVIEW: PASS
→ ORCHESTRATOR_TASK_REVIEW: PASS
```

A later wave may begin only when all declared dependencies have reached the
required reviewed gate. Parallel blocks must have non-overlapping `WRITE_SCOPE`
values and no unresolved dependency edge.

## Review and change control

`IMPLEMENTATION_PLAN_REVIEW` must fail when:

- any reviewed task requiring testable work has no block;
- one block or assignment names multiple task ids;
- RED, review, GREEN, review, or merge gates are omitted or reordered;
- parallel scopes overlap or dependencies are ignored;
- merge order is absent or unsafe;
- stop/reroute conditions are missing;
- the plan starts or performs implementation work while being authored.

Any runtime change to assignment boundaries, waves, dependencies, parallel
groups, write scopes, commands, or merge order requires a committed plan revision,
a new `IMPLEMENTATION_PLAN_REVIEW`, and a new process gate before affected work
continues.
