# ElAgentStudio

Reusable agent skills, workflows, and installation bundles for Codex, OpenCode, Hermes Agent, and related platforms.

## Available Skills

### TriAgent-Driven Development (trdd)

A planner -> builder -> reviewer triagent workflow for structured implementation, bounded review loops, and task orchestration.

- Path: `src/triagent-driven-development/`
- Platforms: Codex, OpenCode

## Install

From the repository root, choose your tool and read its install guide:

### OpenCode


```bash
cat src/triagent-driven-development/README_OPENCODE_INSTALL.md
```

### Codex

```bash
cat src/triagent-driven-development/README_CODEX_INSTALL.md
```

### Codex (Plugin)

```bash
codex plugin marketplace add ToniDonDoni/elagentstudio
codex plugin add triagent-driven-development@elagentstudio
```

---

### Spec-Driven TDD (sdtdd)

A spec-driven development pipeline with review at every step and a complete audit trail. Every line of production code passes through: spec -> review -> decompose -> test -> RED -> GREEN -> refactor -> final review. Designed for Hermes Agent.

- **Path:** `src/spec-driven-tdd/`
- **Platform:** Hermes Agent
- **Requires:** pytest, Hermes Agent with `delegate_task`

### Hermes

```bash
cat src/spec-driven-tdd/README.md
```

### Hermes (Plugin)

```bash
hermes skills install ToniDonDoni/elagentstudio/src/spec-driven-tdd
```
