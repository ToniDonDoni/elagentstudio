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

**Test result:** PASS - installs all expected files (SKILL.md, README.md, references/SPEC-EXAMPLE.md)

**Duplicate install behavior:** Warns and skips (use `--force` to reinstall)

### Hermes Agent (Fallback)

From a cloned repository:

```bash
# Install
install/hermes-spec-driven-tdd.sh

# Force reinstall
install/hermes-spec-driven-tdd.sh --override
```

**Test result:** PASS - installs to `~/.hermes/skills/software-development/spec-driven-tdd/`

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

**Test result:** PASS (fallback script)

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

**Native plugin marketplace:** PARTIAL - requires repo restructure to `plugins/<name>/` layout

Codex plugin marketplace expects a `plugins/` directory at repo root with each plugin under `plugins/<name>/`. Current repo structure is not compatible.

**Fallback install:**

```bash
# Install
install/codex-triagent.sh

# Force reinstall
install/codex-triagent.sh --override
```

**Test result:** PASS (fallback script)

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

---

## Repository Structure

```
elagentstudio/
├── skills/                         # Native installable skills
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
├── install/                        # Fallback install scripts
│   ├── hermes-spec-driven-tdd.sh
│   ├── opencode-triagent.sh
│   └── codex-triagent.sh
├── .codex-plugin/
│   └── plugin.json
├── src/                            # Legacy source (backward compat)
│   ├── spec-driven-tdd/
│   └── triagent-driven-development/
└── README.md
```
