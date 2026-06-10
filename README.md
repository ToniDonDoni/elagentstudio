# ElAgentStudio

Reusable agent skills, workflows, and installation bundles for Codex, OpenCode, Hermes Agent, and related platforms.

## Available Skills

### TriAgent-Driven Development (trdd)

A planner -> builder -> reviewer triagent workflow for structured implementation, bounded review loops, and task orchestration.

- Path: `skills/triagent-driven-development/`
- Platforms: Codex, OpenCode

## Install

From the repository root, choose your tool and read its install guide:

### OpenCode


```bash
cat skills/triagent-driven-development/README_OPENCODE_INSTALL.md
```

### Codex

```bash
cat skills/triagent-driven-development/README_CODEX_INSTALL.md
```

---

### Spec-Driven TDD

A spec-driven development test-driven development (TDD) pipeline with review at every step and a complete audit trail. Every line of production code passes through: spec -> review -> decompose -> test -> RED -> GREEN -> final review. Designed for Hermes Agent.

- **Path:** `skills/spec-driven-tdd/`
- **Platform:** Hermes Agent
- **Requires:** pytest, Hermes Agent with `delegate_task`

### Install

```bash
hermes skills install ToniDonDoni/elagentstudio/skills/spec-driven-tdd
```

### Verify

```bash
hermes skills list | grep spec-driven-tdd
```

### Use

prompt
```
Use the spec-driven-tdd skill for <your task description>
```

