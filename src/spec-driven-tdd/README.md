# Spec-Driven TDD -- Hermes Agent Skill

A spec-driven development pipeline with review at every step and a complete audit trail.

## Installation

The skill is already installed if you use the standard Hermes Agent configuration:

```bash
ls ~/.hermes/skills/software-development/spec-driven-tdd/SKILL.md
```

If installing manually from the cloned repo:

```bash
# Check if already installed
if [ -f ~/.hermes/skills/software-development/spec-driven-tdd/SKILL.md ]; then
  echo "Skill already installed. Use -f to force overwrite."
else
  # Create the skill directory
  mkdir -p ~/.hermes/skills/software-development/spec-driven-tdd/references

  # Copy only what the skill needs -- SKILL.md, README, references
  # Not the entire repo (no test dirs, specs, journal, etc.)
  cp SKILL.md README.md ~/.hermes/skills/software-development/spec-driven-tdd/
  cp references/* ~/.hermes/skills/software-development/spec-driven-tdd/references/
fi
```

The result:

```
~/.hermes/skills/software-development/spec-driven-tdd/
|-- SKILL.md          # Pipeline rules, phases, journaling
|-- README.md          # This file
'-- references/        # Reference artifacts (loaded via skill_view)
    '-- SPEC-EXAMPLE.md
```

### What's Included

| File | Description |
|------|-------------|
| `SKILL.md` | Pipeline rules, phases, journaling, integration examples |
| `README.md` | Installation, file reference, and usage guide |
| `references/SPEC-EXAMPLE.md` | **Canonical reference artifact** -- full Counter API walkthrough from user input to DONE. Required reading before using the pipeline. |

## Usage

### Manually (single session)

```python
from hermes_tools import skill_view
skill_view("spec-driven-tdd")
```

### Via agent prompt

The skill is always listed in the agent's `<available_skills>` index. The agent loads it automatically via `skill_view()` when a relevant task is detected. Just mention the pipeline name in your prompt:

> "Run this through spec-driven-tdd."

Or load it explicitly in a Hermes Gateway session:

```
/skill spec-driven-tdd
```

### In a cron job

```bash
hermes cron create \
  --name "spec-driven-demo" \
  --schedule "0 9 * * 1" \
  --skills spec-driven-tdd,writing-plans \
  --prompt "Take SPEC.md from /home/user/project, run through spec-driven-tdd pipeline."
```

### In a subagent

```python
delegate_task(
    goal="Implement via spec-driven-tdd.",
    context="Spec: ... \nJOURNAL_PATH=/tmp/JOURNAL.log",
    toolsets=["terminal", "file", "skills"]
)
```

## Requirements

- **Hermes Agent** (any version with `delegate_task`)
- **pytest** (for tests)
- Optional: **Codex CLI** / **Claude Code** / **OpenCode** for independent review
