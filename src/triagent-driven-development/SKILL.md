---
name: triagent-driven-development
description: Execute implementation work through builder and reviewer triagents with bounded review loops.
license: MIT
compatibility: opencode
metadata:
  workflow: triagent
  review: required
---

## When to use

Use this skill when the task is large enough to benefit from delegation and explicit review gates.

Prefer this flow for feature work, small prototypes, and refactors where you want the primary agent to coordinate instead of editing directly.

## Core rules

1. The primary agent routes. It does not implement code itself.
2. Read the user request once and pass the task to the builder.
3. Use fresh subagent sessions through the `task` tool.
4. Run review after each implementation pass.
5. Keep revision loops bounded. Stop after 3 failed review cycles and escalate.

## Flow

### 1. Dispatch

Pass the user task directly to the builder. The builder may refine scope, choose files, and decide practical verification as part of implementation.

### 2. Implement

For the task, call:

- `task({ subagent_type: "trdd-builder", ... })`

Give the builder the full task text and any constraints already known in the parent session.

### 3. Review

After each implementation pass, call:

- `task({ subagent_type: "trdd-reviewer", ... })`

Require a strict verdict:

- `VERDICT: APPROVED`
- `VERDICT: REQUEST_CHANGES`

Require concrete findings tied to the task spec, behavior, or code quality.

### 4. Rework

If the reviewer returns `REQUEST_CHANGES`, send only the review findings and the original task back to:

- `task({ subagent_type: "trdd-builder", task_id?: previous_builder_session, ... })`

Then re-run the reviewer.

### 5. Finish

Only accept the task when the reviewer returns `APPROVED`.

At the end, summarize:

- completed tasks
- review cycles per task
- verification that ran
- remaining risks, if any

## Gates

### Pre-flight gate

Do not dispatch implementation until the user task and any known constraints are captured clearly enough for the builder to act.

### Revision gate

Do not move to the next task while review findings are still open.

### Escalation gate

Stop and escalate when:

- the same issue repeats
- requirements conflict
- the builder cannot complete verification

### Abort gate

Abort the loop when 3 review cycles fail to converge for the same task.

## Context discipline

- Keep prompts short and explicit.
- Pass task text directly instead of telling subagents to read large docs.
- Give the reviewer the task spec and the implementation result together.
- Do not re-read this skill unless the workflow becomes ambiguous.
