# ElAgentStudio

Reusable agent skills for Hermes Agent, Codex, and OpenCode.

## Repository Structure

```
skills/                          ← Single source of truth
  spec-driven-tdd/
    SKILL.md
    references/SPEC-EXAMPLE.md
  triagent-driven-development/
    SKILL.md
    agents/
      trdd-orchestrator.md
      trdd-planner.md
      trdd-builder.md
      trdd-reviewer.md

install/                         ← Convenience install scripts
  hermes-spec-driven-tdd.sh
  opencode-triagent.sh
  codex-triagent.sh
```

## Available Skills

### Spec-Driven TDD

A spec-driven development pipeline with review at every step and a complete audit trail.

- **Path:** `skills/spec-driven-tdd/`
- **Platform:** Hermes Agent
- **Requires:** pytest, Hermes Agent with `delegate_task`

### TriAgent-Driven Development

A planner -> builder -> reviewer triagent workflow for structured implementation, bounded review loops, and task orchestration.

- **Path:** `skills/triagent-driven-development/`
- **Platforms:** Hermes Agent, Codex, OpenCode

---

## Installation

### Hermes Agent (Native)

```bash
hermes skills install ToniDonDoni/elagentstudio/skills/spec-driven-tdd
hermes skills install ToniDonDoni/elagentstudio/skills/triagent-driven-development
```

**Duplicate install:** Warns and skips (use `--force` to reinstall).

### Hermes Agent (Fallback)

From a cloned repository:

```bash
install/hermes-spec-driven-tdd.sh
install/hermes-spec-driven-tdd.sh --override   # force reinstall
```

### OpenCode

From a cloned repository:

```bash
install/opencode-triagent.sh
install/opencode-triagent.sh --override
```

### Codex

From a cloned repository:

```bash
install/codex-triagent.sh
install/codex-triagent.sh --override
```

---

## Verification

### Hermes

```bash
hermes skills list | grep spec-driven-tdd
find ~/.hermes/skills -path '*spec-driven-tdd*' -type f | sort
```

### OpenCode

```bash
ls -la ~/.config/opencode/skills/triagent-driven-development/
ls -la ~/.config/opencode/agents/trdd-*.md
```

### Codex

```bash
ls -la ~/.codex/skills/triagent-driven-development/
ls -la ~/.codex/agents/trdd-*.md
```
