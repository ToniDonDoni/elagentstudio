# Demo Feature Case: Counter API with Commit-Based Spec-Driven TDD

This walkthrough demonstrates the Spec-Driven TDD workflow and the one-tool
orchestrator API.

The example request:

> Build a simple in-memory counter. It starts at zero, can be decremented,
> never goes below zero, and exposes its current value.

## Orchestrator start

The implementer starts orchestrator mode with one call:

```json
{
  "repo_path": "/path/to/repo",
  "task_kind": "INITIAL_USER_INPUT",
  "task_id": null,
  "claimed_result": null,
  "work_journal_id": null,
  "evidence": {
    "user_input": "Build a simple in-memory counter. It starts at zero, can be decremented, never goes below zero, and exposes its current value."
  }
}
```

The orchestrator returns `status=task`, `task_review=null`, and
`next_task.task_kind=USER_INPUT_CAPTURE`.

## USER_INPUT_CAPTURE

The implementer creates `.sddtdd_skill/SPEC-DRAFT.md` preserving the request
exactly and writes the `USER_INPUT` journal entry.

```text
=== J-20260614-100000-001 ===
TYPE: USER_INPUT
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: --
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-000
PARENT_TASK_ID: --
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Initial Counter API request received.
```

Commit:

```text
spec: capture immutable raw input for S-DEMO-01
```

Then the implementer calls `getNextTask` again:

```json
{
  "repo_path": "/path/to/repo",
  "task_kind": "USER_INPUT_CAPTURE",
  "task_id": "O-000001",
  "claimed_result": "Captured immutable raw user input and USER_INPUT journal entry.",
  "work_journal_id": "J-20260614-100000-001",
  "evidence": {
    "commits": ["<hash>"],
    "journal_ids": ["J-20260614-100000-001"],
    "files": [".sddtdd_skill/SPEC-DRAFT.md", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"]
  }
}
```

The orchestrator returns `task_review.status=PASS` and the next task. The implementer
writes and commits:

```text
=== J-20260614-100000-002 ===
TYPE: ORCHESTRATOR_TASK_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-001
ROOT: J-20260614-100000-001
TASK_ID: O-000001
PARENT_TASK_ID: --
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Orchestrator verified USER_INPUT_CAPTURE as process-complete.
```

Only after that commit may the implementer execute the returned `next_task`.

## SPEC_SPEC and SPEC_REVIEW

The orchestrator issues `SPEC_SPEC`. The implementer creates
`.sddtdd_skill/SPEC.md`, journals `SPEC_SPEC`, commits, calls
`mcp_sddtdd_review` with `SPEC_REVIEW`, journals `SPEC_REVIEW: PASS`, commits,
then calls `getNextTask` with:

```json
{
  "repo_path": "/path/to/repo",
  "task_kind": "SPEC_SPEC",
  "task_id": "O-000002",
  "claimed_result": "Derived editable SPEC.md from SPEC-DRAFT.md.",
  "work_journal_id": "J-20260614-100000-003",
  "evidence": {
    "review_journal_id": "J-20260614-100000-004",
    "commits": ["<hash1>", "<hash2>"],
    "journal_ids": ["J-20260614-100000-003", "J-20260614-100000-004"],
    "files": [".sddtdd_skill/SPEC.md", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"]
  }
}
```

If the orchestrator returns `task_review.status=PASS`, the implementer records
`ORCHESTRATOR_TASK_REVIEW: PASS`, commits it, and executes `next_task`.

## RED task example

For a RED task, the implementer writes a failing test, captures expected RED
evidence, journals `RED`, commits, calls `mcp_sddtdd_review` with
`RED_REVIEW`, journals `RED_REVIEW: PASS`, commits, then calls `getNextTask`
with completed RED evidence.

The orchestrator may return:

```json
{
  "status": "task",
  "task_review": {
    "status": "PASS",
    "findings": ["RED work entry and RED_REVIEW PASS are committed."],
    "required_fixes": [],
    "parent_for_orchestrator_review": "J-20260614-100000-008",
    "detail_suggestion": "Orchestrator verified RED task O-000010 as process-complete.",
    "rationale": "The submitted RED task satisfies the process gate."
  },
  "next_task": {
    "task_id": "O-000011",
    "task_kind": "GREEN",
    "instruction": "Implement the minimal code required to satisfy the reviewed RED test.",
    "allowed_scope": ["src/**", "tests/**", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
    "required_evidence": ["Committed implementation", "GREEN journal entry", "Passing task test command"],
    "independent_review_required": true,
    "review_type": "GREEN_REVIEW",
    "rationale": "RED_REVIEW has passed, so GREEN is the next legal task."
  },
  "rationale": "Previous task passed process verification; issuing the next task."
}
```

The implementer must commit `ORCHESTRATOR_TASK_REVIEW: PASS` before executing GREEN.

## Orchestrator FAIL example

If process evidence is missing, the orchestrator returns `status=fail` and no
`next_task`.

```json
{
  "status": "fail",
  "task_review": {
    "status": "FAIL",
    "findings": ["Missing committed RED_REVIEW PASS entry."],
    "required_fixes": ["Call the independent reviewer, journal RED_REVIEW PASS, commit it, then retry getNextTask."],
    "parent_for_orchestrator_review": null,
    "detail_suggestion": null,
    "rationale": "The submitted task is not process-complete."
  },
  "next_task": null,
  "rationale": "Orchestrator cannot issue the next task until the submitted task passes process verification."
}
```

The implementer records `ORCHESTRATOR_TASK_REVIEW: FAIL`, commits it, fixes the
required gaps, and retries `getNextTask` with corrected completed-task evidence.
