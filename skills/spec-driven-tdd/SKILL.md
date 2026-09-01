---
name: spec-driven-tdd
version: 8.0.0-simple
description: "Lightweight Spec-Driven TDD for changes to an existing product: reviewed spec, human approval, reviewed RED, reviewed GREEN."
author: GPT-5.6
license: MIT
---

# Simple Spec-Driven TDD

## Purpose

Use this workflow when an existing product already has an architecture and the user asks for a concrete change, fix, or small feature.

The workflow deliberately avoids architecture documents, task graphs, journals, worktree orchestration, merge reviews, and other process artifacts. The existing project architecture is the default design constraint.

The invariant is simple: clarify the requested behavior, get it independently reviewed and approved by the user, prove it with a failing test, independently review that RED state, implement the minimum change, then independently review the GREEN state.

## Roles

Keep three roles separate:

- Orchestrator: coordinates the sequence, presents the spec to the user, and routes feedback. It does not independently approve worker output.
- Implementer: writes either the executable RED tests or the GREEN production change.
- Reviewer: independently inspects one requested result and never fixes it.

The same repository branch is used sequentially for the whole workflow. Do not create per-task worktrees or merge branches unless the user explicitly asks for them.

## No workflow artifacts

Do not create `.sddtdd_skill/`, `SPEC.md`, `SPEC-DRAFT.md`, `ARCHITECTURE.md`, `TASKS.md`, journals, reviewer logs, orchestration logs, evidence manifests, or merge artifacts.

The approved specification is preserved directly in the RED test change. Put a concise `SDDTDD SPEC` header near the proving tests, using the host language's normal comment or docstring format. The header must contain:

- the user-visible behavior to change;
- acceptance criteria;
- important edge cases or non-goals;
- the expected RED reason: what must fail before implementation;
- the GREEN condition: what must pass after implementation.

If several test files are required, keep the canonical full header in the primary proving test and use short references in secondary files.

## Required flow

### 1. Draft the working spec

Treat the user's message as `SPEC-DRAFT` conceptually; do not persist it as a workflow file.

Delegate a spec author to inspect the existing repository and turn the request into a concise working specification. The spec must describe behavior and acceptance criteria, not invent a new architecture. Prefer existing project patterns, modules, test styles, naming, and boundaries.

The spec must also state the intended proving-test boundary and the expected RED failure reason.

### 2. Independent spec review

Delegate a separate reviewer to compare the working spec against:

- the user's request;
- relevant existing product behavior and architecture;
- practical test boundaries.

The reviewer returns `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, or `BLOCKED`.

On `FAIL`, send the findings back to the spec author and re-review. On `NEEDS_CLARIFICATION`, ask the user only for information that cannot be resolved from the repository or request.

### 3. Human approval gate

After independent spec review passes, present the working spec to the user and explicitly ask for approval.

If the user changes anything, revise the same working spec, independently review the revision, and present it again. Do not start RED until the user clearly approves the current version.

### 4. RED implementation

Delegate a RED implementer on the current feature branch.

The RED implementer must:

1. write the proving test or tests using the project's existing test architecture;
2. embed the approved specification in the primary proving test as the `SDDTDD SPEC` header;
3. avoid implementing the requested behavior;
4. run the narrow proving test;
5. demonstrate that it fails specifically because the requested behavior is missing or incorrect;
6. commit the RED change with an ASCII-only commit message.

An unrelated failure, syntax error, fixture problem, dependency failure, or environment problem is not valid RED.

### 5. Independent RED review

Delegate a different reviewer against the exact RED commit.

The reviewer checks that:

- the test matches the approved specification;
- the `SDDTDD SPEC` header faithfully preserves the approved requirements;
- the test exercises the highest practical product boundary for the requested change;
- the observed failure is target-specific;
- production behavior was not implemented during RED.

On `FAIL`, the RED implementer corrects the tests and the same review stage repeats. GREEN cannot begin without RED review `PASS`.

### 6. GREEN implementation

Delegate a GREEN implementer from the reviewed RED state on the same branch.

The implementer must use the existing project architecture and patterns. Do not introduce a new architecture phase or speculative refactor. Implement the minimum production change needed to satisfy the approved spec and reviewed RED test, then run the proving test and relevant nearby regression tests. Commit with an ASCII-only commit message.

### 7. Independent GREEN review

Delegate a different reviewer against the exact GREEN commit.

The reviewer checks that:

- every approved acceptance criterion is covered by direct code/test evidence;
- the reviewed RED test now passes for the intended reason;
- the implementation follows the existing project architecture and conventions;
- the change is minimal enough for the requested scope;
- relevant regression tests pass;
- no requirement was silently weakened in code or tests.

On `FAIL`, route findings back to the GREEN implementer and re-review. The workflow is complete only after GREEN review `PASS`.

## User changes during work

If the user changes the requirement before RED review passes, update the working spec, independently re-review it, and obtain human approval again.

If the user changes the requirement after RED review passes, return to the spec step, re-review and re-approve the new spec, then update RED before continuing GREEN. Do not maintain an append-only draft file or journal.

## Hard rules

1. No production implementation before human-approved spec and independently reviewed RED.
2. No GREEN before `RED_REVIEW: PASS`.
3. No completion before `GREEN_REVIEW: PASS`.
4. The spec author/implementer never reviews its own result.
5. Reviewers are read-only and do not fix files.
6. Use the existing project architecture instead of creating an architecture artifact.
7. Keep the workflow on one feature branch unless the user requests otherwise.
8. Preserve the approved spec in the RED test header, not in a separate workflow artifact.
9. Commit messages are ASCII-only.
10. Passing tests alone do not replace independent review.

## Completion

Report completion with the approved behavior, RED commit, GREEN commit, test commands/results, and final reviewer verdict. Do not manufacture extra process evidence.
