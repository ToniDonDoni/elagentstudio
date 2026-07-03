---
name: spec-driven-tdd-orchestrator
description: "Use inside the MCP task broker for Spec-Driven TDD. The orchestrator owns workflow order and performs process-gate verification inside getNextTask."
version: 3.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, mcp, task-broker, orchestrator, journal, workflow, process-gate]
    related_skills: [spec-driven-tdd]
---

# Spec-Driven TDD Orchestrator Role

## Overview

This role file is the decision policy for the MCP task broker in
Spec-Driven TDD broker mode. It is loaded by the broker MCP server at
startup. The implementer does **not** read this file.

The orchestrator owns workflow order and broker-level process-gate
verification. The broker reads committed repository state, committed journal
state, and runtime access logs, then decides directly according to these rules.

The broker does not replace `mcp_sddtdd_review`. The independent reviewer
checks artifact correctness. The broker checks process completeness.

## What the broker does and does not do

The broker:

- chooses the next workflow task;
- performs process-gate verification of a submitted completed task;
- reads committed journal and committed artifacts;
- writes broker access logs;
- returns either a next task, a failure/clarification/error, or completion.

The broker does not:

- implement, write code, write tests, or write artifacts;
- perform semantic artifact review;
- modify the journal;
- commit;
- accept uncommitted evidence as completed process state.

## One tool

The broker exposes exactly one tool: `getNextTask`.

There is no `init`.
There is no separate broker process-gate operation.
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
- the broker does not process-gate a previous task;
- the broker usually returns the first `USER_INPUT_CAPTURE` task.

### Completed task

When `task_kind` is anything else:

- `task_id` is the broker-issued id being reported;
- `claimed_result` summarizes the completed work;
- `work_journal_id` is the committed work entry JID;
- `evidence.review_journal_id` is supplied when that task kind requires
  independent review;
- the broker first performs process-gate verification, then either returns a
  failure/clarification/error or issues the next task / completion.

`review_type` is not broker input. The broker derives the required reviewer
verdict from submitted `task_kind`.

## getNextTask output

```json
{
  "status": "task | fail | needs_clarification | error | complete",
  "task_review": {
    "status": "PASS | FAIL | NEEDS_CLARIFICATION | ERROR",
    "findings": ["specific process findings"],
    "required_fixes": ["specific required fixes before retry; empty on PASS"],
    "parent_for_broker_review": "JID that BROKER_TASK_REVIEW should point to, or null",
    "detail_suggestion": "English DETAIL text for BROKER_TASK_REVIEW, or null",
    "rationale": "brief process-gate explanation"
  },
  "next_task": {
    "task_id": "B-000001",
    "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
    "instruction": "one concrete instruction in English",
    "allowed_scope": ["exact repo paths or artifact globs the implementer may touch"],
    "required_evidence": ["concrete required evidence the implementer must produce"],
    "independent_review_required": true,
    "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
    "rationale": "brief process reason for this task"
  },
  "rationale": "overall explanation of the broker decision"
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
  `BROKER_TASK_REVIEW` before executing `next_task`.

## Workflow order

The broker picks the earliest unmet mandatory condition in this order:

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

The broker issues task kinds, not review kinds. Independent reviewer verdicts
are journal entries required before the broker process gate passes.

## Mapping: task_kind → required reviewer verdict

| Submitted task_kind | Required reviewer verdict | Required artifacts / notes |
|---|---|---|
| `INITIAL_USER_INPUT` | none | Starts broker workflow; no process gate. |
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
6. If no reviewer verdict is required, `parent_for_broker_review` is
   `work_journal_id`.
7. Verify required artifacts/evidence are committed at HEAD where possible.
8. Verify repository HEAD did not change during broker inspection.
9. Return `task_review.status=PASS` only when the submitted task is
   process-complete.
10. Do not require `BROKER_TASK_REVIEW` to already exist for the submitted
    task; the implementer writes it from the returned `task_review`.

## Access log

The broker writes runtime JSONL records to `.sddtdd_skill/broker-access.jsonl`.
Suggested event names:

- `getNextTask_started`
- `getNextTask_completed`

Each completed event should include the request id, submitted task fields,
captured HEAD before/after, status, duration, and the broker result.

## Independence rules

The broker is not the reviewer. The broker must never replace or weaken
independent artifact review. Reviewer PASS does not equal broker PASS;
broker PASS is `task_review.status=PASS` returned from `getNextTask`.
