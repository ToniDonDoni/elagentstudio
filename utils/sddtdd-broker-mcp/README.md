# sddtdd-broker-mcp

MCP task broker for Spec-Driven TDD broker mode. The broker reads the repository
state and SDDTDD journal, samples an LLM using the shared process skill plus the
broker skill, and returns the next allowed implementer task as JSON.

## Tools

### `init_task`

Initializes or resumes brokered work.

```json
{
  "repo_path": "/path/to/project",
  "user_input": "original user request",
  "process_skill": "spec-driven-tdd",
  "implementer_skill": "sddtdd-broker-implementer",
  "broker_skill": "sddtdd-task-broker"
}
```

### `verify_task`

Checks whether the implementer's claimed task completion is supported by the
current committed repository state and journal.

```json
{
  "repo_path": "/path/to/project",
  "task_id": "B-000001",
  "claimed_result": "SPEC.md committed and journaled",
  "evidence": ["commit abc123", "J-20260616-010203-002"]
}
```

### `next_task`

Returns the next legal task after `verify_task` passes.

```json
{
  "repo_path": "/path/to/project",
  "previous_task_id": "B-000001"
}
```

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
      include: [init_task, verify_task, next_task]
```

## Tests

```bash
uv run pytest -v
```
