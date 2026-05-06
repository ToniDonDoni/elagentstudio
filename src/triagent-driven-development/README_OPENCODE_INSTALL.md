# Install TriDD Bundle into OpenCode

This bundle installs a TriAgent-Driven Development workflow for OpenCode.

It adds a primary orchestrator plus two triagents:
- `trdd-orchestrator` — routes work through the workflow
- `trdd-builder` — implements a task
- `trdd-reviewer` — reviews the result and returns approval or change requests

Workflow summary:
- orchestrator takes the task
- builder does the work
- reviewer approves it or requests changes
- if reviewer requests changes, the loop repeats

This bundle contains:
- `trdd-orchestrator.md`
- `trdd-builder.md`
- `trdd-reviewer.md`
- `SKILL.md`

## Install

from repo root
```bash
src/triagent-driven-development/opencode_install.sh
```

Force reinstall over existing files:
```bash
src/triagent-driven-development/opencode_install.sh --override
```

## How to use

1. Run OpenCode.
2. Open agent selection with `/agents`.
3. Choose `trdd-orchestrator`.
4. Choose the model you want to use.
5. Paste your task prompt.
6. Start your prompt with:

```text
Use the triagent-driven-development skill.
```
