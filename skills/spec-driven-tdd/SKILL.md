---
name: spec-driven-tdd
description: "OpenCode-native Spec-Driven TDD with delegated artifacts, delegated reviews, async implementation, and serialized merge."
version: 5.0.1-opencode-async
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD for OpenCode

This skill uses OpenCode agents only. It does not use MCP.

The Agent Orchestrator controls the workflow. It does not author reviewed artifacts and it does not review its own work.

## Role files

- SKILL.md: global rules
- SKILL-ORCHESTRATOR.md: control-plane policy
- SKILL-IMPLEMENTER.md: implementation worker role
- SKILL-REVIEWER.md: reviewer role
- SKILL-MERGER.md: merge worker role

## Required flow

1. Capture user input into `.sddtdd_skill/SPEC-DRAFT.md`.
2. Launch a synchronous author subagent to write `SPEC.md`.
3. Launch a separate synchronous reviewer subagent for SPEC_REVIEW.
4. If review fails, launch a new author subagent with the findings and repeat review.
5. Repeat the same author/reviewer loop for `ARCHITECTURE.md`.
6. Repeat the same author/reviewer loop for `TASKS.md`.
7. Launch implementers as OpenCode background tasks.
8. Track implementers with `task_status` and recorded task ids.
9. When one implementer completes, launch one background reviewer for that result.
10. Merge reviewed worktrees sequentially with a synchronous merger subagent.

## Hard rules

- The orchestrator must not write SPEC.md, ARCHITECTURE.md, or TASKS.md itself.
- The orchestrator must not ask the user to review artifacts unless the user explicitly acts as reviewer.
- Every subagent prompt must name the skill, the role, and the exact role file to load.
- Implementation and implementation review use background tasks.
- Planning and merge stages use synchronous delegated subagents.
- Merge is never parallel.

## Background requirement

Start OpenCode with:

```bash
OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true opencode
```

If background tasks are unavailable, stop before implementation instead of pretending async work exists.
