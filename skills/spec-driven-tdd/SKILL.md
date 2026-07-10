---
name: spec-driven-tdd
description: "OpenCode-native Spec-Driven TDD with three roles: orchestrator, implementer, reviewer."
version: 5.5.0-opencode-async
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD for OpenCode

This skill uses OpenCode agents only. It does not use MCP.

There are exactly three roles:

- Orchestrator: controls the workflow and decides what happens next.
- Implementer: creates artifacts. An artifact can be SPEC.md, ARCHITECTURE.md, TASKS.md, tests, code, merge results, or evidence.
- Reviewer: reviews artifacts. A reviewed artifact can be SPEC.md, ARCHITECTURE.md, TASKS.md, tests, code, merge results, or evidence.

Do not create extra role categories such as spec author, architecture author, tasks author, or merger. Those are task kinds for the implementer role, not separate roles.

## Role files

- SKILL.md: global rules
- SKILL-ORCHESTRATOR.md: orchestrator role
- SKILL-IMPLEMENTER.md: implementer role for all artifact creation
- SKILL-REVIEWER.md: reviewer role for all reviews

## Load sets

Orchestrator loads the whole process contract because it must construct prompts, verify shapes, check journal/evidence form, and decide whether implementation and review outputs are valid.

Orchestrator loads:

- SKILL.md
- SKILL-ORCHESTRATOR.md
- SKILL-IMPLEMENTER.md
- SKILL-REVIEWER.md
- ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md
- references/JOURNAL.md
- references/STAGES.md
- references/SPEC-EXAMPLE.md
- references/GREP-RED-GREEN.md
- references/INSTRUMENTED-TESTING.md
- references/VISION-RED-TEST.md
- references/POST-DONE-BUG-FIX.md

Implementer loads:

- SKILL.md
- SKILL-IMPLEMENTER.md
- ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md
- references/JOURNAL.md

Reviewer loads:

- SKILL.md
- SKILL-REVIEWER.md
- ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md
- references/JOURNAL.md

The orchestrator may add task-specific references to implementer or reviewer prompts when the task needs them. Do not make every optional testing reference mandatory for every subagent.

## Full ancestry context

Every implementer and every reviewer must receive the full committed ancestry from the current task back to the original request.

Minimum ancestry by stage:

- SPEC or SPEC_REVIEW: SPEC-DRAFT.md, SPEC.md, journal.
- ARCHITECTURE or ARCHITECTURE_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, journal.
- TASKS or TASKS_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, journal.
- IMPLEMENTATION or IMPLEMENTATION_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, assigned task id, related RED/GREEN artifacts or evidence, journal, commits.
- MERGE or MERGE_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, reviewed implementation result, review verdict, merge evidence, journal, commits.

If an ancestor exists, include it. If it does not exist yet, say so explicitly.

## Committed evidence invariant

Every work step, artifact, journal entry, review verdict, correction, and merge result counts as evidence only after it is committed.

The implementer must commit completed artifacts, journal entries, and evidence before reporting completion.

The orchestrator must verify that the relevant worktree is clean before launching a reviewer. If the worktree is not clean, the orchestrator must return the task to the implementer and require a commit.

The reviewer reviews committed artifacts and committed evidence only. Uncommitted working-tree state is not valid evidence.

## Required flow

1. The orchestrator captures the request into `.sddtdd_skill/SPEC-DRAFT.md`.
2. The orchestrator launches a synchronous implementer subagent to create and commit `SPEC.md` plus journal evidence.
3. The orchestrator verifies clean git status for the implementer worktree.
4. The orchestrator launches a separate synchronous reviewer subagent for SPEC_REVIEW with full ancestry context.
5. If review fails, the orchestrator launches an implementer again with the review findings and full ancestry context, then repeats commit, clean-status verification, and review.
6. The same implementer/reviewer loop creates, commits, verifies, and reviews `ARCHITECTURE.md` with full ancestry context.
7. The same implementer/reviewer loop creates, commits, verifies, and reviews `TASKS.md` with full ancestry context.
8. The orchestrator launches implementation work as background implementer tasks with full ancestry context.
9. The orchestrator tracks background implementers with `task_status` and recorded task ids.
10. When one implementer completes, the orchestrator verifies committed evidence and clean git status, then launches one background reviewer for that implementer result with full ancestry context.
11. Reviewed worktrees are merged sequentially by synchronous implementer subagents, committed, verified clean, and reviewed by reviewer subagents if needed.

## Hard rules

- The orchestrator must not create reviewed artifacts itself.
- The orchestrator must not review artifacts itself.
- Every subagent request must name the skill, role, role file, task kind, allowed write scope, required output, required references, and full ancestry context.
- Planning artifacts are created and committed by synchronous implementer subagents.
- Planning artifacts are reviewed by synchronous reviewer subagents only after commit and clean-status verification.
- Code implementation uses background implementer tasks.
- Code review uses background reviewer tasks only after commit and clean-status verification.
- Merge work is sequential and is performed by synchronous implementer subagents.
- Commit messages must be ASCII-only.
- Uncommitted artifacts, journal entries, and mutable working-tree state are not evidence.

## Background requirement

Start OpenCode with:

```bash
OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true opencode
```

If background tasks are unavailable, stop before code implementation instead of pretending async work exists.
