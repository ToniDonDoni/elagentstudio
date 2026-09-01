---
name: spec-driven-tdd
version: 9.0.0-simple
description: "Minimal Spec-Driven TDD for existing products: persisted spec, human approval, reviewed RED, reviewed GREEN."
author: GPT-5.6
license: MIT
---

# Simple Spec-Driven TDD

## Purpose

Use this workflow for changes to an existing product. The project already has an architecture, source layout, and test conventions. Reuse them.

Keep only one workflow artifact: a specification file at `specs/<change>/spec.md`.

Everything else lives where the project normally keeps it:

- specification: `specs/<change>/spec.md`;
- tests: the project's existing test directories;
- implementation: the project's existing source directories.

Do not create architecture documents, task graphs, journals, stage files, evidence manifests, workflow logs, worktree orchestration, merge workers, or merge-review artifacts.

## Roles

There are only two roles.

### Implementer

The primary agent is the Implementer. It owns the whole forward workflow:

- inspect the repository;
- create or revise the spec;
- present the reviewed spec to the user for approval;
- write RED tests;
- implement GREEN;
- handle reviewer findings;
- report completion.

The Implementer must never independently approve its own spec, RED, or GREEN result.

### Reviewer

A separate delegated agent is the Reviewer. It is read-only and reviews exactly one stage:

- `SPEC_REVIEW`;
- `RED_REVIEW`;
- `GREEN_REVIEW`.

The Reviewer never edits files, fixes findings, commits, or advances the workflow.

## Specification file

For each requested change, create a short stable folder name and write:

`specs/<change>/spec.md`

The spec is the single source of truth for the requested behavior. It must contain:

- **Intent** — what the user wants changed;
- **Behavior** — externally observable behavior after the change;
- **Acceptance criteria** — concrete testable outcomes;
- **Edge cases / non-goals** — only where useful;
- **RED proof** — the practical test boundary and the failure expected before implementation;
- **GREEN condition** — what must pass after implementation.

Do not add design, architecture, task, journal, or process-history sections unless they are necessary to understand the behavior itself.

Use the repository's existing architecture and conventions to resolve implementation details. The spec describes what must be true, not a replacement architecture.

## Required flow

### 1. Write the spec

The Implementer reads the user request and inspects the relevant repository code and tests.

Create or update `specs/<change>/spec.md` and commit it with an ASCII-only commit message.

### 2. Independent spec review

Delegate a Reviewer against the exact committed spec.

`SPEC_REVIEW` checks that the spec:

- faithfully captures the user's request without invented scope;
- has concrete acceptance criteria;
- uses existing product architecture as context rather than designing a new architecture;
- identifies a practical proving-test boundary;
- states a target-specific RED failure and a clear GREEN condition;
- is concise enough to remain useful during implementation.

On `FAIL`, the Implementer fixes the spec, commits the revision, and sends the new exact commit for review again.

On `NEEDS_CLARIFICATION`, inspect the repository first; ask the user only when the ambiguity cannot be resolved honestly from the request or codebase.

### 3. Human approval

After `SPEC_REVIEW: PASS`, show the current spec to the user and require explicit approval before writing RED tests.

If the user changes the requirement, update the same spec file, commit it, independently review it again, then request approval again.

### 4. RED

After human approval, the Implementer writes the proving test or tests in the project's normal test location.

The primary proving test should contain a short reference such as:

`SDDTDD SPEC: specs/<change>/spec.md`

Do not duplicate the full spec into test comments.

RED must:

1. test the approved behavior at the highest practical product boundary;
2. avoid implementing the requested production behavior;
3. run the narrow proving command;
4. fail specifically because the requested behavior is missing or incorrect;
5. be committed with an ASCII-only commit message.

Syntax errors, missing dependencies, broken fixtures, environment failures, or unrelated defects are invalid RED.

### 5. Independent RED review

Delegate a Reviewer against the exact RED commit and the approved spec commit/path.

`RED_REVIEW` checks that:

- tests match every relevant acceptance criterion in the approved spec;
- the test points to the canonical spec file;
- the selected boundary is practical and sufficiently high-level;
- the observed failure is target-specific;
- production behavior was not smuggled into RED.

On `FAIL`, the Implementer corrects RED, commits, and re-runs `RED_REVIEW`.

GREEN is forbidden before `RED_REVIEW: PASS`.

### 6. GREEN

The Implementer now changes production code using the project's existing architecture, patterns, naming, and boundaries.

Make the minimum production change required by the approved spec and reviewed RED. Avoid speculative refactors and architectural redesign.

Run the proving test plus relevant nearby regression tests, then commit with an ASCII-only commit message.

### 7. Independent GREEN review

Delegate a Reviewer against the exact GREEN commit, with the approved spec and reviewed RED ancestry.

`GREEN_REVIEW` checks that:

- every acceptance criterion has direct code/test evidence;
- the reviewed RED test now passes for the intended reason;
- implementation follows the existing project architecture and conventions;
- the change is scoped to the requested behavior;
- relevant regression tests pass;
- tests or spec were not weakened merely to manufacture GREEN.

On `FAIL`, the Implementer fixes GREEN, commits, and re-runs `GREEN_REVIEW`.

The workflow is complete only after `GREEN_REVIEW: PASS`.

## Requirement changes during work

The spec file remains the source of truth.

If the user changes the requirement at any point:

1. update `specs/<change>/spec.md`;
2. commit it;
3. run `SPEC_REVIEW` again;
4. obtain human approval again;
5. update and re-review RED if the changed requirement affects tests;
6. continue GREEN only from the newly approved and reviewed state.

No append-only draft, journal, or stage bookkeeping is required.

## Reviewer verdicts

The Reviewer returns exactly one:

- `PASS`;
- `FAIL`;
- `NEEDS_CLARIFICATION`;
- `BLOCKED`.

For `FAIL`, provide concrete actionable findings. For `PASS`, identify the decisive evidence briefly.

## Hard rules

1. One persisted workflow artifact only: `specs/<change>/spec.md`.
2. The primary agent is the Implementer; there is no separate orchestrator role.
3. Review is always performed by a separate read-only Reviewer.
4. No RED before reviewed and human-approved spec.
5. No GREEN before `RED_REVIEW: PASS`.
6. No completion before `GREEN_REVIEW: PASS`.
7. Use the existing project architecture; do not create an architecture phase.
8. Tests and implementation stay in the project's normal directories.
9. Keep work sequential on the current feature branch unless the user asks otherwise.
10. Commit messages are ASCII-only.
11. Passing tests do not replace independent review.

## Completion

Report the spec path, approved behavior, RED commit/result, GREEN commit/results, and final reviewer verdict. Nothing else is required.
