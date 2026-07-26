# ElAgentStudio

Reusable agent skills, workflows, and installation bundles for Codex, OpenCode, Hermes Agent, Oh My Pi, and related platforms.

## Navigation

- [Spec-Driven TDD](#spec-driven-tdd)
- [TriAgent-Driven Development](#triagent-driven-development-trdd)

## Available Skills

### Spec-Driven TDD

A spec-driven test-driven development pipeline with independent review at every stage and a complete audit trail. The Oh My Pi variant uses native asynchronous subagents, a reviewed implementation plan before the first RED/GREEN delegation, dedicated git worktree branches, reviewer subagents, serialized merge/conflict resolution, and advisor watchdog supervision.

- **Path:** `skills/spec-driven-tdd/`
- **Platform:** Oh My Pi
- **Entrypoints:** `AGENTS.md` for the primary orchestrator and `WATCHDOG.md` for the advisor
- **Role files:** `SKILL-ORCHESTRATOR.md`, `SKILL-IMPLEMENTER.md`, `SKILL-REVIEWER.md`, and `SKILL-WATCHDOG.md`
- **Execution artifact:** `.sddtdd_skill/IMPLEMENTATION-PLAN.md`, independently reviewed before implementation delegation

#### Use Spec-Driven TDD

Add the skill entrypoints to the target project as documented in:

```text
skills/spec-driven-tdd/README.md
```

Then ask the primary OMP agent to run the Spec-Driven TDD workflow for the task.

---

### TriAgent-Driven Development (trdd)

A planner -> builder -> reviewer triagent workflow for structured implementation, bounded review loops, and task orchestration.

- **Path:** `skills/triagent-driven-development/`
- **Platforms:** Codex, OpenCode

#### Install TriAgent for OpenCode

```bash
cat skills/triagent-driven-development/README_OPENCODE_INSTALL.md
```

#### Install TriAgent for Codex

```bash
cat skills/triagent-driven-development/README_CODEX_INSTALL.md
```
