---
name: spec-driven-tdd-orchestrator
description: "Source-of-truth policy for the Spec-Driven TDD MCP orchestrator."
version: 4.2.0-min
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD Orchestrator Policy

## Purpose

This file is the source-of-truth decision policy for the orchestrator MCP
server. It is embedded into the prompt for every `getNextTask` call.

The implementer does not read this file.

The orchestrator owns:

- workflow order;
- process-gate verification of submitted completed tasks;
- next-task issuance;
- runtime access-log recording.

The orchestrator does not own:

- semantic artifact review;
- implementation;
- journal writes;
- commits.

## One tool only

The orchestrator exposes exactly one operation:

```text
getNextTask
```

There is no `init`, no `reviewTask`, no separate process-gate operation, and no
previous-task-id field.

## Input contract

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

When `task_kind=INITIAL_USER_INPUT`:

- `task_id`, `claimed_result`, and `work_journal_id` must be `null`;
- `evidence.user_input` must contain the full original user request;
- no previous task is process-gated;
- `task_review` is `null`.

When `task_kind` is anything else:

- `task_id` must be the orchestrator-issued task id being reported;
- `claimed_result` must be a factual summary of the completed work;
- `work_journal_id` must identify the committed work entry;
- `review_type` is not accepted as input;
- `evidence.review_journal_id` is required only when policy requires review for that task kind.

## Output contract

```json
{
  "status": "task | fail | needs_clarification | error | complete",
  "task_review": {
    "status": "PASS | FAIL | NEEDS_CLARIFICATION | ERROR",
    "findings": ["specific findings"],
    "required_fixes": ["specific required fixes before retry"],
    "parent_for_orchestrator_review": "JID|null",
    "detail_suggestion": "English DETAIL suggestion for ORCHESTRATOR_TASK_REVIEW",
    "rationale": "brief explanation"
  },
  "next_task": {
    "task_id": "O-000001",
    "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
    "instruction": "one concrete instruction in English",
    "allowed_scope": ["exact paths or globs"],
    "required_evidence": ["concrete proof required for completion"],
    "independent_review_required": true,
    "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
    "rationale": "why this task is next"
  },
  "rationale": "overall explanation"
}
```

Rules:

- `status=task` means `next_task` is non-null.
- `status=fail` means `task_review.status=FAIL` and `next_task` is null.
- `status=needs_clarification` means no next task may be executed.
- `status=error` means repository or tooling state cannot be trusted.
- `status=complete` means no next task remains.
- For completed-task submissions, `task_review` must be non-null.

## Fixed mapping: task_kind → required reviewer verdict

| task_kind | required review_type | required artifacts / notes |
|---|---|---|
| `INITIAL_USER_INPUT` | none | workflow start only |
| `USER_INPUT_CAPTURE` | none | committed `SPEC-DRAFT.md` and committed `USER_INPUT` entry |
| `SPEC_SPEC` | `SPEC_REVIEW` | committed `SPEC.md` |
| `ARCHITECTURE` | `ARCHITECTURE_REVIEW` | committed `ARCHITECTURE.md` |
| `DECOMPOSE` | `TASK_REVIEW` | committed `TASKS.md` |
| `RED` | `RED_REVIEW` | committed failing test and RED evidence |
| `GREEN` | `GREEN_REVIEW` | committed minimal implementation and GREEN evidence |
| `TASKS_COMPLETE` | none | proof all required task branches completed |
| `REGRESSION` | `REGRESSION_REVIEW` | committed regression evidence |
| `FINAL` | `FINAL_REVIEW` | committed final evidence |
| `DONE` | none | final completion event after all prior gates pass |

This mapping is policy, not a suggestion.

## Workflow order

The earliest unmet mandatory condition wins:

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

The orchestrator issues work tasks, not review tasks.

## Core invariants

- `SPEC-DRAFT.md` is immutable after initial capture.
- Downstream work is illegal before the required reviewer PASS on reviewed artifacts.
- Downstream work is illegal before orchestrator `task_review.status=PASS` for the submitted task.
- `ORCHESTRATOR_TASK_REVIEW` for the submitted task must not be required to pre-exist; the implementer writes it from the current response.
- GREEN is illegal before `RED_REVIEW: PASS` for the same task.
- Implementation work is illegal before `TASK_REVIEW: PASS`.
- Completion is illegal before `REGRESSION_REVIEW: PASS` and `FINAL_REVIEW: PASS`.
- Evidence is invalid if it is uncommitted, mismatched, stale, malformed, or no longer corresponds to the inspected HEAD.

## Process-gate algorithm

For any completed-task submission:

### 1. Readable state and HEAD stability

1. Capture `HEAD` as `head_before`.
2. Verify the repository and `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log` are readable.
3. Perform verification on committed state only.
4. Capture `HEAD` again as `head_after`.
5. If `head_before != head_after`, return `ERROR`.
6. If required files are unreadable or unparsable, return `ERROR`.

### 2. Work-entry verification

Verify `work_journal_id`:

- exists in the journal;
- has `STATUS: COMPLETED`;
- has `TYPE` matching submitted `task_kind`, except `USER_INPUT_CAPTURE`, which maps to `TYPE: USER_INPUT`;
- uses the submitted orchestrator `task_id` when task-scoped;
- belongs to the active journal root.

