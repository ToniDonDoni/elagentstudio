---
name: spec-driven-tdd-implementer
description: "Use when implementing Spec-Driven TDD through an MCP task broker. The implementer only asks the broker for the next task and asks the broker to review a completed task. The implementer does not know the workflow stage order."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, mcp, task-broker, implementer]
    related_skills: [spec-driven-tdd]
---

# Spec-Driven TDD Implementer Role

## Overview

This role file is the implementer-side contract for Spec-Driven TDD broker mode.

The implementer performs the work. The implementer does **not** know or choose the workflow stage order. A task broker MCP server reads the repository state and the SDDTDD journal, decides what the next permitted task is, and verifies whether the implementer actually completed it.

The point of the broker is exactly to stop the implementer from cutting corners: the implementer cannot decide on its own that "this step is obvious, let's skip review" or "the next artifact is clearly X". It must always ask the broker.

The implementer does **not** read the orchestrator role file as instructions for itself. That file exists so the broker MCP server can reason about the workflow independently.

## What the implementer must do

The implementer only needs to know how to drive a broker. That is it.

There are exactly three broker operations the implementer uses:

1. `init` — start (or resume) brokered work for a repository.
2. `getNextTask` — ask the broker for the next task to work on, or for `complete` / a blocker.
3. `reviewTask` — when the implementer thinks the current task is done, ask the broker to verify it.

That is the entire loop. There is no fourth operation the implementer needs to know about.

## Telling the broker who it is

On every call, the implementer MUST pass the broker three things and a
plain instruction in natural language:

- `process_skill: "spec-driven-tdd"`
- `implementer_skill: "skills/spec-driven-tdd/SKILL-IMPLEMENTER.md"`
- `broker_skill: "skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md"`
- a short instruction along the lines of:

```text
Read the broker skill I gave you. You are the broker. Act according to it.
Use the spec-driven-tdd process skill and this orchestrator role file to
decide. Do not implement, review, or edit files.
```

This is how the broker knows it is the broker: the implementer hands it the
`SKILL-ORCHESTRATOR.md` file and tells it to read it. The orchestrator role
file, in turn, tells the broker that it owns the workflow order and the
review rules, and that the implementer must not be exposed to the internal
stage type.

If the broker cannot resolve `broker_skill` to a real file under the
repository, the call is a hard error and the implementer stops and reports
the missing skill to the user.

## Required skill files

The implementer must load the shared process skill and this implementer role file. Nothing else.

- `skills/spec-driven-tdd/SKILL.md` — shared process and artifact contract.
- `skills/spec-driven-tdd/SKILL-IMPLEMENTER.md` — this file, the implementer-side broker loop.

The implementer does **not** read `SKILL-ORCHESTRATOR.md` as instructions for itself. It only forwards that file to the broker.

## Broker loop

1. Load the shared `spec-driven-tdd` skill and this implementer role file.
2. Call broker `init` with:
   - `repo_path: "/absolute/path/to/repo"`
   - `user_input: "<original user request>"`
   - `process_skill: "spec-driven-tdd"`
   - `implementer_skill: "skills/spec-driven-tdd/SKILL-IMPLEMENTER.md"`
   - `broker_skill: "skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md"`
   - `instruction: "Read the broker skill I gave you. You are the broker. ..."`
   
   The broker returns the first task, `complete`, or a blocker.
3. If the broker returned a task: do exactly what the task says, following the shared `spec-driven-tdd` process for the kind of work the task describes (artifacts, tests, journal entries, reviews, commits).
4. When the work is done, append a `BROKER_TASK_REVIEW` journal entry to `JOURNAL_SDD_TDD_SKILL.log` with `STATUS: COMPLETED` and commit the journal update.
5. Call broker `reviewTask` with the same `process_skill`, `implementer_skill`, `broker_skill`, and `instruction` fields, plus the task id, a short summary, and the concrete evidence (commits, journal ids, reviewer request ids, test commands) required to prove the work.
6. The broker returns one of:
   - `PASS` — record `BROKER_TASK_REVIEW: PASS` in the journal, commit it, then call `getNextTask` (with the same skill/instruction fields) for the next task.
   - `FAIL` — record `BROKER_TASK_REVIEW: FAIL` in the journal with the broker-listed gaps in `DETAIL`, commit it, fix exactly those gaps, re-run the reviewer if the task requires it, then call `reviewTask` again. Repeat until `PASS`.
   - `NEEDS_CLARIFICATION` — record `BROKER_TASK_REVIEW: NEEDS_CLARIFICATION`, commit it, ask the user or supply the missing information, then continue.
   - `ERROR` — resolve the tooling or repository state first.
7. Repeat until `getNextTask` returns `complete` (workflow finished) or a blocker.

## Review still uses the reviewer MCP

The task broker is not a reviewer. When a task requires review, the implementer calls the reviewer MCP (`mcp_sddtdd_review_review`) exactly as the shared `spec-driven-tdd` skill requires, records the verdict in `JOURNAL_SDD_TDD_SKILL.log`, commits the journal entry, and only then asks the broker to review the task.

A reviewer `PASS` is **not** the same as a broker `reviewTask PASS`. The implementer must still call `reviewTask` and let the broker confirm that all required evidence (including the journaled review) is committed.

## Hard rules

- Do not choose the next workflow stage yourself. Always ask the broker via `getNextTask`.
- Do not skip the broker even if the next artifact "looks obvious" from the current state.
- Do not call `getNextTask` for the next task until `reviewTask` for the current task returned `PASS`.
- Do not treat a reviewer `PASS` as a broker `reviewTask PASS`; the broker must confirm completion.
- Do not let the broker modify files. All repository changes are the implementer's responsibility.
- Do not continue when the broker returns `blocked` or `ERROR`; resolve the issue first.
- Do not read or follow `SKILL-ORCHESTRATOR.md` as instructions for the implementer. That file is for the broker MCP server.

## Verification checklist

- [ ] `spec-driven-tdd` and this implementer role file are loaded.
- [ ] Every task came from the broker via `init` or `getNextTask`.
- [ ] Every completed task was confirmed by the broker via `reviewTask`.
- [ ] Independent reviews came from the reviewer MCP and were journaled and committed before `reviewTask`.
- [ ] The final report says the broker returned `complete` or describes the blocker.
