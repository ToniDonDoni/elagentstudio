# ElAgentStudio

Reusable agent skills, workflows, and installation bundles for Codex, OpenCode, Hermes Agent, and related platforms.

## Available Skills

### Spec-Driven TDD (sdtdd)

A spec-driven development pipeline with review at every step and a complete audit trail. Designed for Hermes Agent.

- **Path:** `skills/spec-driven-tdd/`
- **Platform:** Hermes Agent
- **Requires:** pytest, Hermes Agent with `delegate_task`

### TriAgent-Driven Development (trdd)

A planner -> builder -> reviewer triagent workflow for structured implementation, bounded review loops, and task orchestration.

- **Path:** `skills/triagent-driven-development/`
- **Platforms:** OpenCode, Codex

---

## Installation

### Hermes Agent (Native)

Hermes supports native skill installation via taps (GitHub repo sources):

```bash
# Add this repo as a tap
hermes skills tap add ToniDonDoni/elagentstudio

# Install from repo path
hermes skills install ToniDonDoni/elagentstudio/skills/spec-driven-tdd
```

Or install directly from URL:

```bash
hermes skills install https://raw.githubusercontent.com/ToniDonDoni/elagentstudio/main/skills/spec-driven-tdd/SKILL.md
```


**Duplicate install behavior:** Warns and skips (use `--force` to reinstall).

### Hermes Agent (Fallback)

From a cloned repository:

```bash
# Install
install/hermes-spec-driven-tdd.sh

# Force reinstall
install/hermes-spec-driven-tdd.sh --override
```

---

### OpenCode

**Native plugin/skill mechanism:** NOT SUPPORTED by current CLI/version

OpenCode does not support installing skills from GitHub repos. The `opencode plugin` command only accepts npm modules.

**Fallback install:**

```bash
# Install
install/opencode-triagent.sh

# Force reinstall
install/opencode-triagent.sh --override
```

**Installed files:**
```
~/.config/opencode/skills/triagent-driven-development/
  SKILL.md
  README.md

~/.config/opencode/agents/
  trdd-orchestrator.md
  trdd-planner.md
  trdd-builder.md
  trdd-reviewer.md
```

---

### Codex (Native)

Codex plugin marketplace:

```bash
# Add this repo as a marketplace
codex plugin marketplace add ToniDonDoni/elagentstudio

# Install
codex plugin add triagent-driven-development@elagentstudio
```

### Codex (Fallback)

From a cloned repository:

```bash
# Install
install/codex-triagent.sh

# Force reinstall
install/codex-triagent.sh --override
```

---


