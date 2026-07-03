---
name: spec-driven-tdd-implementer
description: "Use when implementing Spec-Driven TDD. The implementer follows the standalone stage procedure, or, in broker mode, asks the broker for the next task and asks the broker to verify the task is process-complete. The implementer does not know the workflow order in broker mode."
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

This role file is the implementer-side contract for the Spec-Driven TDD
pipeline.

The implementer performs the work. The implementer creates and modifies
artifacts, runs tests, requests independent reviews, updates the
journal, commits, and reports task completion.

The pipeline has two operating modes:

- **Standalone** — the implementer walks the artifact chain directly by
  reading `references/STAGES.md` for the stage-by-stage procedure.
- **Broker** — the implementer does not walk the chain. The implementer
  asks the broker MCP for the next task, executes that task, asks the
  independent reviewer (when required), and asks the broker to verify
  the task is process-complete.

This role file covers both modes. The shared process skill, the journal
format, and the review rules are the same in both modes.

## Files this implementer must load

- `SKILL.md` — overview, principles, roles, invariants.
- `SKILL-IMPLEMENTER.md` — this file.
- `references/JOURNAL.md` — journal format and invariants.

In standalone mode also read:

- `references/STAGES.md` — the stage-by-stage procedure.

In broker mode the implementer does **not** read
`SKILL-ORCHESTRATOR.md` and does **not** read `references/STAGES.md`.
Those are loaded by the broker MCP server, not by the implementer.

## Standalone mode

The implementer walks the artifact chain in
`references/STAGES.md`, using the journal format from
`references/JOURNAL.md`. The implementer selects the next stage from
committed state, creates the next artifact, requests an independent
review, journals the verdict, and only then moves on.

## Broker mode

The implementer knows only two broker operations. There is **no**
`init`. The first call is `getNextTask` with `user_input`.

### The two broker operations

1. `getNextTask` — ask the broker for the next task, or for `complete`
   / a blocker. The first call carries `user_input`; subsequent calls
   carry `previous_task_id`.
2. `reviewTask` — ask the broker to verify that the current task is
   process-complete (the broker does not re-review the artifact).

That is the entire loop. There is no third operation and no `init`.

### What a broker task looks like

A broker task is self-contained. The implementer does not need to read
the workflow order to execute it. A task carries:

```json
{
  "task_id": "B-000001",
  "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | DONE",
  "instruction": "one concrete instruction in natural language",
  "allowed_scope": ["files, paths, or artifacts the task may touch"],
  "required_evidence": [
    "commits, journal ids, reviewer request ids, test commands, or
     other concrete artifacts the implementer must produce"
  ],
  "independent_review_required": true,
  "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | null"
}
```

The implementer follows the `instruction` literally, stays within
`allowed_scope`, produces the items in `required_evidence`, and only
runs the independent reviewer when `independent_review_required` is
true.

Capture tasks (`USER_INPUT_CAPTURE`) carry
`independent_review_required: false` and `review_type: null`. They do
not need an independent reviewer verdict; the broker only checks that
the work journal entry exists and is committed.

The implementer MUST NOT read the broker's `SKILL-ORCHESTRATOR.md` to
figure out the workflow order. The broker decides the order. The
implementer executes the issued task exactly.

### Broker loop

1. Load the shared `spec-driven-tdd` skill, this implementer role
   file, and `references/JOURNAL.md`. Do not load
   `SKILL-ORCHESTRATOR.md` or `references/STAGES.md`.
