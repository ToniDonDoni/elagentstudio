---
name: spec-driven-tdd-orchestrator
description: "Use inside the MCP task broker for Spec-Driven TDD. The orchestrator owns the workflow order and performs process-gate verification on reviewTask. It does not sample an LLM; the broker itself reads the committed journal and decides."
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

The orchestrator is a state-machine gate over the Spec-Driven TDD
workflow. It owns the workflow order and the broker-level process-gate
verification. It does not sample an LLM; the broker itself reads the
committed repository state and the committed journal, and decides
directly in Python according to the rules defined here.

The orchestrator performs process-gate review, but does not replace
`mcp_sddtdd_review_review` and does not independently re-review
artifacts. The independent reviewer has already evaluated the
artifact's correctness; the broker's job is to verify that the issued
workflow step has produced all evidence and approvals required to
permit the next workflow step.

## What the broker does and does not do

The broker:

- chooses the next workflow task;
- performs process-gate verification of the previous task;
- reads the committed journal and committed artifacts to do so;
- writes an access log of every verification call.

The broker does not:

- implement, write code, write tests, or write artifacts;
- perform the independent artifact review that belongs to
  `mcp_sddtdd_review_review`;
- judge whether the artifact's content is correct, idiomatic,
  well-designed, or appropriate — that is the reviewer's responsibility;
- sample an LLM to make process-gate decisions;
- modify the journal itself. The implementer writes the journal.

## Two tools

The broker exposes exactly two tools. There is no `init`.

### `getNextTask`

The first call to `getNextTask` carries `user_input` and creates or
resumes a delivery. Subsequent calls carry `previous_task_id`. The
broker returns one of three shapes:

- `TASK` — one self-contained next task.
- `complete` — all required SDDTDD completion conditions are
  satisfied.
- `blocked` — no workflow task can proceed right now.

```json
{
  "status": "TASK",
  "task_id": "B-000001",
  "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
  "instruction": "one concrete instruction in natural language",
  "allowed_scope": ["files, paths, or artifacts the task may touch"],
  "required_evidence": [
    "commits, journal ids, reviewer request ids, test commands, or
     other concrete artifacts the implementer must produce"
  ],
  "independent_review_required": true,
  "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
  "rationale": "why this is the next legal task"
}
```

`task_kind` is the workflow stage the implementer is being asked to
execute. `review_type` is the type of independent reviewer verdict the
implementer must obtain and journal; it is `null` (or absent) when the
task does not require independent review, e.g. capture tasks for
`USER_INPUT_CAPTURE`.

### `reviewTask`

`reviewTask` performs process-gate verification. The broker itself
reads the committed journal, the issued `task_kind`, the claimed
`work_journal_id`, and the `review_journal_id` when one is required,
and decides whether the issued step is process-complete.

Input:

```json
{
  "repo_path": "/absolute/path/to/repo",
  "task_id": "broker-assigned id being verified",
  "task_kind": "the same task_kind that was issued by getNextTask",
  "review_type": "the same review_type that was issued (null when not required)",
  "claimed_result": "brief implementer summary",
  "work_journal_id": "JID of the work journal entry the implementer just committed",
  "evidence": {
    "review_journal_id": "JID of the reviewer verdict journal entry (when required)",
    "commits": ["..."],
    "journal_ids": ["..."],
    "files": ["..."],
    "test_commands": ["..."]
  }
}
```

Output statuses:

- `PASS` — the issued step is process-complete; the implementer may
  call `getNextTask` again.
- `FAIL` — the listed findings must be fixed and `reviewTask` called
  again.
- `NEEDS_CLARIFICATION` — the implementer or user must supply
  information that cannot be derived from committed state.
- `ERROR` — repository or tooling state must be resolved before
  continuing.

```json
{
  "status": "PASS | FAIL | NEEDS_CLARIFICATION | ERROR",
  "task_id": "B-000001",
  "findings": ["specific gaps or confirmations"]
}
```

## Workflow order

The orchestrator picks the earliest unmet mandatory condition in the
workflow. Existing artifacts and reviewer verdicts count only when they
are journaled and committed.

The order is:

```text
USER_INPUT_CAPTURE (no reviewer; creates .sddtdd_skill/SPEC-DRAFT.md and the USER_INPUT journal entry)
→ SPEC_SPEC
→ SPEC_REVIEW          (independent reviewer)
→ ARCHITECTURE
→ ARCHITECTURE_REVIEW
→ DECOMPOSE
→ TASK_REVIEW
→ per task: RED → RED_REVIEW → GREEN → GREEN_REVIEW
→ TASKS_COMPLETE
→ REGRESSION
→ REGRESSION_REVIEW
→ FINAL_REVIEW
→ DONE
```

