# Spec-Driven TDD — usage

This skill turns a user request into working software through a chain of
explicit, traceable, committed, and independently reviewed artifacts, with
RED-GREEN TDD for every behavior that can be tested automatically. Every
step is journaled so the work can be reconstructed and audited.

There are two operating modes. Artifacts, journal, and principles are
identical in both.

- **Standalone mode** — no orchestrator. The implementer walks the artifact chain
  stage by stage, reading `SKILL-IMPLEMENTER.md` and `references/STAGES.md`.
- **Orchestrator mode** — one MCP orchestrator tool decides and advances the workflow.
  The implementer calls `mcp_sddtdd_getNextTask` for initial input and after
  each completed task. The independent reviewer remains
  `mcp_sddtdd_review`.

## File layout (project side)

All SDDTDD artifacts and runtime logs live under `<project-dir>/.sddtdd_skill/`:

- **Committed**: `SPEC-DRAFT.md`, `SPEC.md`, `ARCHITECTURE.md`,
  `TASKS.md`, `JOURNAL_SDD_TDD_SKILL.log`.
- **Runtime, not committed**: `review-access.jsonl`, `orchestrator-access.jsonl`.

The committed artifacts and journal are part of the deliverable.

## Orchestrator mode short version

1. Pick a clean working directory.
2. Make sure these MCP tools are reachable:
   - `mcp_sddtdd_getNextTask`
   - `mcp_sddtdd_review`
3. Make sure the `spec-driven-tdd` skill is preloaded.
4. Start the workflow by calling `mcp_sddtdd_getNextTask` with
   `task_kind: INITIAL_USER_INPUT`.
5. Execute only the `next_task` returned by the orchestrator.
6. For every completed task:
   - journal and commit the work entry;
   - if `next_task.independent_review_required` was true, call
     `mcp_sddtdd_review`, journal the reviewer verdict, and commit;
   - call `mcp_sddtdd_getNextTask` again with the completed task evidence;
   - if `task_review.status` is `PASS`, journal and commit
     `ORCHESTRATOR_TASK_REVIEW`, then execute `next_task`;
   - if `status` is `fail`, `needs_clarification`, or `error`, do not execute
     `next_task`; fix or clarify what the orchestrator requested.
7. Stop when `status` is `complete`.

## Orchestrator input schema

`mcp_sddtdd_getNextTask` always uses one input shape.

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
    "user_input": "Build counter API..."
  }
}
```

Completed task call:

```json
{
  "repo_path": "/path/to/repo",
  "task_kind": "RED",
  "task_id": "O-000004",
  "claimed_result": "Added RED test and captured expected failure.",
  "work_journal_id": "J-20260703-120000-001",
  "evidence": {
    "review_journal_id": "J-20260703-120000-002",
    "commits": ["abc1234"],
    "journal_ids": ["J-20260703-120000-001", "J-20260703-120000-002"],
    "files": ["tests/test_counter.py"],
    "test_commands": ["pytest tests/test_counter.py -q"]
  }
}
```

`review_type` is not orchestrator input. The orchestrator derives the required reviewer
verdict from `task_kind`.

## Orchestrator output schema

```json
{
  "status": "task | fail | needs_clarification | error | complete",
  "task_review": {
    "status": "PASS | FAIL | NEEDS_CLARIFICATION | ERROR",
    "findings": ["string"],
    "required_fixes": ["string"],
    "parent_for_orchestrator_review": "string|null",
    "detail_suggestion": "string|null",
    "rationale": "string"
  },
  "next_task": {
    "task_id": "string",
    "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
    "instruction": "string",
    "allowed_scope": ["string"],
    "required_evidence": ["string"],
    "independent_review_required": true,
    "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
    "rationale": "string"
  },
  "rationale": "string"
}
```

For `INITIAL_USER_INPUT`, `task_review` is `null` and `next_task` is normally
`USER_INPUT_CAPTURE`.

For completed tasks, `task_review` is the orchestrator process-gate verdict for the
submitted task. The implementer must record it as `ORCHESTRATOR_TASK_REVIEW` and
commit it before executing `next_task`.

## Example user prompt — orchestrator mode

```text
You are running inside `<project-dir>`. The `spec-driven-tdd` skill is
preloaded. Operate in orchestrator mode using `SKILL-IMPLEMENTER.md`. Do not read
`SKILL-ORCHESTRATOR.md`; that file is for the orchestrator MCP server.

## Task

<describe what to build, including user-visible behavior, constraints, test
scenarios, and the test command>

## Process — non-negotiable

1. Run the workflow only through `mcp_sddtdd_getNextTask` and
   `mcp_sddtdd_review`.
2. Start with `mcp_sddtdd_getNextTask` using `task_kind=INITIAL_USER_INPUT`
   and `evidence.user_input` set to this full task description.
3. Execute only the orchestrator's `next_task`.
4. Commit every work artifact and journal entry before asking the orchestrator to
   advance.
5. If the orchestrator task says `independent_review_required=true`, call
   `mcp_sddtdd_review` using `next_task.review_type`, journal the verdict, and
   commit it before asking the orchestrator to advance.
6. After each completed task, call `mcp_sddtdd_getNextTask` with the completed
   task evidence. If `task_review.status=PASS`, append and commit a
   `ORCHESTRATOR_TASK_REVIEW` entry using `parent_for_orchestrator_review` and
   `detail_suggestion`, then continue with `next_task`.
7. If the orchestrator returns `fail`, `needs_clarification`, or `error`, do not
   execute a next task. Fix or clarify the listed issue and retry.
8. When the orchestrator returns `complete`, write a final report listing commits,
   JIDs, test commands, and `.sddtdd_skill/orchestrator-access.jsonl` contents.
```

## What to check afterwards

- `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log` is committed and shows the full chain.
- `.sddtdd_skill/orchestrator-access.jsonl` shows `getNextTask_started` and
  `getNextTask_completed` activity for orchestrator advancement.
- `.sddtdd_skill/review-access.jsonl` shows independent reviewer activity.
- The requested test command passes.
- `git log --oneline` shows a clean, reviewable commit history.
