---
name: spec-driven-tdd-implementer
description: "Implementer role for Spec-Driven TDD."
version: 4.2.0-min
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD Implementer Role

## Load set

Always load:

- `SKILL.md`
- `SKILL-IMPLEMENTER.md`
- `references/JOURNAL.md`

In standalone mode also load `references/STAGES.md`.
In orchestrator mode do not load `SKILL-ORCHESTRATOR.md` or `references/STAGES.md`.

## Modes

### Standalone

Walk the pipeline directly using `references/STAGES.md`.

### Orchestrator

Use exactly:

```text
mcp_sddtdd_getNextTask
mcp_sddtdd_review
```

There is no separate init call, no separate process-gate tool, and no
previous-task-id field.

## Orchestrator request shape

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

Start with `task_kind=INITIAL_USER_INPUT` and the full original user request in
`evidence.user_input`.

For completed tasks, send the orchestrator-issued `task_id`, the committed work
JID, a factual result summary, and the committed evidence.

Do not send `review_type` to the orchestrator. It is derived from `task_kind`.

## Orchestrator loop

1. Call `mcp_sddtdd_getNextTask` with `INITIAL_USER_INPUT`.
2. Execute only the returned `next_task`.
3. Stay within `allowed_scope`.
4. Produce all `required_evidence`.
5. Journal the work entry with `STATUS: COMPLETED`.
6. Commit artifacts and journal entry before using them as evidence.
7. If the task requires independent review:
   - call `mcp_sddtdd_review` with `next_task.review_type`;
   - journal the verdict;
   - commit the review entry before continuing.
8. Call `mcp_sddtdd_getNextTask` with completed-task evidence.
9. Inspect `task_review`.
10. If `task_review.status=PASS`:
    - append `ORCHESTRATOR_TASK_REVIEW: PASS`;
    - set `TASK_ID` to the orchestrator task id;
    - set `PARENT` to `task_review.parent_for_orchestrator_review`;
    - use `detail_suggestion` as the DETAIL base;
    - commit it;
    - only then execute the new `next_task`.
11. If `task_review.status=FAIL`:
    - append and commit `ORCHESTRATOR_TASK_REVIEW: FAIL`;
    - fix the listed process or evidence gaps;
    - if a fix changes a reviewed artifact, obtain and commit a fresh reviewer verdict;
    - retry `getNextTask`.
12. If `task_review.status=NEEDS_CLARIFICATION`:
    - append and commit `ORCHESTRATOR_TASK_REVIEW: NEEDS_CLARIFICATION`;
    - ask the user or produce the missing proof;
    - do not execute a next task.
13. If `task_review.status=ERROR`:
    - append and commit `ORCHESTRATOR_TASK_REVIEW: ERROR`;
    - resolve repository, tooling, or evidence-state problems;
    - do not execute a next task.
14. Stop only on `status=complete`.

## Hard rules

- Never execute a task the orchestrator did not issue.
- Never execute `next_task` from a completed-task response before committing the matching `ORCHESTRATOR_TASK_REVIEW`.
- Reviewer `PASS` is not orchestrator `PASS`.
- Do not depend on uncommitted artifacts, uncommitted journal entries, or mutable working-tree state as evidence.
- Do not move to GREEN before `RED_REVIEW: PASS` and orchestrator PASS for that RED task.
- Do not treat `FAIL`, `NEEDS_CLARIFICATION`, or `ERROR` as approval.
- If a correction changes a reviewed artifact, prior review proof is stale until a fresh verdict is committed.