Capture tasks (`USER_INPUT_CAPTURE`) are exempt from
`independent_review_required`. For those, `review_type` is `null` and
the broker does not require a reviewer verdict.

Acceptance-changing compromises introduce corrective workflow work before
normal completion. When the committed journal contains an `AGENT_DECISION`
that changes, weakens, replaces, or reinterprets an acceptance criterion,
user-visible behavior, user-observable evidence, or required test boundary,
the broker MUST require corrective follow-up tasks before `DONE`. These
corrective tasks use the existing task kinds (`ARCHITECTURE`, `DECOMPOSE`,
`RED`, `GREEN`, `REGRESSION`, and `FINAL`) with corrective instructions; the
broker does not invent a new stage type.

The stage procedure is defined in `references/STAGES.md` and is the
same procedure the broker enforces.

## Mapping: task_kind → required reviewer verdict

The broker does not decide this dynamically. The mapping is fixed by
this file:

| `task_kind` | required `review_type` | prerequisites in the journal | required artifacts |
|---|---|---|---|
| `USER_INPUT_CAPTURE` | (none) | — | `.sddtdd_skill/SPEC-DRAFT.md` |
| `SPEC_SPEC` | `SPEC_REVIEW` | — | `.sddtdd_skill/SPEC.md` |
| `ARCHITECTURE` | `ARCHITECTURE_REVIEW` | `SPEC_REVIEW` | `.sddtdd_skill/ARCHITECTURE.md` |
| `DECOMPOSE` | `TASK_REVIEW` | `SPEC_REVIEW`, `ARCHITECTURE_REVIEW` | `.sddtdd_skill/TASKS.md` |
| `RED` | `RED_REVIEW` | `SPEC_REVIEW`, `ARCHITECTURE_REVIEW`, `TASK_REVIEW` | — |
| `GREEN` | `GREEN_REVIEW` | `RED_REVIEW` (and the chain above) | — |
| `TASKS_COMPLETE` | (none) | `GREEN_REVIEW` (and the chain above) | — |
| `REGRESSION` | `REGRESSION_REVIEW` | `TASKS_COMPLETE` (and the chain above) | — |
| `FINAL` | `FINAL_REVIEW` | `REGRESSION_REVIEW` (and the chain above) | — |
| `DONE` | (none) | all of the above | — |

`DONE` itself is a journal entry with `STATUS: COMPLETED`. The broker
treats it as process-complete when all required prior reviews have
passed and the `DONE` entry exists.

## Acceptance-changing compromise remediation

A committed `AGENT_DECISION` is a transparency and audit mechanism, not a
permanent waiver. When the broker sees, in the committed journal or in the
verified task evidence, an `AGENT_DECISION` that changes, weakens, replaces,
or reinterprets an acceptance criterion, user-visible behavior,
user-observable evidence, or required test boundary, the broker MUST treat the
delivery as carrying unresolved corrective work unless the journal also proves
that the user or owner explicitly accepted the changed acceptance contract as
final.

The broker MUST distinguish two cases:

1. **Minor technical compromise.** The compromise is journaled, but it does
   not change the acceptance contract, user-visible behavior,
   user-observable evidence, or required test boundary. The broker may allow
   normal forward progress after the required `AGENT_DECISION` exists.
2. **Major acceptance change.** The compromise changes, weakens, replaces, or
   reinterprets an acceptance criterion, user-visible behavior,
   user-observable evidence, or required test boundary. The broker MUST
   require user/owner notification and MUST schedule corrective work before
   `DONE`, unless the journal explicitly records user/owner acceptance of the
   changed contract as final.

For a major acceptance change, the broker MUST prefer restoring the original
acceptance contract over normalizing the compromise. The corrective sequence
MUST include, as applicable:

1. an `ARCHITECTURE` correction task to revise the architecture so the
   affected acceptance criteria can be satisfied without weakening the user
   contract;
2. a `DECOMPOSE` correction task to update `.sddtdd_skill/TASKS.md` with the
   implementation and test-remediation work required by the corrected
   architecture;
3. one or more `RED` remediation tasks to replace compromised tests with tests
   matching the corrected architecture and required acceptance boundary;
4. corresponding `GREEN` work and independent reviews for the corrected
   architecture, task decomposition, RED evidence, and implementation;
5. `REGRESSION` and `FINAL` verification that explicitly report the
   compromise history and the corrective work performed.

The broker MUST NOT issue `DONE` while an unresolved major acceptance change
exists. A major acceptance change is resolved only when one of the following is
true in the committed journal:

- corrective architecture, task decomposition, RED, GREEN, regression, and
  final-review work has restored the affected acceptance boundary; or
- the user/owner explicitly accepted the changed acceptance contract as final,
  and the final report includes the required major-compromise disclosure.

