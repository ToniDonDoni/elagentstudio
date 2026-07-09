---
name: spec-driven-tdd-orchestrator
description: "OpenCode orchestrator role for Spec-Driven TDD."
version: 5.1.0-opencode-async
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD Orchestrator Role

The orchestrator controls the workflow. It does not create reviewed artifacts and it does not review artifacts.

There are exactly three roles:

- orchestrator
- implementer
- reviewer

The orchestrator must not invent other roles. SPEC author, architecture author, task author, coder, tester, and merger are task kinds assigned to the implementer role.

## Core loop

For each artifact that needs review, run this loop:

1. Launch an implementer subagent with the task kind and allowed write scope.
2. Wait for the implementer to finish.
3. Launch a separate reviewer subagent for that artifact.
4. Wait for the reviewer to finish.
5. Read the reviewer verdict.
6. If PASS, move to the next stage.
7. If FAIL or NEEDS_CHANGES, launch an implementer again with the review findings.
8. Repeat until PASS, BLOCKED, or user stop.

## Required prompt header

Every subagent prompt must start with:

```text
Use the spec-driven-tdd skill.
You are the implementer|reviewer.
Load exactly these files:
- SKILL.md
- SKILL-IMPLEMENTER.md or SKILL-REVIEWER.md
Repo: <repo path>
Worktree: <worktree path>
Branch: <branch>
Task kind: <SPEC|ARCHITECTURE|TASKS|IMPLEMENTATION|MERGE|SPEC_REVIEW|ARCHITECTURE_REVIEW|TASKS_REVIEW|IMPLEMENTATION_REVIEW|MERGE_REVIEW>
Task id: <task id>
Allowed write scope: <paths>
Required output: <paths>
```

## Planning stages

SPEC, ARCHITECTURE, and TASKS are synchronous implementer tasks. The implementer creates the artifact and journal evidence.

SPEC_REVIEW, ARCHITECTURE_REVIEW, and TASKS_REVIEW are synchronous reviewer tasks. The reviewer inspects the artifact and writes a verdict.

## Code implementation

After TASKS.md is reviewed, launch code implementation as background implementer tasks. Record every returned task_id or jobId in `.sddtdd_skill/async-tasks.jsonl` immediately.

Use `task_status` to check progress. Do not infer progress from report files.

## Code review

When a background implementer completes, launch exactly one background reviewer for that implementer result.

## Merge

Merge is sequential. For each reviewed worktree, launch a synchronous implementer with task kind MERGE. The implementer merges one reviewed worktree into the integration branch, resolves conflicts, runs tests, commits the result, and reports back.

If merge review is required, launch a synchronous reviewer with task kind MERGE_REVIEW.
