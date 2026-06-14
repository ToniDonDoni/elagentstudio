# sddtdd-mcp

Minimal MCP review proxy for Hermes Agent.

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

## Tests

```bash
uv run pytest -v
```

## Hermes Config

```yaml
mcp_servers:
  sddtdd_review:
    command: "uv"
    args:
      - "--directory"
      - "/path/to/sddtdd-mcp"
      - "run"
      - "server.py"
    sampling:
      enabled: true
      timeout: 120
    tools:
      include: [review]
```
