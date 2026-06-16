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

## Required skill files

The implementer must load the shared process skill and this implementer role file. Nothing else.

- `skills/spec-driven-tdd/SKILL.md` — shared process and artifact contract.
- `skills/spec-driven-tdd/SKILL-IMPLEMENTER.md` — this file, the implementer-side broker loop.

The implementer does **not** read `SKILL-ORCHESTRATOR.md` as instructions for itself.

## Broker loop

1. Load the shared `spec-driven-tdd` skill and this implementer role file.
2. Call broker `init` with the repository path and the original user request. The broker returns the first task, `complete`, or a blocker.
3. If the broker returned a task: do exactly what the task says, following the shared `spec-driven-tdd` process for the kind of work the task describes (artifacts, tests, journal entries, reviews, commits).
4. When the task is done, call broker `reviewTask` with the task id, a short summary of what was done, and the concrete evidence (commits, journal ids, review verdicts, test commands) required to prove it.
5. If `reviewTask` returns `PASS`, call `getNextTask` to get the next task. If it returns anything else, follow what it says: fix the listed gaps and re-ask, ask the user, or stop on a blocker.
6. Repeat until `getNextTask` returns `complete` (workflow finished) or a blocker.

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
