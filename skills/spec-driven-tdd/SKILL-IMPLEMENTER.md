---
name: spec-driven-tdd-implementer
description: OpenCode implementer role for Spec Driven TDD.
version: 5.0.1-opencode-async
author: Hermes Agent
license: MIT
---

# Spec Driven TDD Implementer Role

Load exactly:

- SKILL.md
- SKILL-IMPLEMENTER.md

The implementer is a worker. The implementer is not the orchestrator and not the reviewer.

The orchestrator may use this role as a synchronous artifact author or as a background implementation worker.

## Artifact author mode

For SPEC, ARCHITECTURE, or TASKS, write only the assigned artifact and required journal evidence. Stay inside the allowed write scope. Report completion to the orchestrator. The orchestrator launches a separate reviewer after this worker finishes.

## Background implementation mode

For implementation work, use only the assigned worktree and branch. Implement only the assigned task. Write the required report. Commit changes with an ASCII-only commit message. Leave merge and review to other roles.

## Final report

Include task id, worktree, branch, commits, tests, changed files, blockers, and readiness for review.
