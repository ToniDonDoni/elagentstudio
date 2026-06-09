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

# Search for available skills
hermes skills search spec-driven-tdd

# Install from tap
hermes skills install ToniDonDoni/elagentstudio/skills/spec-driven-tdd
```

Or install directly from URL:

```bash
hermes skills install https://raw.githubusercontent.com/ToniDonDoni/elagentstudio/main/skills/spec-driven-tdd/SKILL.md
```

**Installed files:**
```
~/.hermes/skills/software-development/spec-driven-tdd/
  SKILL.md
  README.md
  references/SPEC-EXAMPLE.md
```

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

OpenCode does not support native skill installation from GitHub repos. Use the fallback script.

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

Codex supports plugin marketplaces:

```bash
# Add this repo as a marketplace
codex plugin marketplace add ToniDonDoni/elagentstudio

# List available plugins
codex plugin list

# Install
codex plugin add elagentstudio
```

**Note:** Codex plugin installs the skill files. Agent files may require the fallback script.

### Codex (Fallback)

From a cloned repository:

```bash
# Install
install/codex-triagent.sh

# Force reinstall
install/codex-triagent.sh --override
```

**Installed files:**
```
~/.codex/skills/triagent-driven-development/
  SKILL.md
  README.md

~/.codex/agents/
  trdd-orchestrator.md
  trdd-planner.md
  trdd-builder.md
  trdd-reviewer.md
```

---

## Verification

### Hermes

```bash
hermes skills list | grep spec-driven-tdd
hermes skills inspect spec-driven-tdd
```

### OpenCode

```bash
ls -la ~/.config/opencode/skills/triagent-driven-development/
ls -la ~/.config/opencode/agents/trdd-*.md
```

### Codex

```bash
codex plugin list
ls -la ~/.codex/skills/triagent-driven-development/
ls -la ~/.codex/agents/trdd-*.md
```

---

## Repository Structure

```
elagentstudio/
├── skills/
│   ├── spec-driven-tdd/
│   │   ├── SKILL.md
│   │   ├── README.md
│   │   └── references/
│   │       └── SPEC-EXAMPLE.md
│   └── triagent-driven-development/
│       ├── SKILL.md
│       ├── README.md
│       └── agents/
│           ├── trdd-orchestrator.md
│           ├── trdd-planner.md
│           ├── trdd-builder.md
│           └── trdd-reviewer.md
├── install/
│   ├── hermes-spec-driven-tdd.sh
│   ├── opencode-triagent.sh
│   └── codex-triagent.sh
├── .codex-plugin/
│   └── plugin.json
├── src/                          # Legacy source (backward compat)
│   ├── spec-driven-tdd/
│   └── triagent-driven-development/
└── README.md
```

## Existing detailed guides

```bash
cat skills/spec-driven-tdd/README.md
cat skills/triagent-driven-development/README.md
```