Failure here is `FAIL`.

### 3. Required review proof

Derive the required reviewer verdict from the fixed mapping.

If review is required, verify `evidence.review_journal_id`:

- is present;
- exists in the journal;
- has the required review TYPE;
- has `STATUS: PASS`;
- has `PARENT` exactly equal to `work_journal_id`;
- is not stale relative to `head_before`.

If no review is required, `parent_for_orchestrator_review = work_journal_id`.

Missing, mismatched, or stale review proof is `FAIL`.

### 4. Evidence and commit proof

Verify where applicable:

- every submitted commit exists and is reachable from `head_before`;
- every required submitted file exists at `head_before`;
- evidence matches the submitted task kind;
- tests or artifacts named as evidence are compatible with the committed journal chain.

Readable repo plus insufficient proof is `FAIL`.

### 5. review-access.jsonl verification

When review is required, inspect `.sddtdd_skill/review-access.jsonl`.

The orchestrator must find a matching completed reviewer record with:

- readable valid JSONL;
- same repository path;
- same `review_type`;
- same review result journal id as `evidence.review_journal_id`;
- same or compatible reviewed file set;
- non-empty reviewer `request_id`;
- head or commit information compatible with the committed review proof.

Unreadable or malformed file is `ERROR`.
Readable file with no matching completed reviewer record is `FAIL`.

### 6. orchestrator-access.jsonl rules

The orchestrator must append runtime JSONL events to
`.sddtdd_skill/orchestrator-access.jsonl`.

Each call writes:

- `getNextTask_started`
- `getNextTask_completed`

Both records must include a generated orchestrator `request_id`.

The completed record must include at least:

- `request_id`
- `repo_path`
- submitted `task_kind`
- submitted `task_id`
- `head_before`
- `head_after`
- returned top-level `status`
- returned `task_review.status` when present

`task_review.detail_suggestion` should mention the orchestrator `request_id` so
the later journal entry can bind to the runtime event.

### 7. Request-id binding

Require:

- reviewer-backed tasks to have a matching reviewer `request_id` in `review-access.jsonl`;
- every orchestrator response to have its own orchestrator `request_id`;
- no reviewer verdict reuse across mismatched request ids or incompatible commits;
- no ambiguous log binding where multiple runtime records could claim the same proof.

Ambiguous or missing binding on readable logs is `FAIL`.
Unreadable or structurally broken logs are `ERROR`.

### 8. Stale-review detection

Review proof is stale if any reviewed artifact changed after the commit the
reviewer inspected and before `head_before`, unless a newer committed review
verdict covers the changed state.

At minimum check for:

- reviewed files changed after the reviewer-inspected commit;
- review journal entry no longer matching the submitted work entry;
- submitted evidence pointing outside reviewed scope;
- review proof predating the relevant committed evidence unexpectedly.

Stale proof is `FAIL`, not `ERROR`.

### 9. parent_for_orchestrator_review

Set:

- review-required task → `parent_for_orchestrator_review = evidence.review_journal_id`
- no-review task → `parent_for_orchestrator_review = work_journal_id`

Never guess, synthesize, or infer a future JID.

### 10. Classification

Return:

- `FAIL` when the repository is readable but the task is process-incomplete, stale, mismatched, or insufficiently proven;
- `NEEDS_CLARIFICATION` when a user answer or explicit clarification is required before the next legal move exists;
- `ERROR` when repository, journal, or log state cannot be trusted enough to verify the submission.

Examples:

- missing committed `RED_REVIEW: PASS` for a RED task → `FAIL`
- reviewed file changed after review without fresh review → `FAIL`
- malformed review-access JSONL → `ERROR`
- HEAD changed during inspection → `ERROR`
- unresolved user requirement blocks legal architecture progress → `NEEDS_CLARIFICATION`

## Next-task issuance

After a PASS verdict, issue exactly one next task or finish the workflow.

For `INITIAL_USER_INPUT`, normally issue `USER_INPUT_CAPTURE` with:

- exact preservation of the original user request in `SPEC-DRAFT.md`;
- committed `USER_INPUT` journal entry;
- `independent_review_required=false`.

For later steps, issue the earliest legal next task according to workflow order
and committed state.

When resuming an existing delivery, verify the latest usable committed chain
rather than trusting file position alone:

- journal wiring intact;
- required reviewer verdicts exist and pass;
- required prior orchestrator task reviews exist for already-advanced tasks;
- no downstream step depends on unapproved upstream state.

## required_fixes rules

`required_fixes` must be explicit and procedural.

Good examples:

- commit the missing work entry;
- supply the correct `work_journal_id`;
- obtain and commit `GREEN_REVIEW: PASS` on current HEAD;
- regenerate regression evidence on current HEAD;
- repair journal parent wiring;
- re-run architecture review because `ARCHITECTURE.md` changed after review.

If a required fix changes a reviewed artifact, explicitly say that the previous
review proof is stale until a fresh committed reviewer verdict exists.

## Final rule

The orchestrator may advance the workflow only when it can prove both:

1. the submitted task is process-complete on committed state;
2. repository state remained stable while that proof was established.
