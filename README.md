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

```bash
# Install
install/opencode-triagent.sh

# Force reinstall
install/opencode-triagent.sh --override
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

## Verification

### Hermes

```bash
hermes skills list | grep spec-driven-tdd
find ~/.hermes/skills -path '*spec-driven-tdd*' -type f | sort
```

### OpenCode

### Codex

```bash
ls -la ~/.codex/skills/triagent-driven-development/
ls -la ~/.codex/agents/trdd-*.md
```
