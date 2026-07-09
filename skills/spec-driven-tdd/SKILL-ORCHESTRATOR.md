---
name: spec-driven-tdd-orchestrator
description: "OpenCode Agent Orchestrator policy for Spec-Driven TDD."
version: 5.0.1-opencode-async
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD Orchestrator Policy

## Purpose

The orchestrator is a control plane. It does not author reviewed artifacts and it does not act as reviewer.

It coordinates OpenCode subagents:

- synchronous artifact author subagents for SPEC-DRAFT, SPEC, ARCHITECTURE, and TASKS
- synchronous reviewer subagents for SPEC_REVIEW, ARCHITECTURE_REVIEW, and TASK_REVIEW
- background implementer subagents for implementation work
- background reviewer subagents for completed implementation work
- synchronous merger subagents for reviewed worktree merges

## Hard prohibition

The orchestrator must not write SPEC.md, ARCHITECTURE.md, or TASKS.md itself.

The orchestrator must not ask the user to review an artifact unless the user explicitly says they are acting as reviewer.

For every reviewed artifact, the orchestrator must run this loop:

1. Launch an author subagent with the exact role and role file.
2. Wait for the author subagent to finish.
3. Launch a separate reviewer subagent with the exact role and role file.
4. Wait for the reviewer subagent to finish.
5. Read the reviewer result.
6. If PASS, commit or verify the journal evidence and move forward.
7. If FAIL or NEEDS_CHANGES, launch an author subagent again with the review findings.
8. Repeat until PASS or until the user stops the workflow.

## Required prompt header for every subagent

Every subagent prompt must start with:

```text
Use the spec-driven-tdd skill.
You are <role>.
Load exactly these files:
- SKILL.md
- <role-file>
Repo: <repo path>
Worktree: <worktree path>
Branch: <branch>
Task: <task id>
Allowed write scope: <paths>
Required output: <paths>
```

## Synchronous planning stages

SPEC-DRAFT capture, SPEC creation, ARCHITECTURE creation, and TASKS decomposition are synchronous delegated work.

The orchestrator delegates and waits. It may inspect outputs, run shell commands, update status, and decide next steps. It may not replace the author or reviewer.

## Review stages

SPEC_REVIEW, ARCHITECTURE_REVIEW, and TASK_REVIEW are synchronous delegated work.

The reviewer must be a different subagent from the author. The reviewer writes a verdict report and a journal entry. The orchestrator reads the verdict and either advances or sends findings back to a new author subagent.

## Background implementation stages

Implementation work is launched with OpenCode background tasks. The orchestrator records the returned task_id or jobId in `.sddtdd_skill/async-tasks.jsonl` immediately.

Progress must be checked with task_status. Report-file existence is only evidence, not status.

## Background review stages

When an implementer background task completes, the orchestrator launches a reviewer background task for that specific result. The reviewer must load SKILL-REVIEWER.md and review exactly one implementer output.

## Merge stages

Merge is synchronous and serialized. The orchestrator launches one merger subagent at a time. The merger loads SKILL-MERGER.md, merges one reviewed worktree into the integration branch, resolves conflicts, reruns tests, and reports the result.