If the broker cannot determine from the committed journal whether an
`AGENT_DECISION` is minor or major, whether user/owner notification happened,
or whether corrective work has resolved the issue, it MUST return
`NEEDS_CLARIFICATION` instead of issuing the next normal workflow task.

## Process-gate verification rules

The broker applies the following checks in order. If any check fails,
the broker returns `FAIL` with the specific findings.

1. **Working tree is clean.** The broker only verifies committed
   state. If `git status --porcelain` is non-empty, the broker
   returns `FAIL` and tells the implementer to commit first.
2. **`head_sha_before` is known.** The broker records the
   `HEAD` SHA at the start of `reviewTask` and reads the committed
   journal from that exact commit for the rest of the call. This
   means the implementer cannot commit additional journal entries
   or verdict JIDs after the broker started verification and then
   re-ask for a PASS.
3. **Stage-required artifacts exist at `head_sha_before`.** For
   document-producing stages, the broker verifies the artifact the
   reviewer allegedly reviewed actually exists in the committed tree:
   - `USER_INPUT_CAPTURE` requires `.sddtdd_skill/SPEC-DRAFT.md`.
   - `SPEC_SPEC` requires `.sddtdd_skill/SPEC.md`.
   - `ARCHITECTURE` requires `.sddtdd_skill/ARCHITECTURE.md`.
   - `DECOMPOSE` requires `.sddtdd_skill/TASKS.md`.
   For code-producing stages (`RED`, `GREEN`, `REGRESSION`, `FINAL`,
   `DONE`) the broker does not check artifact existence — the broker
   does not decide which code files belong to a task, the reviewer
   does.
4. **Committed journal exists at `head_sha_before`.**
   `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log` must exist at the recorded ref. If
   not, the broker returns `ERROR`.
5. **`work_journal_id` exists in the committed journal.** The
   implementer must commit the work journal entry for the issued
   `task_kind` before calling `reviewTask`. If the JID is not found,
   the broker returns `FAIL`.
6. **Work entry has `STATUS: COMPLETED`.** Anything else means the
   implementer is asking the broker to verify work that the
   implementer itself has not marked complete.
7. **Stage prerequisites exist in the journal.** For each entry in the
   stage's prerequisite list — currently:
   - `GREEN` requires `RED_REVIEW: PASS` to already be in the committed
     journal.
   - `TASKS_COMPLETE` requires `GREEN_REVIEW: PASS` to already be in the
     committed journal.
   - `REGRESSION` requires `TASKS_COMPLETE: COMPLETED` to already be in
     the committed journal.
   - `FINAL` requires `REGRESSION_REVIEW: PASS` to already be in the
     committed journal.

   This is the process-order check. The broker generalises the rule
   to "any prerequisite `(TYPE, STATUS)` pair must be present in the
   committed journal before the issued stage can be verified"; the
   concrete list lives in the `STAGE_PREREQUISITES` table in
   `server.py` and is the source of truth, this rule names the
   current entries.
8. **Required reviewer verdict exists and is `PASS`.** When the
   issued `review_type` is non-null, the broker requires a
   reviewer-verdict journal entry whose `TYPE` matches the issued
   `review_type` and whose `STATUS` is `PASS`. The implementer
   supplies the JID of that entry as `evidence.review_journal_id`.
9. **Reviewer verdict is bound to the work entry of this task.**
   The reviewer verdict's `PARENT` JID must equal the
   `work_journal_id` of the task being verified. The broker rejects
   reviewer verdicts whose `PARENT` points to a different work entry
   or that have no `PARENT` at all. This catches a implementer that
   reuses an old `PASS` verdict from a previous task.
10. **Reviewer verdict's `PARENT` resolves in the journal.** The
    reviewer verdict's `PARENT` JID is also required to be present in
    the committed journal. This catches a guessed or fabricated
    `PARENT`.
11. **No outstanding unverified broker tasks (`getNextTask` gate).**
    Before the broker hands out the next task on `getNextTask`, it
    checks that every broker task id it has previously issued in this
    delivery has a corresponding committed `BROKER_TASK_REVIEW:
    PASS` journal entry whose `TASK_ID` matches. The broker
    identifies issued task ids from the broker access log
    (`<repo>/.sddtdd_skill/broker-access.jsonl`), and identifies
    verified task ids from committed journal entries of
    `TYPE: BROKER_TASK_REVIEW, STATUS: PASS`. If any issued task id
    is still unverified, the broker returns `status: "blocked"`
    with a `required_action` naming the outstanding task id(s) and
    instructing the implementer to call `reviewTask` and commit the
    matching `BROKER_TASK_REVIEW: PASS` entry first. This is the
    process gate that catches the implementer that does the work,
    skips `reviewTask`, and asks for the next task anyway.
