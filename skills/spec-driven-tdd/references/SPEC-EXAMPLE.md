# Spec-Driven TDD Example

Start of the workflow:

- the user request is captured verbatim in `.sddtdd_skill/SPEC-DRAFT.md` and journaled as `USER_INPUT`;
- the orchestrator delegates SPEC creation, then launches `SPEC_REVIEW`, records the process gate, and proceeds through ARCHITECTURE and TASKS the same way.

For a reviewed task like `RED`, the legal chain is:

```text
RED work entry (COMPLETED)
→ RED_REVIEW (PASS, parent = RED)
→ ORCHESTRATOR_TASK_REVIEW (PASS, parent = RED_REVIEW)
→ GREEN
```

If reviewed files changed after `RED_REVIEW: PASS`, the orchestrator must return
`FAIL` until a fresh committed review verdict exists on the current HEAD.