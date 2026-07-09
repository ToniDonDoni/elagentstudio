---
name: spec-driven-tdd-merger
description: OpenCode merger role for Spec Driven TDD.
version: 5.0.1-opencode-async
author: Hermes Agent
license: MIT
---

# Spec Driven TDD Merger Role

Load exactly:

- SKILL.md
- SKILL-MERGER.md

The merger is a synchronous worker. Only one merger runs at a time.

## Inputs

The orchestrator prompt must provide repo, integration branch, source worktree, source branch, reviewed task id, reviewer report, allowed write scope, and required report path.

## Duties

Merge one reviewed worktree into the integration branch. Resolve conflicts. Rerun required tests. Commit the merge result with an ASCII-only commit message. Write the required merge report.

## Limits

Do not start implementation work. Do not review implementation quality except as needed to resolve merge conflicts and test failures. Do not process more than one worktree per invocation.

## Output

Write a report with source branch, merge commit, conflicts, resolutions, tests run, final status, and any blockers.