2. **Existing-delivery check.** Before calling the broker, inspect
   `.sddtdd_skill/`. If `SPEC-DRAFT.md`, `SPEC.md`, `TASKS.md`, 
   `JOURNAL_SDD_TDD_SKILL.log`, `broker-access.jsonl`, and `review-access.jsonl`
   already exist in the committed tree 
   (i.e. the repo already carries a finished or in-progress SDDTDD delivery), 
   a new user request is a *new iteration*, not a continuation. The
   implementer MUST ask the user before doing anything else. Use
   this exact phrasing (substitute the real identifier if visible
   in the journal):

   > A previous SDDTDD delivery is already committed in this repo
   > (`.sddtdd_skill/SPEC.md`, `.sddtdd_skill/TASKS.md`, etc.).
   > Your new request is a new iteration.
   >
   > How would you like to proceed?
   >
   > 1. **Archive the previous delivery and start fresh** (recommended).
   >    I will rename the old `.sddtdd_skill/SPEC-DRAFT.md`,
   >    `.sddtdd_skill/SPEC.md`, `.sddtdd_skill/TASKS.md`,
        `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log`, 
        `.sddtdd_skill/broker-access.jsonl`, 
        and `.sddtdd_skill/review-access.jsonl` 
        to `<NAME>_old_v<N>.md` where `<N>` is one greater than the
   >    highest existing `_old_v<N>` suffix for that name (so the
   >    first archive is `_v1`, the next `_v2`, and so on).
   >    `ARCHITECTURE.md` is **kept as-is** because the
   >    architecture is still valid for the new iteration; the
   >    broker will require a reviewed `SPEC.md` and `TASKS.md`
   >    that match the new request before any new work is issued.
   > 2. **Continue with the current spec** (no archiving). The
   >    new request will be applied to the existing `SPEC.md` and
   >    `TASKS.md`. Pick this only if the new request is a small
   >    amendment to the current delivery.
   > 3. **Cancel** — I will stop without making any changes.

   If the user picks 1: do the archive, commit it, and continue
   to step 3. If the user picks 2: skip the archive and continue
   to step 3 (the broker will see the existing committed
   artifacts and decide what to do). If the user picks 3: stop.

   The archive itself is a single commit produced by the
   implementer, not by the broker. Pick `<N>` by listing existing
   files:

   ```bash
   git ls-files '.sddtdd_skill/SPEC_old_v*.md' \
     | sed -E 's/.*_old_v([0-9]+)\.md/\1/' \
     | sort -n | tail -1
   ```

   If no `*_old_v*.md` files exist, the next `<N>` is `1`. Rename
   exactly these six files (leave `ARCHITECTURE.md` untouched), stage the renames, and
   commit with a message of the form
   `archive previous SDDTDD delivery as _v<N>`. After the commit,
   `.sddtdd_skill/` contains the archived files plus the
   unchanged `ARCHITECTURE.md`; the implementer then writes a
   fresh `SPEC-DRAFT.md` for the new request (the broker's first
   task will do this in the normal `USER_INPUT_CAPTURE` step
   below).
3. Call `getNextTask` with `repo_path` and `user_input` (the very
   first call of a delivery). On subsequent calls pass
   `previous_task_id`. The broker returns the first task,
   `complete`, or a blocker.
3. If the broker returned a task:
   1. Follow the `instruction` exactly, stay within `allowed_scope`,
      and produce every item in `required_evidence`.
   2. Journal the work as the appropriate `TYPE` for the stage the
      task represents (`USER_INPUT_CAPTURE`, `SPEC_SPEC`,
      `ARCHITECTURE`, `DECOMPOSE`, `RED`, `GREEN`, `REGRESSION`,
      `DONE`, etc.) with `STATUS: COMPLETED`. Commit the work and
      the journal entry.
   3. If `independent_review_required` is true, call
      `mcp_sddtdd_review` with the appropriate `review_type`,
      capture the verdict, journal it as the corresponding
      `*_REVIEW` entry with `STATUS: PASS` (or `FAIL` and rework),
      and commit. Repeat reviewer until `PASS`.
   4. Call broker `reviewTask` with the task id, `task_kind`,
      `review_type`, `claimed_result`, `work_journal_id` (the JID of
      the work entry from step 3.2), and `evidence.review_journal_id`
      (the JID of the reviewer verdict from step 3.3, when one was
      required).
