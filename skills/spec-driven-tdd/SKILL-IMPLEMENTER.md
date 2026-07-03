---
name: spec-driven-tdd-implementer
description: "Use when implementing Spec-Driven TDD. In broker mode, the implementer uses one broker operation, getNextTask, and the independent reviewer tool."
version: 3.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, mcp, task-broker, implementer]
    related_skills: [spec-driven-tdd]
---

# Spec-Driven TDD Implementer Role

## Overview

The implementer performs the work: creates artifacts, runs tests, requests
independent reviews, updates the journal, commits, and reports task completion.

The pipeline has two operating modes:

- **Standalone** — read `references/STAGES.md` and walk the chain directly.
- **Broker** — do not walk the chain. Ask the broker for one task at a time.

## Files this implementer must load

- `SKILL.md`
- `SKILL-IMPLEMENTER.md`
- `references/JOURNAL.md`

In standalone mode also read `references/STAGES.md`.

In broker mode do **not** read `SKILL-ORCHESTRATOR.md` or
`references/STAGES.md`; those are broker policy.

## Standalone mode

Follow `references/STAGES.md` using `references/JOURNAL.md`.

## Broker mode

The implementer knows exactly one broker operation:

```text
mcp_sddtdd_getNextTask
```

There is no separate broker process-gate operation.
There is no previous-task-id field.
There is no broker `init`.

The independent reviewer remains:

```text
mcp_sddtdd_review
```

## Broker input shape

Every broker call uses this same shape:

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

First call:

```json
{
  "repo_path": "/path/to/repo",
  "task_kind": "INITIAL_USER_INPUT",
  "task_id": null,
  "claimed_result": null,
  "work_journal_id": null,
  "evidence": {
    "user_input": "<full original user request>"
  }
}
```

Completed task call:

```json
{
  "repo_path": "/path/to/repo",
  "task_kind": "<completed task kind>",
  "task_id": "<broker task id>",
  "claimed_result": "<summary>",
  "work_journal_id": "<work JID>",
  "evidence": {
    "review_journal_id": "<review JID when required>",
    "commits": ["..."],
    "journal_ids": ["..."],
    "files": ["..."],
    "test_commands": ["..."]
  }
}
```

Do not send `review_type` to the broker. The broker derives required review
type from `task_kind`.

## Broker output shape

The broker returns:

```json
{
  "status": "task | fail | needs_clarification | error | complete",
  "task_review": {
    "status": "PASS | FAIL | NEEDS_CLARIFICATION | ERROR",
    "findings": ["..."],
    "required_fixes": ["..."],
    "parent_for_broker_review": "JID|null",
    "detail_suggestion": "string|null",
    "rationale": "..."
  },
  "next_task": {
    "task_id": "B-000001",
    "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
    "instruction": "...",
    "allowed_scope": ["..."],
    "required_evidence": ["..."],
    "independent_review_required": true,
    "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
    "rationale": "..."
  },
  "rationale": "..."
}
```

## Broker loop

1. Load this role file and `references/JOURNAL.md`.
2. Do the existing-delivery check. If an existing delivery is present and the
   user request is a new iteration, ask whether to archive, continue, or cancel.
3. Start by calling `mcp_sddtdd_getNextTask` with
   `task_kind=INITIAL_USER_INPUT` and `evidence.user_input`.
4. If the broker returns `status=task`, execute only `next_task`.
5. For the returned task:
   1. Follow `instruction` exactly.
   2. Stay within `allowed_scope`.
   3. Produce all `required_evidence`.
   4. Journal the work entry with `STATUS: COMPLETED`.
   5. Commit the work artifacts and journal entry.
   6. If `independent_review_required=true`, call `mcp_sddtdd_review` using
      `next_task.review_type`, journal the reviewer verdict, and commit.
6. Call `mcp_sddtdd_getNextTask` with the completed task evidence.
7. Inspect `task_review`.
   - If `task_review.status=PASS`, append `BROKER_TASK_REVIEW` with
     `STATUS: PASS`, `TASK_ID` equal to the broker task id, and `PARENT` equal
     to `task_review.parent_for_broker_review`; use `detail_suggestion` for
     `DETAIL`. Commit it. Only then may you execute `next_task`.
   - If `task_review.status=FAIL`, append and commit
     `BROKER_TASK_REVIEW: FAIL`, fix `required_fixes`, and retry
     `mcp_sddtdd_getNextTask` with corrected completed-task evidence.
   - If `NEEDS_CLARIFICATION`, ask for the missing information or produce the
     missing evidence; do not execute a next task.
   - If `ERROR`, resolve repository/tooling state; do not execute a next task.
8. Stop only when `status=complete`.

## What a broker task looks like

```json
{
  "task_id": "B-000001",
  "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
  "instruction": "one concrete instruction",
  "allowed_scope": ["files, paths, or artifacts the task may touch"],
  "required_evidence": ["concrete evidence the implementer must produce"],
  "independent_review_required": true,
  "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
  "rationale": "why this task is next"
}
```

Use `next_task.review_type` only for calling the independent reviewer. Do not
send it back as broker input.

## Broker task journal chain

For a task requiring independent review:

```text
work journal entry (STATUS: COMPLETED)
→ reviewer verdict (STATUS: PASS, PARENT = work)
→ getNextTask completed-task call
→ BROKER_TASK_REVIEW (STATUS: PASS, PARENT = task_review.parent_for_broker_review)
→ next task work entry
```

For a task not requiring independent review:

```text
work journal entry (STATUS: COMPLETED)
→ getNextTask completed-task call
→ BROKER_TASK_REVIEW (STATUS: PASS, PARENT = work)
→ next task work entry
```

## Hard rules

- Do not execute `next_task` from a completed-task broker response until
  `task_review.status=PASS` has been journaled as `BROKER_TASK_REVIEW` and
  committed.
- Reviewer PASS is not broker PASS.
- Broker PASS is `task_review.status=PASS` from `mcp_sddtdd_getNextTask`.
- Never call a removed broker operation.
- Never send `review_type` as broker input.
- Do not read `SKILL-ORCHESTRATOR.md` in broker mode.
- Do not move to GREEN before RED_REVIEW PASS and broker task_review PASS.
- Do not depend on uncommitted artifacts or uncommitted journal entries.
- Every artifact and journal entry must be committed before it is used as
  evidence.
