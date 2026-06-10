# ElAgentStudio

Reusable agent skills for Hermes Agent, Codex, and OpenCode.

---

## Spec-Driven TDD

A spec-driven development pipeline with review at every step and a complete audit trail.

**What it does:** You write a spec, the agent implements against it with RED-GREEN-REFACTOR cycle, and every step gets reviewed. Journal tracks all decisions.

**Platform:** Hermes Agent
**Requires:** pytest, Hermes Agent with `delegate_task`

### Install

```bash
# Native
hermes skills install ToniDonDoni/elagentstudio/skills/spec-driven-tdd

# From cloned repo
install/hermes-spec-driven-tdd.sh
install/hermes-spec-driven-tdd.sh --override
```

### Verify

```bash
hermes skills list | grep spec-driven-tdd
find ~/.hermes/skills -path '*spec-driven-tdd*' -type f | sort
```

### Use

```
/spec-driven-tdd <your task description>
```

---

## TriAgent-Driven Development

A planner -> builder -> reviewer triagent workflow for structured implementation, bounded review loops, and task orchestration.

**What it does:** Three agents collaborate: Planner breaks down the task, Builder implements, Reviewer checks. Bounded loops prevent infinite review cycles.

**Platforms:** Hermes Agent, Codex, OpenCode

### Install

```bash
# Hermes (native)
hermes skills install ToniDonDoni/elagentstudio/skills/triagent-driven-development

# Hermes (from cloned repo)
install/hermes-spec-driven-tdd.sh

# Codex (from cloned repo)
install/codex-triagent.sh
install/codex-triagent.sh --override

# OpenCode (from cloned repo)
install/opencode-triagent.sh
install/opencode-triagent.sh --override
```

### Verify

```bash
# Hermes
hermes skills list | grep triagent

# Codex
ls -la ~/.codex/skills/triagent-driven-development/
ls -la ~/.codex/agents/trdd-*.md

# OpenCode
ls -la ~/.config/opencode/skills/triagent-driven-development/
ls -la ~/.config/opencode/agents/trdd-*.md
```

### Use

```
/trdd <your task description>
```
