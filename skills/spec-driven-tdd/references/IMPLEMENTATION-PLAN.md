# IMPLEMENTATION-PLAN.md Reference

Runtime file:

```text
.sddtdd_skill/IMPLEMENTATION-PLAN.md
```

Create and review it after `TASKS.md` and before any RED, GREEN, test, or code
assignment.

## Rules

- One worker assignment handles exactly one `TASK_ID`.
- Independent tasks may run concurrently on separate OMP subagents.
- Independent reviewers may also run concurrently.
- GREEN for one task starts only after that task has `RED_REVIEW: PASS` and the following process gate.
- A dependent task waits for its declared dependency gate.
- Parallel writers must have non-overlapping `WRITE_SCOPE` values.
- Real OMP agent and job ids are recorded after `task()` returns; do not invent them in the plan.

## Simple four-task example

Tasks:

```text
T1: paddle movement; independent
T2: ball movement; independent
T3: brick removal; independent
T4: ball collision response; depends on T2 GREEN_REVIEW: PASS and its process gate
```

Initial execution:

```text
Agent 1 takes T1.
Agent 2 takes T2.
Agent 3 takes T3.
No agent takes T4 yet because T4 depends on T2.
```

Review and continuation:

```text
Reviewer 1 reviews T1 RED.
Reviewer 2 reviews T2 RED.
Reviewer 3 reviews T3 RED.
The three reviewers may run at the same time.

After each task has both RED_REVIEW: PASS and the following
ORCHESTRATOR_TASK_REVIEW: PASS, its worker may start that task's GREEN without
waiting for unrelated tasks.

Reviewer 1 reviews T1 GREEN.
Reviewer 2 reviews T2 GREEN.
Reviewer 3 reviews T3 GREEN.
The three GREEN reviewers may run at the same time.

After T2 receives GREEN_REVIEW: PASS and the following process gate,
Agent 2, or another free worker, takes T4.
```

Implementation plan:

```text
## PLAN-T1
TASK_ID: T1
DEPENDS_ON: --
DEPENDENCY_GATE: --
WAVE: 1
PARALLEL_GROUP: WAVE-1
WRITE_SCOPE: tests/paddle/**, src/paddle/**
RED_ASSIGNMENT: Agent-1
RED_COMMAND: npm test -- paddle
RED_REVIEW_ASSIGNMENT: Reviewer-1
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: Agent-1
GREEN_REVIEW_ASSIGNMENT: Reviewer-1
GREEN_REVIEW: REQUIRED
MERGE_ORDER: 1
POST_INTEGRATION_TESTS: npm test -- paddle
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT

## PLAN-T2
TASK_ID: T2
DEPENDS_ON: --
DEPENDENCY_GATE: --
WAVE: 1
PARALLEL_GROUP: WAVE-1
WRITE_SCOPE: tests/ball/**, src/ball/**
RED_ASSIGNMENT: Agent-2
RED_COMMAND: npm test -- ball
RED_REVIEW_ASSIGNMENT: Reviewer-2
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: Agent-2
GREEN_REVIEW_ASSIGNMENT: Reviewer-2
GREEN_REVIEW: REQUIRED
MERGE_ORDER: 2
POST_INTEGRATION_TESTS: npm test -- ball
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT

## PLAN-T3
TASK_ID: T3
DEPENDS_ON: --
DEPENDENCY_GATE: --
WAVE: 1
PARALLEL_GROUP: WAVE-1
WRITE_SCOPE: tests/bricks/**, src/bricks/**
RED_ASSIGNMENT: Agent-3
RED_COMMAND: npm test -- bricks
RED_REVIEW_ASSIGNMENT: Reviewer-3
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: Agent-3
GREEN_REVIEW_ASSIGNMENT: Reviewer-3
GREEN_REVIEW: REQUIRED
MERGE_ORDER: 3
POST_INTEGRATION_TESTS: npm test -- bricks
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT

## PLAN-T4
TASK_ID: T4
DEPENDS_ON: T2
DEPENDENCY_GATE: GREEN_REVIEW
WAVE: 2
PARALLEL_GROUP: AFTER-T2
WRITE_SCOPE: tests/collision/**, src/collision/**
RED_ASSIGNMENT: Agent-2-or-free-worker
RED_COMMAND: npm test -- collision
RED_REVIEW_ASSIGNMENT: Reviewer-4
RED_REVIEW: REQUIRED
GREEN_ASSIGNMENT: Agent-2-or-free-worker
GREEN_REVIEW_ASSIGNMENT: Reviewer-4
GREEN_REVIEW: REQUIRED
MERGE_ORDER: 4
POST_INTEGRATION_TESTS: npm test -- collision
STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT
```

Merges remain serial and follow `MERGE_ORDER`. Any change to dependencies,
assignment boundaries, parallel groups, write scopes, or merge order requires a
committed plan revision and another `IMPLEMENTATION_PLAN_REVIEW`.
