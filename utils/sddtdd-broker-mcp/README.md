# sddtdd-broker-mcp

MCP task broker for Spec-Driven TDD broker mode. The broker reads the
committed repository state, the SDDTDD journal, samples an LLM using the
shared process skill plus the in-folder orchestrator role file, and answers
two questions from the implementer: what is the next task, and is the
current task really complete.

The orchestrator role file (`skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md`)
is the source of truth for the workflow order and the review rules. The
implementer only needs the two decision tools.

## Tools

### `init`

Start or resume brokered work for a repository.

```json
{
  "repo_path": "/path/to/project",
  "user_input": "original user request"
}
```

### `getNextTask`

Ask the orchestrator for the next task, or for `complete` / `blocked`.

```json
{
  "repo_path": "/path/to/project",
  "previous_task_id": "B-000001"
}
```

`previous_task_id` is optional. On the first call after `init`, omit it.
On subsequent calls, pass the task id returned by the previously verified
task.

The response is one of:

- `{"status": "TASK", "task_id": "...", "summary": "...", "rationale": "..."}`
- `{"status": "complete", ...}`
- `{"status": "blocked", ...}`

### `reviewTask`

Ask the orchestrator to verify that the current task is genuinely complete.

```json
{
  "repo_path": "/path/to/project",
  "task_id": "B-000001",
  "claimed_result": "SPEC.md committed and journaled",
  "evidence": ["commit abc123", "J-20260616-010203-002"]
}
```

The response is one of:

- `PASS` — the task is verified; call `getNextTask` again.
- `FAIL` — fix the listed gaps and call `reviewTask` again.
- `NEEDS_CLARIFICATION` — supply the missing information.
- `ERROR` — resolve tooling or repository state first.

On `PASS` the broker writes a `task_verified` event to
`<repo>/.git/sddtdd/broker-access.jsonl` so subsequent `getNextTask` calls
can confirm the previous task was verified from committed state.

## Hermes Config

```yaml
mcp_servers:
  sddtdd_broker:
    command: "uv"
    args:
      - "--directory"
      - "/path/to/elagentstudio/utils/sddtdd-broker-mcp"
      - "run"
      - "server.py"
    sampling:
      enabled: true
      timeout: 120
    tools:
      include: [init, getNextTask, reviewTask]
```

## Tests

```bash
uv run pytest -v
```
