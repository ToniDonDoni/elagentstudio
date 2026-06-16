---
name: spec-driven-tdd-implementer
description: "Use when implementing Spec-Driven TDD. The implementer follows the standalone stage procedure, or, in broker mode, asks the broker for the next task and asks the broker to verify completion. The implementer does not know the workflow order in broker mode."
version: 2.0.0
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
artifacts, runs tests, requests independent reviews, updates the journal,
commits, and reports task completion.

The pipeline has two operating modes:

- **Standalone** — the implementer walks the artifact chain directly by
  reading `references/STAGES.md` for the stage-by-stage procedure.
- **Broker** — the implementer does not walk the chain. The implementer
  asks the broker MCP for the next task, executes that task, then asks
  the broker to verify completion. The broker owns the workflow order.

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

The implementer knows only three broker operations. The implementer does
not know the workflow order.

### The three broker operations

1. `init` — start or resume brokered work for a repository.
2. `getNextTask` — ask the broker for the next task, or for `complete` /
   a blocker.
3. `reviewTask` — ask the broker to verify that the current task is
   actually complete.

That is the entire loop. There is no fourth operation.

### What a broker task looks like

A broker task is self-contained. The implementer does not need to read
the workflow order to execute it. A task carries:

```json
{
  "task_id": "B-000001",
  "instruction": "one concrete instruction in natural language",
  "allowed_scope": ["files, paths, or artifacts the task may touch"],
  "required_evidence": [
    "commits, journal ids, reviewer request ids, test commands, or other
     concrete artifacts the broker will check"
  ],
  "independent_review_required": true,
  "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW"
}
```

The implementer follows the `instruction` literally, stays within
`allowed_scope`, produces the items in `required_evidence`, and only
runs the independent reviewer when `independent_review_required` is
true.

The implementer MUST NOT read the broker's `SKILL-ORCHESTRATOR.md` to
figure out the workflow order. The broker decides the order. The
implementer executes the issued task exactly.

### Broker loop

1. Load the shared `spec-driven-tdd` skill, this implementer role file,
   and `references/JOURNAL.md`. Do not load `SKILL-ORCHESTRATOR.md` or
   `references/STAGES.md`.
2. Call broker `init` with `repo_path` and `user_input`. The broker
   returns the first task, `complete`, or a blocker.
3. If the broker returned a task:
   1. Follow the `instruction` exactly, stay within `allowed_scope`,
      and produce every item in `required_evidence`.
   2. If `independent_review_required` is true, call
      `mcp_sddtdd_review_review` with the appropriate `review_type`,
      capture the verdict, journal it as the corresponding
      `*_REVIEW` entry, and commit.
   3. Journal the work as the appropriate `TYPE` for the stage the
      task represents (`USER_INPUT`, `SPEC_SPEC`, `ARCHITECTURE`,
      `DECOMPOSE`, `RED`, `GREEN`, `REGRESSION`, etc.) and commit.
   4. Append a `BROKER_TASK_SUBMITTED` journal entry with `STATUS:
      COMPLETED` and `DETAIL` referencing the broker task id, the
      work journal entry, and the reviewer verdict (if any). Commit.
   5. Call broker `reviewTask` with the task id, a short summary, the
      evidence from `required_evidence`, the reviewer verdict id, the
      `BROKER_TASK_SUBMITTED` journal id, and the head SHA.
4. The broker returns one of:
   - `PASS` — append a `BROKER_TASK_REVIEW` journal entry with
     `STATUS: PASS`, commit, then call `getNextTask` for the next
     task.
   - `FAIL` — append a `BROKER_TASK_REVIEW` journal entry with
     `STATUS: FAIL` and the broker-listed gaps in `DETAIL`, commit,
     fix exactly those gaps, re-run the reviewer if the task requires
     it, re-append `BROKER_TASK_SUBMITTED` for the rework, and call
     `reviewTask` again. Repeat until `PASS`.
   - `NEEDS_CLARIFICATION` — append `BROKER_TASK_REVIEW:
     NEEDS_CLARIFICATION`, commit, ask the user or supply the missing
     information, then continue.
   - `ERROR` — resolve tooling or repository state first.
5. Repeat until `getNextTask` returns `complete` (workflow finished) or
   a blocker.

### Broker task journal chain

The implementer produces this sequence in the journal for every broker
task:

```text
work journal entry
   TYPE = the stage the task represents
   STATUS = COMPLETED

BROKER_TASK_SUBMITTED
   STATUS = COMPLETED
   PARENT = work journal entry
   DETAIL = references broker task id, work entry, reviewer verdict id

independent reviewer verdict (if required by the task)
   TYPE = <review_type>_REVIEW
   STATUS = PASS | FAIL | NEEDS_CLARIFICATION
   PARENT = work journal entry

BROKER_TASK_REVIEW
   STATUS = PASS | FAIL | NEEDS_CLARIFICATION | ERROR
   PARENT = BROKER_TASK_SUBMITTED (and reviewer verdict entry when
            independent review was required)
   DETAIL = broker verdict and findings
```

The next broker task's work entry then has the `BROKER_TASK_REVIEW: PASS`
entry as its `PARENT`.

## Independent review still uses the reviewer MCP

The broker is not a reviewer. When a broker task requires a reviewer
verdict, the implementer calls the reviewer MCP
(`mcp_sddtdd_review_review`) exactly as the shared `spec-driven-tdd`
skill requires, records the verdict in `JOURNAL_SDD_TDD_SKILL.log`,
commits the journal entry, and only then asks the broker to verify the
task.

A reviewer `*_REVIEW: PASS` is **not** the same as a broker
`BROKER_TASK_REVIEW: PASS`. The two chains are independent and both
must succeed.

## Hard rules

- Do not choose the next workflow stage yourself in broker mode. Always
  ask the broker via `getNextTask`.
- Do not skip the broker even if the next artifact "looks obvious" from
  the current state.
- Do not call `getNextTask` for the next task until `reviewTask` for the
  current task returned `PASS`.
- Do not treat a reviewer `PASS` as a broker `reviewTask PASS`; the
  broker must confirm completion.
- Do not execute work outside the broker task's `allowed_scope`.
- Do not let the broker modify files. All repository changes are the
  implementer's responsibility.
- Do not continue when the broker returns `blocked` or `ERROR`; resolve
  the issue first.
- Do not read or follow `SKILL-ORCHESTRATOR.md` as instructions for the
  implementer. That file is for the broker MCP server.

## Verification checklist

- [ ] `spec-driven-tdd` and this implementer role file are loaded.
- [ ] In standalone mode, the stage procedure and journal format are
      loaded.
- [ ] In broker mode, every task came from the broker via `init` or
      `getNextTask`.
- [ ] In broker mode, every completed task produced a
      `BROKER_TASK_SUBMITTED` journal entry, was verified by the broker
      through `reviewTask`, and produced a `BROKER_TASK_REVIEW` journal
      entry.
- [ ] Independent reviews came from the reviewer MCP and were journaled
      and committed before the broker `reviewTask` call.
- [ ] The final report says the broker returned `complete` or describes
      the blocker.
