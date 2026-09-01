---
name: spec-driven-tdd
version: 9.0.0-simple
description: "Minimal brownfield Spec-Driven TDD: human-approved spec, independently reviewed RED and GREEN."
author: GPT-5.6
license: MIT
---

# Simple Spec-Driven TDD

Use this workflow for changes to an existing product. Reuse the repository's architecture, source layout, and test conventions.

Keep one workflow artifact per change: a flat numbered spec at `specs/spec_<number>.md`, for example `specs/spec_001.md`. Tests stay in normal test directories and implementation stays in normal source directories.

Do not create per-spec subdirectories, architecture documents, task graphs, journals, stage files, evidence manifests, workflow logs, worktrees, merge workers, or merge-review artifacts.

## Roles

There are exactly two agent roles.

### Implementer

The Implementer is the single primary agent and owns the whole forward path: inspect the repository, formalize the user's draft into the persisted spec, obtain explicit user approval, write and fix RED tests, write and fix GREEN implementation, and finish the change.

Do not split spec authoring, test authoring, and implementation into separate worker roles.

### Reviewer

The Reviewer is a genuinely independent delegated agent. Launch it through the available agent runtime/platform delegation mechanism as a separate worker/session from the Implementer; the Implementer must not merely switch hats.

The Reviewer is read-only: it does not edit files, fix findings, commit, or advance the workflow. It performs only:

- `RED_REVIEW`
- `GREEN_REVIEW`

## Spec

For each change, allocate the next number and create or update `specs/spec_<number>.md`.

Keep the spec concise. It should state:

- intent and observable behavior;
- concrete acceptance criteria;
- important edge cases or non-goals when useful;
- RED proof: what test boundary should prove the behavior and why it should fail before implementation;
- GREEN condition: what must pass after implementation.

Acceptance criteria must describe observable behavior at the highest practical product boundary. For backend/API work, prefer real application or public API boundaries over isolated internals. A class, method, route declaration, DTO, mock call, internal flag, requirement ID, or grep result is not acceptance evidence when the requested behavior can be tested at a practical backend/API boundary.

Example: for a public API requirement, a strong proving test sends a real HTTP/RPC request through the application boundary and asserts status/body plus required side effects. Testing only the controller or service method in isolation is not equivalent.

Commit the spec with an ASCII-only commit message, show the current spec to the user, and require explicit user approval before RED. There is no `SPEC_REVIEW` stage.

If the user changes the requirement, update the same spec, commit it, obtain explicit user approval again, and repeat any affected RED/GREEN work and reviews.

## RED

After user approval, the Implementer writes proving tests in the project's normal test location. The primary proving test should reference the canonical spec, for example:

`SDDTDD SPEC: specs/spec_<number>.md`

Do not duplicate the full spec in test comments.

RED must test the approved behavior at the highest practical boundary, contain no production implementation of the requested behavior, and fail specifically because that behavior is missing or incorrect. Syntax errors, missing dependencies, broken fixtures, environment failures, or unrelated defects are invalid RED.

Run the narrow proving command and commit RED with an ASCII-only commit message.

### RED_REVIEW

Delegate the independent Reviewer against the exact RED commit and approved spec.

Reviewer checks that:

- tests cover the relevant acceptance criteria;
- the proving boundary is practical and sufficiently high-level;
- the observed failure is target-specific;
- production behavior was not smuggled into RED.

Reviewer returns `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, or `BLOCKED`. On `FAIL`, it gives concrete findings; the Implementer fixes them, commits, reruns RED, and delegates review again.

GREEN is forbidden before `RED_REVIEW: PASS`.

## GREEN

After RED review passes, the Implementer makes the minimum production change required by the approved spec and reviewed RED, using the project's existing architecture and conventions. Avoid speculative refactors or redesign.

Run the proving tests and relevant nearby regression tests, then commit with an ASCII-only commit message.

### GREEN_REVIEW

Delegate the independent Reviewer against the exact GREEN commit, approved spec, and reviewed RED.

Reviewer checks that:

- every relevant acceptance criterion has direct code/test evidence;
- reviewed RED now passes for the intended reason;
- implementation follows existing architecture and conventions;
- scope stays within the approved behavior;
- relevant regression tests pass;
- tests or spec were not weakened merely to manufacture GREEN.

Reviewer returns `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, or `BLOCKED`. On `FAIL`, the Implementer fixes GREEN, commits, reruns tests, and delegates review again.

The workflow is complete only after `GREEN_REVIEW: PASS`.

## Flow

`user draft -> Implementer formalizes spec -> explicit user approval -> RED -> independent RED_REVIEW -> GREEN -> independent GREEN_REVIEW -> done`

Keep the work sequential on the current feature branch unless the user explicitly asks otherwise. Passing tests never replace independent RED/GREEN review.

## Completion

Report the spec path, approved behavior, RED commit/result, GREEN commit/results, and final Reviewer verdict.
