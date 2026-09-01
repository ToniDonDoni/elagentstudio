# Simple Spec-Driven TDD

A minimal reviewed TDD workflow for changing an existing product.

## Shape

Each change has one numbered specification file directly under `specs/`:

`specs/spec_<number>.md`

For example: `specs/spec_001.md`, `specs/spec_002.md`.

Do not create a subdirectory per spec.

Tests stay in the project's existing test directories. Production code stays in the existing source layout. The project architecture is reused rather than redesigned.

## Roles

Both roles are defined in `SKILL.md`:

- **Implementer** — the primary agent. Writes/revises the spec, RED tests, and GREEN implementation.
- **Reviewer** — a separate read-only agent. Reviews SPEC, RED, and GREEN stages.

## Flow

1. Implementer inspects the repository and writes `specs/spec_<number>.md`.
2. Reviewer independently reviews the exact committed spec.
3. User explicitly approves the reviewed spec.
4. Implementer writes failing proving tests in the normal test location.
5. Reviewer verifies RED against the approved spec and target-specific failure.
6. Implementer makes the minimum production change using the existing architecture.
7. Reviewer verifies GREEN, acceptance coverage, architecture fit, and relevant regression tests.

If the requirement changes, update the same spec first, review it again, obtain user approval again, and repeat affected RED/GREEN stages.

## Deliberately absent

No `SPEC-DRAFT`, architecture file, task graph, journal, stage file, evidence verifier, runtime logs, worktree fan-out, merge worker, or merge review.

## Files

- `SKILL.md` — complete workflow with both Implementer and Reviewer roles.
- `AGENTS.md` — compact entrypoint.
- `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md` — optional detailed guidance for writing acceptance criteria and selecting proving-test boundaries.

The essential rule is boring and therefore useful: approved spec, reviewed RED, reviewed GREEN. Everything else has to justify its existence.
