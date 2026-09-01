# Simple Spec-Driven TDD entrypoint

Load:

- `SKILL.md`
- `SKILL-ORCHESTRATOR.md`

Run the primary agent as the lightweight Spec-Driven TDD orchestrator for changes to an existing product.

The required sequence is:

1. draft a working spec from the user request and repository context;
2. independently review the spec;
3. ask the user to approve it;
4. implement RED tests on the current feature branch;
5. independently review RED;
6. implement GREEN using the existing project architecture;
7. independently review GREEN.

Do not create architecture/task/journal artifacts, worktree fan-out, merge workers, or merge-review stages unless the user explicitly asks for them.

Every RED/GREEN implementer must load `SKILL-IMPLEMENTER.md`. Every independent reviewer must load `SKILL-REVIEWER.md` and remain read-only.

Keep author/implementer and reviewer identities separate. Preserve the approved spec directly in the primary RED test under an `SDDTDD SPEC` comment/docstring header.