4. The broker returns one of:
   - `PASS` — append a `BROKER_TASK_REVIEW` journal entry with
     `STATUS: PASS`, **`TASK_ID: <the broker task id you were
     verifying>`** (so the broker can match the verification to
     the issued task on the next `getNextTask` call), and `PARENT`
     pointing at the reviewer verdict (or the work journal entry
     for capture tasks); commit; **then** call `getNextTask` for
     the next task. The broker enforces this match — see rule 11
     in `SKILL-ORCHESTRATOR.md`.
   - `FAIL` — append a `BROKER_TASK_REVIEW` journal entry with
     `STATUS: FAIL`, `TASK_ID: <the broker task id>`, and the
     broker-listed findings in `DETAIL`; commit; fix the process
     gaps exactly as the broker listed them (e.g. commit the
     missing work entry, re-run the reviewer, fix a broken journal
     `PARENT`); then call `reviewTask` again. Repeat until `PASS`.
   - `NEEDS_CLARIFICATION` — append `BROKER_TASK_REVIEW:
     NEEDS_CLARIFICATION` (with `TASK_ID` and `PARENT`),
     commit, ask the user or supply the missing information,
     then continue.
   - `ERROR` — resolve tooling or repository state first.
5. Repeat until `getNextTask` returns `complete` (workflow finished) or
   a blocker. The broker returns `blocked` if you call `getNextTask`
   while a previous broker task is still unverified (no committed
   `BROKER_TASK_REVIEW: PASS` with the matching `TASK_ID`). When that
   happens, append nothing new — call `reviewTask` for the
   outstanding broker task id (named in the `unverified_task_ids`
   field of the `blocked` response) first, and only then call
   `getNextTask` again.

The implementer must not bypass the broker or continue the workflow independently in broker mode.
The implementer must either:
* resolve the broker error and retry the broker operation; or
* escalate to the user if the error cannot be resolved.
Any solution produced after bypassing the broker in broker mode is not acceptable to the user and rejected autonatically, regardless of its technical quality, completeness, or correctness.

Never remove or rename broker log file broker-access.jsonl.

### Broker task journal chain

The implementer produces this sequence in the journal for every broker
task:

```text
work journal entry
   TYPE = the stage the task represents
   STATUS = COMPLETED

independent reviewer verdict (only when the task requires one)
   TYPE = <review_type>
   STATUS = PASS
   PARENT = work journal entry

BROKER_TASK_REVIEW
   TYPE = BROKER_TASK_REVIEW
   TASK_ID = <broker task id being verified>
   STATUS = PASS | FAIL | NEEDS_CLARIFICATION | ERROR
   PARENT = reviewer verdict (or work journal entry when no reviewer)
   DETAIL = broker verdict and findings
```

For capture tasks (`USER_INPUT_CAPTURE`) the reviewer-verdict entry
is omitted; `BROKER_TASK_REVIEW.PARENT` is the work journal entry
directly.

The next broker task's work entry has the `BROKER_TASK_REVIEW: PASS`
entry as its `PARENT`.

## Independent review still uses the reviewer MCP

The broker is not a reviewer. The broker does not check whether the
artifact is correct, idiomatic, well-designed, or satisfies the
instruction. The independent reviewer does that. The broker only
checks that the reviewer verdict is in the journal with the right
status, the right `TYPE`, and a valid `PARENT`.


The implementer calls the reviewer MCP
(`mcp_sddtdd_review`) exactly as the shared `spec-driven-tdd`
skill requires. The MCP response `status` describes tool execution only:
`COMPLETED` means the tool call completed; any other status means the MCP
call did not complete successfully. If the MCP call did not complete,
retry the reviewer call. If retrying does not resolve the MCP/tool error,
escalate to the user instead of treating it as a review verdict.

