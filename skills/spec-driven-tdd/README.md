# Simple Spec-Driven TDD

A lightweight reviewed TDD workflow for changing an existing product without inventing a second project-management system inside the repository.

## Flow

1. The user describes a change in normal language.
2. A spec author inspects the repository and drafts a concise behavioral spec.
3. A separate reviewer reviews that spec.
4. The user approves or corrects the reviewed spec.
5. A RED implementer adds proving tests and embeds the approved spec in the primary test as an `SDDTDD SPEC` comment/docstring header.
6. A separate reviewer verifies that RED matches the spec and fails for the intended target reason.
7. A GREEN implementer makes the minimum production change using the project's current architecture.
8. A separate reviewer verifies GREEN, acceptance coverage, architecture fit, and relevant regression tests.

If the user changes the requirement, return to the spec gate and repeat the affected RED/GREEN stages.

## Deliberately absent

This variant does not create `SPEC.md`, `SPEC-DRAFT.md`, `ARCHITECTURE.md`, `TASKS.md`, journals, evidence manifests, runtime logs, worktree-per-task branches, scheduling waves, merge workers, or merge-review stages.

The working spec exists in conversation until approval. Once RED is written, the approved behavior and test requirements are preserved in the proving test header, next to the executable evidence that enforces them.

## Files

- `SKILL.md` — workflow and hard gates.
- `SKILL-ORCHESTRATOR.md` — primary-agent sequence.
- `SKILL-IMPLEMENTER.md` — SPEC, RED, GREEN, and correction behavior.
- `SKILL-REVIEWER.md` — independent SPEC/RED/GREEN review.
- `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md` — optional detailed guidance for choosing test boundaries.
- `AGENTS.md` — compact entrypoint.

## Core invariant

No production implementation before a human-approved spec and independently reviewed RED; no completion before independently reviewed GREEN.
