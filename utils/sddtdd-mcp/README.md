# sddtdd-mcp

MCP review and orchestration registrar for the Spec-Driven TDD skill.

## Quick Start

```bash
uv sync
uv run server.py
```

## MCP Tool

### `review`

Accepts a repository path, review type, optional task ID, and prompt. Captures Git state, asks an independent reviewer via MCP sampling, records to access log, returns verdict.

**Request:**
```json
{
  "repo_path": "/work/gorillas-game",
  "review_type": "RED review",
  "task_id": "T-000003",
  "prompt": "Review the committed tests and RED evidence."
}
```

**Response:**
```json
{
  "request_id": "01JXW8W6Q6Q8M2Q6S2T5W9R4P7",
  "status": "COMPLETED",
  "verdict": "PASS",
  "response": "The tests correctly prove the missing behavior.",
  "stale": false
}
```

## Access Log

Default: `<repo>/.git/sddtdd/review-access.jsonl`
Override: `SDDTDD_LOG_PATH` env var

Orchestrator requests are appended to `<repo>/.sddtdd_skill/orchestrator-access.jsonl`.
This includes `getNextTask` and both task-status operations. Review requests
remain in the separate review access log.

## Task status

The `taskStatus` tool has two operations:

```json
{
  "repo_path": "/work/gorillas-game",
  "operation": "update",
  "task_id": "T-000003",
  "task_kind": "IMPLEMENTATION",
  "status": "RUNNING",
  "role": "implementer",
  "execution_id": "background-task-123",
  "worktree_path": "/work/gorillas-game/.worktrees/T-000003"
}
```

State is atomically persisted at `<repo>/.sddtdd_skill/task-status.json` and
keeps the current task plus its status history. Use `operation: "get"` with a
`task_id` to read one task, or without a task ID to read all tasks. The
registrar includes this document in the `getNextTask` model context. Only
implementer and reviewer agents should call `operation: "update"`; the
dispatcher reads state and does not impersonate them.

`getNextTask` returns `orchestrator_result.status: "notReady"` with no
`next_task` while issued tasks are still active. A task that receives no
`taskStatus(update)` report for 600 seconds is marked `FAILED` with
`retryable: true` and can be issued again. Configure the timeout with
`SDDTDD_TASK_TIMEOUT_SECONDS`.

## Tests

```bash
uv run --dev pytest tests/test_task_status.py
uv run python server_e2e_test.py
```

## Hermes Config

```yaml
mcp_servers:
  sddtdd:
    command: uv
    args:
    - --directory
    - /work/elagentstudio/utils/sddtdd-mcp
    - run
    - server.py
    env:
      PATH: /root/.local/bin:/usr/bin:/bin
    sampling:
      enabled: true
      timeout: 1228
      max_rpm: 5555
      max_tool_rounds: 5555
    timeout: 1228
    connect_timeout: 30
    max_tokens_cap: 40000
```
