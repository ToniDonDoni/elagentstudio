# ElAgentStudio

Reusable agent skills, workflows, and installation bundles for Codex, OpenCode, Hermes Agent, and related platforms.

## Available Skills

### TriAgent-Driven Development (trdd)

A planner -> builder -> reviewer triagent workflow for structured implementation, bounded review loops, and task orchestration.

- Path: `src/triagent-driven-development/`
- Platforms: Codex, OpenCode

### Spec-Driven TDD (sdtdd)

A spec-driven development pipeline with review at every step and a complete audit trail. Designed for Hermes Agent.

- Path: `src/spec-driven-tdd/`
- Platform: Hermes Agent
- Requires: pytest, Hermes Agent with `delegate_task`

## Install

### Hermes Agent

From a cloned repository:

```bash
install/hermes-spec-driven-tdd.sh
```

Force reinstall:

```bash
install/hermes-spec-driven-tdd.sh --override
```

If your Hermes version supports installing from a GitHub repo/path directly:

```bash
hermes skills install ToniDonDoni/elagentstudio/src/spec-driven-tdd
```

### OpenCode

From a cloned repository:

```bash
install/opencode-triagent.sh
```

Force reinstall:

```bash
install/opencode-triagent.sh --override
```

### Codex

Plugin-style install, when supported by your Codex CLI:

```bash
codex plugin marketplace add ToniDonDoni/elagentstudio
codex plugin add elagentstudio@elagentstudio
```

Manual install from a cloned repository:

```bash
install/codex-triagent.sh
```

Force reinstall:

```bash
install/codex-triagent.sh --override
```

## Existing detailed guides

```bash
cat src/triagent-driven-development/README_OPENCODE_INSTALL.md
cat src/triagent-driven-development/README_CODEX_INSTALL.md
cat src/spec-driven-tdd/README.md
```
