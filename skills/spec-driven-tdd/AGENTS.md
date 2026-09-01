# Simple Spec-Driven TDD entrypoint

Load `SKILL.md`.

The primary agent runs the **Implementer** role defined there. Delegate a separate read-only **Reviewer** role from the same skill for `SPEC_REVIEW`, `RED_REVIEW`, and `GREEN_REVIEW`.

Use one persisted workflow artifact per change, directly under `specs/`:

`specs/spec_<number>.md`

For example: `specs/spec_001.md`. Do not create per-spec subdirectories.

Keep tests and production code in the project's existing directories.

Required flow:

1. Implementer writes and commits the spec.
2. Reviewer reviews the exact spec commit.
3. User explicitly approves the reviewed spec.
4. Implementer writes and commits RED tests.
5. Reviewer reviews the exact RED commit.
6. Implementer writes and commits GREEN implementation.
7. Reviewer reviews the exact GREEN commit.

No architecture/task/journal/stage/evidence artifacts, no separate orchestrator, no per-task worktrees, and no merge-review ceremony unless the user explicitly asks for them.
