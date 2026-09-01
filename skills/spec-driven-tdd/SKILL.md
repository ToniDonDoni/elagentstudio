---
name: spec-driven-tdd
version: 9.0.0-simple
description: "Minimal Spec-Driven TDD for existing products: human-approved spec, independently reviewed RED and GREEN."
author: GPT-5.6
license: MIT
---

# Simple Spec-Driven TDD

Use this workflow for changes to an existing product. Reuse the repository's architecture, source layout, and test conventions.

## Workflow

1. **Implementer** inspects the existing repository and formalizes the user's request into a concise spec with acceptance criteria, RED proof, and GREEN condition.
2. **User** explicitly approves that spec.
3. **Implementer** writes RED tests and proves they fail for the intended reason.
4. **Reviewer**, running as a separate delegated agent, performs `RED_REVIEW` against the approved spec.
5. **Implementer** writes the minimum GREEN implementation and runs proving plus relevant regression tests.
6. **Reviewer**, again independently delegated, performs `GREEN_REVIEW` and verifies the final outcome solves the original business task.
7. The change is complete only after `GREEN_REVIEW: PASS` and the original user task is demonstrably resolved.

Work sequentially on a dedicated feature branch for the change unless the user explicitly asks otherwise. Never implement directly on the repository's main/default branch.

## Roles

There are exactly two agent roles.

### Implementer

The Implementer is the single primary agent and owns the whole forward path: repository inspection, spec formalization, user approval, RED, fixes from RED review, GREEN implementation, fixes from GREEN review, and completion.

### Reviewer

The Reviewer is a genuinely independent delegated agent. Launch it through the available agent runtime/platform delegation mechanism as a separate worker/session from the Implementer; the Implementer must not merely switch hats.

The Reviewer must not edit production code, tests, or the spec and must not fix findings or commit changes. It may read any repository content, run tests or other verification commands, and inspect CI results or other build/test artifacts needed to validate the review.

The Reviewer performs only `RED_REVIEW` and `GREEN_REVIEW`.

## Spec

If the project already has a `specs/` directory, keep one flat numbered spec per change there: `specs/spec_<number>.md`, for example `specs/spec_001.md`. Do not create per-spec subdirectories.

If the project has no `specs/` directory, do not introduce one only for this workflow. Instead, preserve the complete user-approved spec in the primary proving test description so the test remains self-contained and reviewable.

The final spec shown to the user for approval must be compact enough to read quickly, but it must preserve the full substance of the user's problem and requirements.

The approval version of the spec must include:

- a concise but complete statement of the original problem or business task expressed by the user;
- all explicit requirements, constraints, and required observable behavior from the user's request;
- proposed acceptance criteria for the tests, written so each criterion can be objectively proved or disproved;
- important edge cases or non-goals when useful;
- RED proof: what test boundary should prove the behavior and why it should fail before implementation;
- GREEN condition: what must pass after implementation.

Do not ask the user to approve an abbreviated summary that omits part of the stated problem or requirements. The user-approved version is the canonical spec for subsequent RED and GREEN work.

Acceptance criteria must describe observable behavior at the highest practical product boundary. For backend/API work, prefer real application or public API boundaries over isolated internals. A class, method, route declaration, DTO, mock call, internal flag, requirement ID, or grep result is not acceptance evidence when the requested behavior can be tested at a practical backend/API boundary.

Example: for a public API requirement, a strong proving test sends a real HTTP/RPC request through the application boundary and asserts status/body plus required side effects. Testing only the controller or service method in isolation is not equivalent.

When a spec file is used, commit it with an ASCII-only commit message, show this final compact canonical version to the user, and require explicit user approval before RED. There is no `SPEC_REVIEW` stage.

If the user changes the requirement, update the approved spec source, obtain explicit user approval again, and repeat any affected RED/GREEN work and reviews.

## RED

After user approval, the Implementer writes proving tests in the project's normal test location.

Every proving test must have a clear description of the behavior under test and its expected result.

When a persisted spec file exists, the primary proving test should reference it, for example:

`SDDTDD SPEC: specs/spec_<number>.md`

When no persisted spec file exists, the primary proving test description must contain the complete user-approved spec, including acceptance criteria and expected result.

RED must test the approved behavior at the highest practical boundary, contain no production implementation of the requested behavior, and fail specifically because that behavior is missing or incorrect. Syntax errors, missing dependencies, broken fixtures, environment failures, or unrelated defects are invalid RED.

Run the narrow proving command and commit RED with an ASCII-only commit message.

### RED_REVIEW — Reviewer agent

The independently delegated Reviewer must first read the approved spec and the original user request, then inspect the exact RED commit and execute or inspect the proving test evidence as needed.

The Reviewer checks that:

- RED is relevant to the approved spec and follows sound test-driven-development practice;
- tests cover **all acceptance criteria** in the approved spec;
- each proving test clearly states the behavior and expected result;
- the proving boundary is practical and sufficiently high-level;
- the observed failure is target-specific and demonstrates the requested behavior is genuinely missing or incorrect;
- RED does not contain production implementation or test-only logic that makes the requested behavior pass before GREEN, such as embedding the solution in fixtures, mocks, helpers, or assertions;
- test setup, environment, fixtures, and dependencies are valid enough that the RED result is trustworthy.

The Reviewer may run tests and inspect CI/test artifacts to establish this evidence.

Reviewer returns `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, or `BLOCKED`. On `FAIL`, it gives concrete findings; the Implementer fixes them, commits, reruns RED, and delegates review again.

GREEN is forbidden before `RED_REVIEW: PASS`.

## GREEN

After RED review passes, the Implementer makes the minimum production change required by the approved spec and reviewed RED, using the project's existing architecture and conventions. Avoid speculative refactors or redesign.

Run the proving tests and relevant nearby regression tests, then commit with an ASCII-only commit message.

### GREEN_REVIEW — Reviewer agent

The independently delegated Reviewer must read the original user request, the approved spec, the reviewed RED, and the exact GREEN commit. It may run tests and inspect CI/build/test artifacts needed to verify the result.

The Reviewer checks that:

- every acceptance criterion in the approved spec has direct code/test evidence;
- reviewed RED now passes for the intended reason;
- implementation follows existing architecture and conventions;
- scope stays within the approved behavior;
- relevant regression tests pass;
- tests or spec were not weakened merely to manufacture GREEN;
- there is an explicit end-to-end trace from the original business task in the user's request, through the approved spec and acceptance criteria, to tested observable behavior and an accepted outcome that actually resolves that business task.

Reviewer returns `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, or `BLOCKED`. On `FAIL`, the Implementer fixes GREEN, commits, reruns tests, and delegates review again.

The workflow is complete only after `GREEN_REVIEW: PASS` and the Reviewer has explicitly confirmed that the original user task is resolved by the accepted outcome.

## Constraints

Use the project's existing architecture and conventions.

Commit messages are ASCII-only. Passing tests never replace independent RED/GREEN review.

## Completion

Report the spec source, approved behavior, RED commit/result, GREEN commit/results, final Reviewer verdict, and how the accepted outcome resolves the original user task.
