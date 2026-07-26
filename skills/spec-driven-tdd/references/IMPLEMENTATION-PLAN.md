# IMPLEMENTATION-PLAN.md Specification

The runtime artifact path is exactly:

```text
.sddtdd_skill/IMPLEMENTATION-PLAN.md
```

It is created after reviewed `TASKS.md` and independently reviewed before any
RED, GREEN, test, code, or implementation delegation.

## Parallel execution

Independent tasks may be executed concurrently by separate OMP subagents.
Independent RED assignments may run in parallel. After each task's own
`RED_REVIEW: PASS` and process gate, its GREEN assignment may run independently
of unrelated tasks. Read-only RED and GREEN reviewers may also run in parallel
against their exact assigned commits.

Parallel execution is legal only when declared dependencies are satisfied and
write scopes do not overlap. Parallelism never permits one assignment to contain
multiple `TASKS.md` task ids or permits GREEN to begin before that task's own
reviewed RED gate.

## Canonical task block

Create exactly one block for every reviewed `TASKS.md` node that requires
automatically testable work:

```text
## PLAN-<TASK_ID>
TASK_ID: <exactly one TASKS.md task id>
DEPENDS_ON: <task ids or -->
DEPENDENCY_GATE: <required reviewed gate or -->
WAVE: <positive integer>
PARALLEL_GROUP: <group name or SERIAL>
WRITE_SCOPE: <non-overlapping paths>
RED_ASSIGNMENT: <logical implementer assignment>
RED_COMMAND: <highest practical proving command>
RED_REVIEW_ASSIGNMENT: <logical read-only reviewer assignment>
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: <logical implementer assignment>
GREEN_REVIEW_ASSIGNMENT: <logical read-only reviewer assignment>
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

## Example with parallel workers and reviewers

This example has four tasks. `T010`, `T020`, and `T030` are independent and may
run concurrently. `T040` depends on reviewed GREEN evidence from `T020` and
therefore belongs to the next wave.

```text
# Implementation Plan

## PLAN-T010
TASK_ID: T010
DEPENDS_ON: --
DEPENDENCY_GATE: --
WAVE: 1
PARALLEL_GROUP: WAVE-1-INDEPENDENT
WRITE_SCOPE: tests/paddle/**, src/paddle/**
RED_ASSIGNMENT: red-worker-T010
RED_COMMAND: npm test -- paddle
RED_REVIEW_ASSIGNMENT: red-reviewer-T010
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: green-worker-T010
GREEN_REVIEW_ASSIGNMENT: green-reviewer-T010
GREEN_REVIEW: REQUIRED
MERGE_ORDER: 1
POST_INTEGRATION_TESTS: npm test -- paddle
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT

## PLAN-T020
TASK_ID: T020
DEPENDS_ON: --
DEPENDENCY_GATE: --
WAVE: 1
PARALLEL_GROUP: WAVE-1-INDEPENDENT
WRITE_SCOPE: tests/ball/**, src/ball/**
RED_ASSIGNMENT: red-worker-T020
RED_COMMAND: npm test -- ball
RED_REVIEW_ASSIGNMENT: red-reviewer-T020
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: green-worker-T020
GREEN_REVIEW_ASSIGNMENT: green-reviewer-T020
GREEN_REVIEW: REQUIRED
MERGE_ORDER: 2
POST_INTEGRATION_TESTS: npm test -- ball
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT

## PLAN-T030
TASK_ID: T030
DEPENDS_ON: --
DEPENDENCY_GATE: --
WAVE: 1
PARALLEL_GROUP: WAVE-1-INDEPENDENT
WRITE_SCOPE: tests/bricks/**, src/bricks/**
RED_ASSIGNMENT: red-worker-T030
RED_COMMAND: npm test -- bricks
RED_REVIEW_ASSIGNMENT: red-reviewer-T030
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: green-worker-T030
GREEN_REVIEW_ASSIGNMENT: green-reviewer-T030
GREEN_REVIEW: REQUIRED
MERGE_ORDER: 3
POST_INTEGRATION_TESTS: npm test -- bricks
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT

## PLAN-T040
TASK_ID: T040
DEPENDS_ON: T020
DEPENDENCY_GATE: GREEN_REVIEW
WAVE: 2
PARALLEL_GROUP: WAVE-2-AFTER-T020
WRITE_SCOPE: tests/collision/**, src/collision/**
RED_ASSIGNMENT: red-worker-T040
RED_COMMAND: npm test -- collision
RED_REVIEW_ASSIGNMENT: red-reviewer-T040
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: green-worker-T040
GREEN_REVIEW_ASSIGNMENT: green-reviewer-T040
GREEN_REVIEW: REQUIRED
MERGE_ORDER: 4
POST_INTEGRATION_TESTS: npm test -- collision
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT
```

The orchestrator executes this example as follows:

1. Launch `red-worker-T010`, `red-worker-T020`, and `red-worker-T030` concurrently.
2. As each RED worker returns, immediately launch its matching read-only RED reviewer. These reviewers may run concurrently.
3. After an individual task receives `RED_REVIEW: PASS` and the following process gate, launch that task's GREEN worker without waiting for unrelated tasks.
4. Launch matching read-only GREEN reviewers as individual GREEN commits arrive. These reviewers may run concurrently.
5. Do not launch `red-worker-T040` until `T020` has `GREEN_REVIEW: PASS` and the following process gate.
6. Integrate reviewed GREEN results serially according to `MERGE_ORDER`, with mandatory review of every exact integration commit.

If `T040` needs the integrated form of `T020` rather than only its reviewed GREEN
commit, set `DEPENDENCY_GATE: MERGE_REVIEW` and wait for the following process
gate instead.

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
specified `DEPENDENCY_GATE` and its following process gate. Parallel blocks must
have non-overlapping `WRITE_SCOPE` values and no unresolved dependency edge.

## Review and change control

`IMPLEMENTATION_PLAN_REVIEW` must fail when:

- any reviewed task requiring testable work has no block;
- one block or assignment names multiple task ids;
- RED, review, GREEN, review, or merge gates are omitted or reordered;
- parallel scopes overlap or dependencies are ignored;
- merge order is absent or unsafe;
- stop/reroute conditions are missing;
- the plan starts or performs implementation work while being authored.

Any runtime change to assignment boundaries, waves, dependencies, dependency
gates, parallel groups, write scopes, commands, reviewer assignments, or merge
order requires a committed plan revision, a new `IMPLEMENTATION_PLAN_REVIEW`,
and a new process gate before affected work continues.