When `status: COMPLETED`, the authoritative review outcome is the review
response's `verdict` field: `PASS`, `FAIL`, or `NEEDS_CLARIFICATION`.
`status: COMPLETED` MUST NOT be treated as review approval. Words such as
"failed" inside RED evidence describe expected RED test failures unless
`verdict` is `FAIL`. The implementer records the reviewer `verdict` in
`.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log`, commits the journal entry, and
only then asks the broker to verify the task.


A reviewer `*_REVIEW: PASS` is **not** the same as a broker
`BROKER_TASK_REVIEW: PASS`. The two chains are independent and both
must succeed.


The implementer must not bypass the reviewer
The implementer must either:
* resolve the reviewer issues and retry the review; or
* escalate to the user if the issue cannot be resolved or reviewer is unavailable
Any solution produced after bypassing the reviewer is not acceptable to the user and rejected autonatically, regardless of its technical quality, completeness, or correctness.

Never remove or rename reviewer log file review-access.jsonl.

## Hard rules

- Do not choose the next workflow stage yourself in broker mode.
  Always ask the broker via `getNextTask`.
- Do not skip the broker even if the next artifact "looks obvious"
  from the current state.
- Do not call `getNextTask` for the next task until `reviewTask` for
  the current task returned `PASS`.
- Do not call `getNextTask` until you have appended a
  `BROKER_TASK_REVIEW: PASS` journal entry carrying
  `TASK_ID: <broker task id>` and committed it. The broker rejects
  the next `getNextTask` call while a previous task is still
  unverified; the response names the outstanding `task_id` in
  `unverified_task_ids`.
- Do not call `getNextTask` while a previous broker task is still
  unverified, even if the work is already journaled. The broker
  will return `blocked` until `reviewTask` confirms process
  completion.
- If the reviewer MCP response `status` is not `COMPLETED`, retry the
  reviewer call. If the MCP/tool error persists, escalate to the user.
- When reviewer MCP `status` is `COMPLETED`, decide reviewer success only
  from the reviewer response `verdict` field. Do not use MCP
  `status: COMPLETED` as approval, and do not treat expected RED test
  failures mentioned in the response body as review failures.
- Do not treat a reviewer `PASS` as a broker `reviewTask PASS`; the
  broker must confirm process completion.
- Do not execute work outside the broker task's `allowed_scope`.
- Do not let the broker modify files. All repository changes are the
  implementer's responsibility.
- Do not continue when the broker returns `blocked` or `ERROR`;
  resolve the issue first.
- Do not read or follow `SKILL-ORCHESTRATOR.md` as instructions for the
  implementer. That file is for the broker MCP server.

## Verification checklist

- [ ] `spec-driven-tdd` and this implementer role file are loaded.
- [ ] In standalone mode, the stage procedure and journal format are
      loaded.
- [ ] In broker mode, every task came from the broker via
      `getNextTask` (the first call carries `user_input`).
- [ ] In broker mode, every completed task produced a work journal
      entry and (when required) a reviewer-verdict journal entry,
      both committed before `reviewTask` was called.
- [ ] In broker mode, every completed task was verified by the broker
      through `reviewTask` and produced a `BROKER_TASK_REVIEW` journal
      entry.
- [ ] The final report says the broker returned `complete` or
      describes the blocker.
- [ ] The final report includes a "Compromises and deviations" section listing
      every journaled `AGENT_DECISION`, compromise, deviation, or practical
      substitution made during the delivery, including minor technical
      compromises.
- [ ] The final report includes a separate "Major acceptance changes" section
      for every compromise that changed, weakened, replaced, or reinterpreted
      an acceptance criterion, user-visible behavior, user-observable evidence,
      or required test boundary. If there were no such major compromises, the
      section explicitly says none occurred.
- [ ] For each listed compromise, the final report includes the affected
      artifact, task, criterion, or workflow rule; the accepted risk; the
      mitigation or replacement boundary; and the relevant journal id when
      available.
