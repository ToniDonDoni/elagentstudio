# ElAgentStudio

Reusable agent skills, workflows, and installation bundles for Codex, OpenCode, Hermes Agent, and related platforms.

## Navigation

- [Spec-Driven TDD](#spec-driven-tdd)
- [TriAgent-Driven Development](#triagent-driven-development-trdd)

## Available Skills

### Spec-Driven TDD

A spec-driven development test-driven development (TDD) pipeline with review at every step and a complete audit trail. Every line of production code passes through: spec -> review -> decompose -> test -> RED -> GREEN -> final review. Designed for Hermes Agent.

- **Path:** `skills/spec-driven-tdd/`
- **Platform:** Hermes Agent
- **Requires:** pytest, Hermes Agent with `delegate_task`; optional SDDTDD reviewer and orchestrator MCP servers
- **Orchestrator role files:** `SKILL-IMPLEMENTER.md` and `SKILL-ORCHESTRATOR.md` live inside this same skill directory. They are not separate installable skills.

#### Install Spec-Driven TDD

```bash
hermes skills install ToniDonDoni/elagentstudio/skills/spec-driven-tdd
```

#### Verify Spec-Driven TDD

```bash
hermes skills list | grep spec-driven-tdd
```

#### Use Spec-Driven TDD

```prompt
Use the spec-driven-tdd skill for <your task description>
```

For orchestrator mode, install only `spec-driven-tdd` and use its in-folder role files:

```prompt
Use spec-driven-tdd orchestrator mode. The implementer follows skills/spec-driven-tdd/SKILL-IMPLEMENTER.md, and the MCP task orchestrator follows skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md.
```

---

### TriAgent-Driven Development (trdd)

A planner -> builder -> reviewer triagent workflow for structured implementation, bounded review loops, and task orchestration.

- **Path:** `skills/triagent-driven-development/`
- **Platforms:** Codex, OpenCode

#### Install TriAgent-Driven Development

From the repository root, choose your tool and read its install guide.

##### Install TriAgent for OpenCode

```bash
cat skills/triagent-driven-development/README_OPENCODE_INSTALL.md
```

##### Install TriAgent for Codex

```bash
cat skills/triagent-driven-development/README_CODEX_INSTALL.md
```

