---
name: spec-driven-tdd-orchestrator
description: "OpenCode orchestrator role for Spec-Driven TDD."
version: 5.3.0-opencode-async
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
3. Verify that the implementer committed the artifact, journal entry, and evidence.
4. Verify clean git status in the relevant worktree.
5. If the worktree is not clean, send the task back to the implementer and require a commit before review.
6. Launch a separate reviewer subagent for that committed artifact or implementation result.
7. Wait for the reviewer to finish.
8. Read the reviewer verdict.
9. If PASS, move to the next stage.
10. If FAIL or NEEDS_CHANGES, launch an implementer again with the review findings.
11. Repeat until PASS, BLOCKED, or user stop.

## Required prompt header

Every subagent prompt must start with:

```text
Use the spec-driven-tdd skill.
You are the implementer|reviewer.
Load exactly these files:
- SKILL.md
- SKILL-IMPLEMENTER.md or SKILL-REVIEWER.md
- ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md
- references/JOURNAL.md
Repo: <repo path>
Worktree: <worktree path>
Branch: <branch>
Task kind: <SPEC|ARCHITECTURE|TASKS|IMPLEMENTATION|MERGE|SPEC_REVIEW|ARCHITECTURE_REVIEW|TASKS_REVIEW|IMPLEMENTATION_REVIEW|MERGE_REVIEW>
Task id: <task id>
Allowed write scope: <paths>
Required output: <paths>
```

For task-specific testing modes, add only the specific extra references needed for that task. Do not add optional references to every subagent by default.

## Committed evidence gate

The orchestrator must not launch a reviewer for uncommitted work.

Before review, run or otherwise verify the equivalent of:

```bash
git status --short
```

The expected result is an empty status for the relevant worktree. If status is not empty, the orchestrator must return the task to the implementer with an instruction to commit all completed artifacts, journal entries, and evidence using an ASCII-only commit message.

## Planning stages

SPEC, ARCHITECTURE, and TASKS are synchronous implementer tasks. The implementer creates the artifact, appends journal evidence, and commits both before reporting completion.

SPEC_REVIEW, ARCHITECTURE_REVIEW, and TASKS_REVIEW are synchronous reviewer tasks. The reviewer inspects committed artifacts and committed evidence.

## Code implementation

After TASKS.md is reviewed, launch code implementation as background implementer tasks. Record every returned task_id or jobId in `.sddtdd_skill/async-tasks.jsonl` immediately.

Use `task_status` to check progress. Do not infer progress from report files.

## Code review

When a background implementer completes, verify committed evidence and clean git status, then launch exactly one background reviewer for that implementer result.

## Merge

Merge is sequential. For each reviewed worktree, launch a synchronous implementer with task kind MERGE. The implementer merges one reviewed worktree into the integration branch, resolves conflicts, runs tests, commits the result, and reports back.

If merge review is required, verify committed merge evidence and clean git status, then launch a synchronous reviewer with task kind MERGE_REVIEW.
