---
name: spec-driven-tdd
description: "OpenCode-native Spec-Driven TDD with three roles: orchestrator, implementer, reviewer."
version: 5.2.0-opencode-async
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

## Minimal load sets

Orchestrator loads:

- SKILL.md
- SKILL-ORCHESTRATOR.md

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

Other reference files are optional and task-specific. Load them only when the task needs them, or when the orchestrator explicitly includes them in the subagent prompt. Do not make new reference files mandatory just because they exist.

## Required flow

1. The orchestrator captures user input into `.sddtdd_skill/SPEC-DRAFT.md`.
2. The orchestrator launches a synchronous implementer subagent to create `SPEC.md`.
3. The orchestrator launches a separate synchronous reviewer subagent for SPEC_REVIEW.
4. If review fails, the orchestrator launches an implementer again with the review findings, then repeats review.
5. The same implementer/reviewer loop creates and reviews `ARCHITECTURE.md`.
6. The same implementer/reviewer loop creates and reviews `TASKS.md`.
7. The orchestrator launches implementation work as background implementer tasks.
8. The orchestrator tracks background implementers with `task_status` and recorded task ids.
9. When one implementer completes, the orchestrator launches one background reviewer for that implementer result.
10. Reviewed worktrees are merged sequentially by synchronous implementer subagents, then reviewed by reviewer subagents if needed.

## Hard rules

- The orchestrator must not create reviewed artifacts itself.
- The orchestrator must not review artifacts itself.
- The orchestrator must not ask the user to review artifacts unless the user explicitly says they are acting as reviewer.
- Every subagent prompt must name the skill, the role, the role file, the task kind, allowed write scope, required output, and required references.
- Planning artifacts are created by synchronous implementer subagents.
- Planning artifacts are reviewed by synchronous reviewer subagents.
- Code implementation uses background implementer tasks.
- Code review uses background reviewer tasks.
- Merge work is sequential and is performed by synchronous implementer subagents.
- Commit messages must be ASCII-only.

## Background requirement

Start OpenCode with:

```bash
OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true opencode
```

If background tasks are unavailable, stop before code implementation instead of pretending async work exists.
