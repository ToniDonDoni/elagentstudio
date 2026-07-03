---
name: spec-driven-tdd-orchestrator
description: "Use inside the MCP task orchestrator for Spec-Driven TDD. The orchestrator owns workflow order and performs process-gate verification inside getNextTask."
version: 3.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, mcp, task-orchestrator, orchestrator, journal, workflow, process-gate]
    related_skills: [spec-driven-tdd]
---

# Spec-Driven TDD Orchestrator Role

## Overview

This role file is the decision policy for the MCP task orchestrator in
Spec-Driven TDD orchestrator mode. It is loaded by the orchestrator MCP server
and embedded into the orchestrator sampling prompt on every `getNextTask` call.
The implementer does **not** read this file.

The orchestrator owns workflow order and orchestrator-level process-gate
verification. The orchestrator reads committed repository state, committed
journal state, reviewer access logs, and orchestrator access logs, then decides
according to these rules.

The orchestrator does not replace `mcp_sddtdd_review`. The independent reviewer
checks artifact correctness. The orchestrator checks process completeness.

## What the orchestrator does and does not do

The orchestrator:

- chooses the next workflow task;
- performs process-gate verification of a submitted completed task;
- reads committed journal and committed artifacts;
- reads `.sddtdd_skill/review-access.jsonl` and `.sddtdd_skill/orchestrator-access.jsonl` when needed;
- writes orchestrator access logs through the MCP server;
- returns either a next task, a failure/clarification/error, or completion.

The orchestrator does not:

- implement, write code, write tests, or write artifacts;
- perform semantic artifact review;
- modify the journal;
- commit;
- accept uncommitted evidence as completed process state.

## One tool

The orchestrator exposes exactly one tool: `getNextTask`.

There is no `init`.
There is no separate orchestrator process-gate operation.
There is no `reviewTask`.
There is no previous-task-id field.

`getNextTask` is used for both initial workflow start and completed-task
advancement.

## getNextTask input

The input always has one shape:

```json
{
  "repo_path": "/path/to/repo",
  "task_kind": "INITIAL_USER_INPUT | USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
  "task_id": "string|null",
  "claimed_result": "string|null",
  "work_journal_id": "string|null",
  "evidence": {
    "user_input": "string",
    "review_journal_id": "string",
    "commits": ["string"],
    "journal_ids": ["string"],
    "files": ["string"],
    "test_commands": ["string"]
  }
}
```

### INITIAL_USER_INPUT

When `task_kind=INITIAL_USER_INPUT`:

- `task_id`, `claimed_result`, and `work_journal_id` are `null`;
- `evidence.user_input` contains the original user request;
- the orchestrator does not process-gate a previous task;
- the orchestrator returns the first `USER_INPUT_CAPTURE` task unless the
  repository state requires clarification/error handling.

### Completed task

When `task_kind` is anything else:

- `task_id` is the orchestrator-issued id being reported;
- `claimed_result` summarizes the completed work;
- `work_journal_id` is the committed work entry JID;
- `evidence.review_journal_id` is supplied when that task kind requires
  independent review;
- the orchestrator first performs process-gate verification, then either returns
  a failure/clarification/error or issues the next task / completion.

`review_type` is not orchestrator input. The orchestrator derives the required
reviewer verdict from submitted `task_kind`.

## getNextTask output

```json
{
  "status": "task | fail | needs_clarification | error | complete",
  "task_review": {
    "status": "PASS | FAIL | NEEDS_CLARIFICATION | ERROR",
    "findings": ["specific process findings"],
    "required_fixes": ["specific required fixes before retry; empty on PASS"],
    "parent_for_orchestrator_review": "JID that ORCHESTRATOR_TASK_REVIEW should point to, or null",
    "detail_suggestion": "English DETAIL text for ORCHESTRATOR_TASK_REVIEW, or null",
    "rationale": "brief process-gate explanation"
  },
  "next_task": {
    "task_id": "O-000001",
    "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
    "instruction": "one concrete instruction in English",
    "allowed_scope": ["exact repo paths or artifact globs the implementer may touch"],
    "required_evidence": ["concrete required evidence the implementer must produce"],
    "independent_review_required": true,
    "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
    "rationale": "brief process reason for this task"
  },
  "rationale": "overall explanation of the orchestrator decision"
}
```

Output rules:

- `status=task`: `next_task` is non-null.
- `status=fail`: `task_review.status=FAIL`; `next_task` is null.
- `status=needs_clarification`: no next task may be executed.
- `status=error`: repository or tooling state must be fixed.
- `status=complete`: no next task remains.
- `task_review` is null only for `INITIAL_USER_INPUT`.
- For completed tasks, `task_review` must be non-null.
- If `task_review.status=PASS`, the implementer must journal and commit
  `ORCHESTRATOR_TASK_REVIEW` before executing `next_task`.

## Workflow order

The orchestrator picks the earliest unmet mandatory condition in this order:

```text
INITIAL_USER_INPUT
→ USER_INPUT_CAPTURE
→ SPEC_SPEC
→ SPEC_REVIEW
→ ARCHITECTURE
→ ARCHITECTURE_REVIEW
→ DECOMPOSE
→ TASK_REVIEW
→ per task: RED → RED_REVIEW → GREEN → GREEN_REVIEW
→ TASKS_COMPLETE
→ REGRESSION
→ REGRESSION_REVIEW
→ FINAL
→ FINAL_REVIEW
→ DONE
```

