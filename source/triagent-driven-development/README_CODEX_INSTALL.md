# Install TriDD Bundle into Codex

This bundle installs a TriAgent-Driven Development workflow for Codex.

It adds a primary orchestrator plus three triagents:
- `trdd-orchestrator` — routes work through the workflow
- `trdd-planner` — breaks work into concrete tasks
- `trdd-builder` — implements a task
- `trdd-reviewer` — reviews the result and returns approval or change requests

Workflow summary:
- orchestrator receives the task
- planner decomposes it when needed
- builder implements one task at a time
- reviewer checks the result
- if reviewer requests changes, the work goes through a bounded rework loop

This bundle contains:
- `trdd-orchestrator.md`
- `trdd-planner.md`
- `trdd-builder.md`
- `trdd-reviewer.md`
- `SKILL.md`

## Install and verify

Global install:

```bash
mkdir -p ~/.codex/agents
mkdir -p ~/.codex/skills/triagent-driven-development
cp source/triagent-driven-development/trdd-*.md ~/.codex/agents/
cp source/triagent-driven-development/SKILL.md ~/.codex/skills/triagent-driven-development/
ls ~/.codex/agents/trdd-*.md
ls ~/.codex/skills/triagent-driven-development/SKILL.md
```

Project-local install:

```bash
mkdir -p ./.codex/agents
mkdir -p ./.codex/skills/triagent-driven-development
cp source/triagent-driven-development/trdd-*.md ./.codex/agents/
cp source/triagent-driven-development/SKILL.md ./.codex/skills/triagent-driven-development/
```

## How to use

1. Launch Codex in the workspace where you want to work.
2. Start your next prompt with the exact header line below so Codex knows which skill to load.
3. Then write the actual task right below that line.

Use this exact header:

```text
Use the triagent-driven-development skill.
```

Then continue with the task:

```text
Use the triagent-driven-development skill.

<your task here>
```

Example:

```text
Use the triagent-driven-development skill.

Bug fix: Codex tool call parse failures should not halt session.
Investigate where malformed tool-call argument parsing escapes into a fatal halt.
Make invalid tool arguments return a normal tool error/result so the model can retry.
Keep fatal runtime/system errors unchanged.
Work in /work/codex_workspace.
```
