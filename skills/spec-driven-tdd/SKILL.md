---
name: spec-driven-tdd 
description: "Spec-Driven Test-Driven Development with three roles: orchestrator, implementer, reviewer."
version: 5.7.0
author: GPT-5.5
license: MIT
---

# Spec-Driven TDD

## Purpose

This skill turns a user request into committed software through a strict
artifact chain, independent review, RED/GREEN TDD for automatically testable
behavior, and a committed journal.

There are exactly three roles:

- Orchestrator: controls the workflow and decides what happens next. The orchestrator is a dispatcher only: it delegates artifact work to implementers and review work to reviewers.
- Implementer: creates artifacts. An artifact can be SPEC.md, ARCHITECTURE.md, TASKS.md, tests, code, merge results, or evidence.
- Reviewer: reviews artifacts. A reviewed artifact can be SPEC.md, ARCHITECTURE.md, TASKS.md, tests, code, merge results, or evidence.

## Role files

- SKILL.md: global rules
- SKILL-ORCHESTRATOR.md: orchestrator role
- SKILL-IMPLEMENTER.md: implementer role for all artifact creation
- SKILL-REVIEWER.md: reviewer role for all reviews

## Load sets

Orchestrator loads only its own control-plane contract:

- SKILL.md
- SKILL-ORCHESTRATOR.md
- references/JOURNAL.md

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

## Four hard rules

1. Every agent-generated artifact must receive the required independent review before downstream work depends on it.
2. Every automatically testable behavior must pass through reviewed RED then reviewed GREEN.
3. Every work step, review verdict, correction, and orchestrator gate must be journaled and committed before it counts as evidence.
4. Reviewer approval and orchestrator process approval are distinct proofs. Neither replaces the other.
5. Changes in user acceptance behavior must be escalated to the user and recorded to the journal with lable ACCEPTANCE_CHANGE.

## Required flow

1. The orchestrator captures the request into `.sddtdd_skill/SPEC-DRAFT.md`.
2. The orchestrator launches a synchronous implementer subagent to create and commit `SPEC.md` plus journal evidence.
3. The orchestrator verifies clean git status for the implementer worktree.
4. The orchestrator launches a separate synchronous reviewer subagent for SPEC_REVIEW with full ancestry context.
5. If review fails, the orchestrator launches an implementer again with the review findings and full ancestry context, then repeats commit, clean-status verification, and review.
6. The same implementer/reviewer loop creates, commits, verifies, and reviews `ARCHITECTURE.md` with full ancestry context.
7. The same implementer/reviewer loop creates, commits, verifies, and reviews `TASKS.md` with full ancestry context.
8. The orchestrator launches implementation work as background implementer tasks with full ancestry context.
9. The orchestrator tracks background implementers with the runtime task-status mechanism and recorded task ids.
10. When one implementer completes, the orchestrator verifies committed evidence and clean git status, then immediately launches one background reviewer for that implementer result with full ancestry context.
11. The orchestrator does not wait for a whole batch or wave before reviewing a completed implementer result.
12. Reviewed worktrees are merged sequentially by synchronous MERGE implementer subagents.
13. Each MERGE implementer merges one reviewed worktree into the integration branch, resolves conflicts if needed, runs the required tests after conflict resolution and before committing the merge result, records test evidence, then reports completion.

## Background requirement

This skill requires an agent runtime that can launch background subagents and later query their task status.

If background tasks are unavailable, stop before code implementation instead of pretending async work exists.
