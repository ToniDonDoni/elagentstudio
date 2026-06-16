# ElAgentStudio

Reusable agent skills, workflows, and installation bundles for Codex, OpenCode, Hermes Agent, and related platforms.

## Navigation

- [Spec-Driven TDD](#spec-driven-tdd)
- [TriAgent-Driven Development](#triagent-driven-development-trdd)
- [SDDTDD Broker Implementer](#sddtdd-broker-implementer)
- [SDDTDD Task Broker](#sddtdd-task-broker)

## Available Skills

### Spec-Driven TDD

A spec-driven development test-driven development (TDD) pipeline with review at every step and a complete audit trail. Every line of production code passes through: spec -> review -> decompose -> test -> RED -> GREEN -> final review. Designed for Hermes Agent.

- **Path:** `skills/spec-driven-tdd/`
- **Platform:** Hermes Agent
- **Requires:** pytest, Hermes Agent with `delegate_task`; optional SDDTDD reviewer and broker MCP servers

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


---

### SDDTDD Broker Implementer

Implementer-side skill for Spec-Driven TDD broker mode. The primary agent asks a
task-broker MCP server for initialization, verification, and the next task instead
of choosing workflow stages itself.

- **Path:** `skills/sddtdd-broker-implementer/`
- **Platform:** Hermes Agent
- **Requires:** `spec-driven-tdd`, SDDTDD task-broker MCP server

#### Install SDDTDD Broker Implementer

```bash
hermes skills install ToniDonDoni/elagentstudio/skills/sddtdd-broker-implementer
```

#### Use SDDTDD Broker Implementer

```prompt
Use spec-driven-tdd in broker mode with sddtdd-broker-implementer for <your task>.
```

---

### SDDTDD Task Broker

Broker-side decision skill for an MCP server. It reads committed repository state
and `JOURNAL_SDD_TDD_SKILL.log`, then returns the next legal Spec-Driven TDD task
without implementing or reviewing artifacts.

- **Path:** `skills/sddtdd-task-broker/`
- **Platform:** MCP sampling server for Hermes Agent
- **Requires:** `spec-driven-tdd`, `utils/sddtdd-broker-mcp/`

#### Install SDDTDD Task Broker

```bash
hermes skills install ToniDonDoni/elagentstudio/skills/sddtdd-task-broker
```

#### Configure Broker MCP

See `utils/sddtdd-broker-mcp/README.md`.
