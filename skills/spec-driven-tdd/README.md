# Spec-Driven TDD

Compact runtime version of the skill.

Read:

- `SKILL.md` for principles and layout
- `SKILL-IMPLEMENTER.md` for implementer behavior
- `SKILL-ORCHESTRATOR.md` for server policy
- `references/JOURNAL.md` for chain and invariants
- `references/STAGES.md` for standalone operation

The workflow advances only on committed proof:

- committed artifact;
- committed journal entry;
- required committed reviewer verdict;
- required committed orchestrator verdict in orchestrator mode;
- evidence that still matches the inspected HEAD.
