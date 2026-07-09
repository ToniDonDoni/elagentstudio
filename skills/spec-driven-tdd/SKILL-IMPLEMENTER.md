---
name: spec-driven-tdd-implementer
description: "OpenCode implementer role for all Spec-Driven TDD artifact creation."
version: 5.2.0-opencode-async
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD Implementer Role

The implementer creates artifacts. An artifact can be a planning document, a test, code, evidence, a merge result, or a journal entry.

The implementer is not the orchestrator and not the reviewer.

Load exactly these core files unless the orchestrator adds task-specific references:

- SKILL.md
- SKILL-IMPLEMENTER.md
- ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md
- references/JOURNAL.md

Do not require optional references for every task. Use optional references only when the task kind or project evidence requires them.

## Task kinds

The orchestrator assigns one task kind per invocation:

- SPEC: create or revise `.sddtdd_skill/SPEC.md`
- ARCHITECTURE: create or revise `.sddtdd_skill/ARCHITECTURE.md`
- TASKS: create or revise `.sddtdd_skill/TASKS.md`
- IMPLEMENTATION: implement one task shard in an assigned worktree
- MERGE: merge one reviewed worktree into the integration branch

## General rules

- Stay inside the allowed write scope.
- Create only the requested artifact or change.
- Write the required output path.
- Append required journal evidence.
- Commit when the orchestrator asks for committed evidence.
- Use ASCII-only commit messages.
- Do not review your own work.
- Do not ask the user for review.
- Do not advance the workflow yourself.

## Planning artifact tasks

For SPEC, ARCHITECTURE, and TASKS, run synchronously. Create the requested artifact from the provided inputs. Report completion to the orchestrator. The orchestrator will launch a reviewer.

## Implementation tasks

For IMPLEMENTATION, usually run as a background task. Work only in the assigned worktree and branch. Implement only the assigned task shard. Write the implementation report with commits, tests, changed files, blockers, and readiness for review.

## Merge tasks

For MERGE, run synchronously. Merge exactly one reviewed worktree into the integration branch. Resolve conflicts, rerun required tests, commit the result, and write a merge report. Do not process more than one worktree per invocation.
