---
name: sddtdd-broker-implementer
description: "Use when implementing Spec-Driven TDD through an MCP task broker. The implementer asks the broker for initialization, verification, and next-task decisions instead of self-selecting workflow stages."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, mcp, task-broker, implementer]
    related_skills: [spec-driven-tdd, sddtdd-task-broker]
---

# SDDTDD Broker Implementer

## Overview

This skill is the implementer-side contract for Spec-Driven TDD broker mode.
The implementer still performs the work: writing artifacts, running tests,
requesting independent review, updating the journal, and committing changes.
The implementer does **not** decide which workflow stage comes next. A task
broker MCP server reads the repository state and returns the next permitted
task.

The goal is to prevent shortcutting. The implementer executes only the broker
task currently assigned, reports the result, and asks the broker for the next
task after the required evidence is committed.

## When to Use

Use this skill when:

- the user asks for Spec-Driven TDD with a task broker;
- an MCP server exposes task-broker tools for SDDTDD;
- the primary `spec-driven-tdd` skill says broker mode is active;
- the implementer is tempted to infer or skip the next stage.

Do not use this skill when no task-broker MCP server exists. In that case, use
`spec-driven-tdd` directly and record any deviation explicitly.

## Required Skills

The implementer MUST load both:

- `spec-driven-tdd` — shared process and artifact contract;
- `sddtdd-broker-implementer` — this implementer-side MCP loop.

The implementer MUST NOT load `sddtdd-task-broker` as executable instructions for
itself. That skill is supplied to the broker MCP server so the broker can decide
tasks independently.

## MCP Tool Contract

The broker MCP server is expected to provide three logical operations. Tool names
may be prefixed by the MCP integration, but their semantics must match this
contract.

### `init_task`

Starts or resumes brokered work for a repository.

Input:

```json
{
  "repo_path": "/absolute/path/to/repo",
  "user_input": "original user request or a pointer to it",
  "implementer_skill": "sddtdd-broker-implementer",
  "broker_skill": "sddtdd-task-broker",
  "process_skill": "spec-driven-tdd"
}
```

Output:

```json
{
  "status": "TASK",
  "task_id": "broker-assigned id",
  "kind": "INITIALIZE | CREATE_ARTIFACT | REQUEST_REVIEW | FIX_ARTIFACT | RUN_TESTS | UPDATE_JOURNAL | COMMIT | ASK_USER | DONE_CHECK",
  "summary": "what to do now",
  "allowed_actions": ["explicit action list"],
  "required_evidence": ["paths, commands, review verdicts, or commits expected before verification"],
  "blocking_conditions": ["conditions that forbid starting this task"],
  "journal_parent": "required existing JID or null"
}
```

### `verify_task`

Checks whether the current broker task is actually complete.

Input:

```json
{
  "repo_path": "/absolute/path/to/repo",
  "task_id": "broker-assigned id",
  "claimed_result": "brief implementer summary",
  "evidence": ["commit hashes", "journal entries", "test commands", "review request ids"]
}
```

Output statuses:

- `PASS` — the broker accepts completion; ask for `next_task`;
- `FAIL` — fix only the listed gaps, then call `verify_task` again;
- `NEEDS_CLARIFICATION` — ask the user or provide missing evidence;
- `ERROR` — resolve tooling or repository state before continuing.

### `next_task`

Returns the next allowed task after a verified task.

Input:

```json
{
  "repo_path": "/absolute/path/to/repo",
  "previous_task_id": "broker-assigned id returned by the verified task"
}
```

Output statuses:

- `TASK` — execute the returned task exactly;
- `DONE` — no more tasks remain; prepare the final user report;
- `BLOCKED` — stop and report the blocker;
- `ERROR` — resolve tooling or repository state before continuing.

## Implementer Loop

1. Load `spec-driven-tdd` and this skill.
2. Call broker `init_task` with the repository path and user input.
3. Execute only the returned task's `allowed_actions`.
4. Commit every required artifact and journal update before verification when
   the task requires committed evidence.
5. Call `verify_task` with concrete evidence.
6. If verification fails, fix only the broker-listed gaps and verify again.
7. After verification passes, call `next_task`.
8. Repeat until the broker returns `DONE` or `BLOCKED`.

## Review Still Uses the Reviewer MCP

The task broker does not review artifacts. When a broker task requires review,
the implementer calls `mcp_sddtdd_review_review` exactly as required by
`spec-driven-tdd`, records the reviewer verdict in `JOURNAL_SDD_TDD_SKILL.log`,
and commits the journal update before reporting completion to the broker.

## Hard Rules

- Do not choose the next workflow stage yourself in broker mode.
- Do not execute work that is outside the broker task's `allowed_actions`.
- Do not treat a broker `PASS` as an independent review `PASS`.
- Do not treat reviewer `PASS` as broker task completion until the journal entry
  is written and committed.
- Do not ask `next_task` until `verify_task` returns `PASS`.
- Do not let the broker modify files; all repository changes are implementer
  responsibility.
- Do not continue when the broker returns `BLOCKED`, `ERROR`, or
  `NEEDS_CLARIFICATION`; resolve the blocker first.

## Verification Checklist

- [ ] `spec-driven-tdd` and this skill are loaded.
- [ ] Every task came from the broker MCP server.
- [ ] Every completed task was verified through `verify_task`.
- [ ] Independent reviews still came from `mcp_sddtdd_review_review`.
- [ ] Review verdicts were journaled and committed before later work.
- [ ] The final report includes broker `DONE` or a clear blocker.