12. **Acceptance-changing compromises are not silently normalized.** If the
    committed journal contains an unresolved major acceptance change as
    defined in `Acceptance-changing compromise remediation`, the broker must
    either issue the required corrective task sequence or return
    `NEEDS_CLARIFICATION`. The broker must not verify `DONE` and must not let
    ordinary forward progress hide the compromised acceptance boundary.

The broker does not check:

- whether the implementation satisfies the instruction (reviewer's job);
- whether the changes are within `allowed_scope` (reviewer's job);
- whether unrelated work was added (reviewer's job);
- whether tests are valid RED (reviewer's job);
- whether architecture decisions are good (reviewer's job);
- whether a compromise is technically acceptable as a product decision
  (user/owner and reviewer responsibility);
- which source files belong to a given code task (reviewer's job).

The broker does check the **process state**: are the right reviewer
verdicts in the right place with the right status, in the right
order, with the right parent chain pointing at the right work
entry, in the committed journal at the broker-recorded ref, on a
clean working tree, with the right artifacts in the tree; and, when
journaled compromises exist, whether required user/owner notification and
corrective follow-up tasks are present before completion.

## Broker access log

The broker writes every `reviewTask` call to an append-only access log:

```text
<repo>/.sddtdd_skill/broker-access.jsonl
```

Each call produces two events:

- `task_review_started` — written at the start of `reviewTask`,
  containing the request id, the broker task id, the committed `HEAD`
  SHA before, and the arguments the implementer passed.
- `task_review_completed` — written at the end, containing the
  request id, the broker task id, the `HEAD` SHA before and after,
  the verdict, the findings, and the duration in milliseconds.

The broker writes both events for every `reviewTask` call, including
`FAIL`, `NEEDS_CLARIFICATION`, and `ERROR`. The implementer does not
need to look at this log; the broker uses it for investigation.

## Independence rules

- Do not modify repository files.
- Do not run implementation commands.
- Do not perform the independent artifact review that belongs to
  `mcp_sddtdd_review_review`. The implementer must call the reviewer
  MCP.
- Do not sample an LLM to make process-gate decisions. The process
  rules are explicit and are enforced in code.
- Do not issue multi-stage tasks; return exactly one next task.
- Do not infer a `PASS` from artifact presence. Only journaled
  reviewer `PASS` plus a correctly-built journal chain justify a
  broker `PASS`.
- Do not create JIDs or task IDs for the implementer except
  orchestrator-local task IDs such as `B-000001`. Required journal
  parents must be copied from existing journal entries.
- Do not expose the internal stage type to the implementer beyond the
  `task_kind` field on the broker task itself. The implementer loop
  is intentionally simple: `getNextTask` → work → reviewer (if
  required) → `reviewTask` → `getNextTask`.

## Verification checklist

- [ ] The response is JSON only.
- [ ] `getNextTask` returns exactly one of `TASK`, `complete`, or
     `blocked`. The `blocked` shape can come from either of two
     conditions: the implementer did not provide `user_input` for a
     fresh delivery, or there are outstanding unverified broker task
     ids (rule 11).
- [ ] When `getNextTask` returns `blocked` because of rule 11, the
     `unverified_task_ids` field names the outstanding broker task
     id(s) the implementer must verify before the broker will issue
     the next task.
- [ ] `reviewTask` returns exactly one of `PASS`, `FAIL`,
      `NEEDS_CLARIFICATION`, `ERROR`.
- [ ] `TASK` carries `task_id`, `task_kind`, `instruction`,
      `allowed_scope`, `required_evidence`,
      `independent_review_required`, `review_type`.
- [ ] `review_type` is `null` for capture tasks (`USER_INPUT_CAPTURE`).
- [ ] The emitted task is the earliest unmet mandatory workflow
      condition.
- [ ] No task authorizes work based on uncommitted or unjournaled
      evidence.
- [ ] The rationale names the journal state that made the task legal.
- [ ] Both `task_review_started` and `task_review_completed` were
      written to `broker-access.jsonl` for the call.
- [ ] If a journaled `AGENT_DECISION` changes, weakens, replaces, or
      reinterprets an acceptance criterion, user-visible behavior,
      user-observable evidence, or required test boundary, the broker does not
      issue `DONE` until corrective work restores the acceptance boundary or
      the journal records explicit user/owner acceptance of the changed
      contract as final.
- [ ] Major acceptance changes cause corrective `ARCHITECTURE`, `DECOMPOSE`,
      `RED`, `GREEN`, `REGRESSION`, and `FINAL` work as applicable, rather
      than being treated as ordinary forward progress.
- [ ] If the broker cannot determine whether a compromise is minor or major,
      notified or unnotified, resolved or unresolved, it returns
      `NEEDS_CLARIFICATION`.