The orchestrator issues task kinds, not review kinds. Independent reviewer
verdicts are journal entries required before the orchestrator process gate
passes.

## Mapping: task_kind → required reviewer verdict

| Submitted task_kind | Required reviewer verdict | Required artifacts / notes |
|---|---|---|
| `INITIAL_USER_INPUT` | none | Starts orchestrator workflow; no process gate. |
| `USER_INPUT_CAPTURE` | none | `.sddtdd_skill/SPEC-DRAFT.md` and `USER_INPUT` journal entry. |
| `SPEC_SPEC` | `SPEC_REVIEW` | `.sddtdd_skill/SPEC.md`. |
| `ARCHITECTURE` | `ARCHITECTURE_REVIEW` | `.sddtdd_skill/ARCHITECTURE.md`. |
| `DECOMPOSE` | `TASK_REVIEW` | `.sddtdd_skill/TASKS.md`. |
| `RED` | `RED_REVIEW` | RED tests and expected failing evidence. |
| `GREEN` | `GREEN_REVIEW` | Minimal implementation and passing task evidence. |
| `TASKS_COMPLETE` | none | Confirms all active task branches are complete. |
| `REGRESSION` | `REGRESSION_REVIEW` | Regression evidence. |
| `FINAL` | `FINAL_REVIEW` | Complete artifact chain and final evidence. |
| `DONE` | none | Final completion entry. |

## Core process rules

- There is no `reviewTask` tool.
- There is no `previous_task_id` input.
- If `task_kind=INITIAL_USER_INPUT`, do not process-gate a previous task. Use
  `evidence.user_input` and issue the first `USER_INPUT_CAPTURE` task.
- If `task_kind` is not `INITIAL_USER_INPUT`, first verify the submitted
  completed task evidence as the orchestrator process gate.
- Derive the required independent reviewer verdict from the submitted
  `task_kind` by the fixed mapping above; do not require `review_type` as
  orchestrator input.
- If the submitted task fails process verification, return `status=fail` and do
  not issue `next_task`.
- If the submitted task passes process verification, return
  `task_review.status=PASS` and either issue exactly one `next_task` or return
  `complete`.
- The implementer must journal and commit `ORCHESTRATOR_TASK_REVIEW` from
  `task_review` before executing `next_task`.
- Use monotonically increasing orchestrator task ids `O-000001`, `O-000002`,
  etc.
- The first task for a fresh delivery is `USER_INPUT_CAPTURE` and must preserve
  the user's input exactly in `.sddtdd_skill/SPEC-DRAFT.md` plus create the
  `USER_INPUT` journal entry.
- For agent-generated artifacts, require independent reviewer verdict before
  orchestrator PASS.
- Do not let implementation begin before `TASK_REVIEW: PASS`.
- Do not allow `GREEN` before `RED_REVIEW: PASS` for that task.
- Do not allow final completion before `REGRESSION_REVIEW: PASS` and
  `FINAL_REVIEW: PASS`.
- Instructions must be in English and self-contained.

## Process-gate verification rules

For any submitted completed task:

1. Verify `work_journal_id` exists in `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log`.
2. Verify the work entry `TYPE` matches submitted `task_kind`.
3. Verify the work entry `STATUS` is `COMPLETED`.
4. Derive the required reviewer verdict from `task_kind`.
5. If a reviewer verdict is required, verify `evidence.review_journal_id`:
   - exists;
   - has the required review TYPE;
   - has `STATUS: PASS`;
   - has `PARENT` equal to `work_journal_id`.
6. If no reviewer verdict is required, `parent_for_orchestrator_review` is
   `work_journal_id`.
7. Verify required artifacts/evidence are committed at HEAD where possible.
8. Verify repository HEAD did not change during orchestrator inspection.
9. Return `task_review.status=PASS` only when the submitted task is
   process-complete.
10. Do not require `ORCHESTRATOR_TASK_REVIEW` to already exist for the submitted
    task; the implementer writes it from the returned `task_review`.

## Access log

The orchestrator writes runtime JSONL records to `.sddtdd_skill/orchestrator-access.jsonl`.
Suggested event names:

- `getNextTask_started`
- `getNextTask_completed`

Each completed event should include the request id, submitted task fields,
captured HEAD before/after, status, duration, and the orchestrator result.

## Independence rules

The orchestrator is not the reviewer. The orchestrator must never replace or
weaken independent artifact review. Reviewer PASS does not equal orchestrator
PASS; orchestrator PASS is `task_review.status=PASS` returned from
`getNextTask`.

The orchestrator may ask the implementer to fix whatever is blocking process
progress, including fixes that require changing code, tests, specs,
architecture, task files, or other artifacts. When such a fix creates or
changes any reviewed artifact, the orchestrator must explicitly remind the
implementer that the changed artifact must go through the appropriate
independent reviewer loop and receive a committed reviewer `PASS` before the
task can pass orchestration.

Allowed orchestrator `required_fixes` include process/evidence fixes, for
example:

- commit the missing work entry or artifact;
- supply the committed `work_journal_id`;
- supply the committed reviewer verdict JID;
- obtain the required reviewer `PASS` verdict;
- fix journal parent/root/task-id wiring;
- fix stale or mismatched review evidence;
- record and commit the required `ORCHESTRATOR_TASK_REVIEW` entry.

When the required fix changes a reviewed artifact, the orchestrator should name
the process requirement explicitly: complete the appropriate independent review,
record and commit the reviewer verdict, and retry `getNextTask` only after that
reviewer verdict is `PASS`.
