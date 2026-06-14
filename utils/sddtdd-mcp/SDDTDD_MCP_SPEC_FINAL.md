# sddtdd-mcp

## Purpose

`sddtdd-mcp` is a minimal MCP review proxy for Hermes Agent.

Hermes sends a free-form review request. The server records the request, captures the current Git state, asks an independent reviewer, records the result in its own append-only access log, and returns the verdict to Hermes.

The goal is to make review activity independently observable and comparable with Git history.

## Scope

The first version has one MCP tool:

```text
review
```

The server:

- accepts a review request;
- captures repository metadata itself;
- performs the review through MCP sampling;
- writes request and result events to its access log;
- returns a structured result.

The server reviews committed repository state and does not modify the repository.

## MCP Contract

### Request

```json
{
  "repo_path": "/work/gorillas-game",
  "review_type": "RED review",
  "task_id": "T-000003",
  "prompt": "Review the committed physics tests and RED evidence. Verify that the tests fail because the behavior is missing. Review only; do not modify files."
}
```

Fields:

- `repo_path` — absolute path to the Git repository;
- `review_type` — free-form label describing what is being reviewed;
- `task_id` — optional free-form task identifier;
- `prompt` — complete review instruction, stored exactly as received.

The server does not restrict `review_type` to a fixed list.

### Response

```json
{
  "request_id": "01JXW8W6Q6Q8M2Q6S2T5W9R4P7",
  "status": "COMPLETED",
  "verdict": "PASS",
  "response": "The tests correctly prove the missing behavior.",
  "stale": false
}
```

`status`:

```text
COMPLETED
STALE
ERROR
```

`verdict`:

```text
PASS
FAIL
NEEDS_CLARIFICATION
null
```

A review is usable as approval only when:

```text
status = COMPLETED
verdict = PASS
stale = false
```

## Processing Flow

When `review` is called, the server:

1. generates a `request_id`;
2. captures the server timestamp;
3. captures the repository branch, current `HEAD` SHA, and dirty state;
4. appends a `review_started` event to the access log;
5. sends the prompt to an independent reviewer through MCP sampling;
6. receives the verdict and full reviewer response;
7. reads `HEAD` again;
8. marks the result `STALE` if `HEAD` changed during review;
9. appends a `review_completed` event to the access log;
10. returns the structured result to Hermes.

The reviewer evaluates the committed repository state identified by `reviewed_head_sha`.

## Access Log

Default path:

```text
<repo>/.git/sddtdd/review-access.jsonl
```

The format is JSON Lines: one JSON object per line.

### Request Event

```json
{
  "event": "review_started",
  "request_id": "01JXW8W6Q6Q8M2Q6S2T5W9R4P7",
  "timestamp_utc": "2026-06-14T17:42:11.184Z",
  "repo_path": "/work/gorillas-game",
  "branch": "feature/physics",
  "head_sha": "8d49454f76b5c23f4d5e78fb52a13d30e3a7b8c1",
  "working_tree_dirty": false,
  "review_type": "RED review",
  "task_id": "T-000003",
  "prompt": "Review the committed physics tests and RED evidence. Verify that the tests fail because the behavior is missing. Review only; do not modify files."
}
```

### Successful Result Event

```json
{
  "event": "review_completed",
  "request_id": "01JXW8W6Q6Q8M2Q6S2T5W9R4P7",
  "timestamp_utc": "2026-06-14T17:42:14.901Z",
  "repo_path": "/work/gorillas-game",
  "review_type": "RED review",
  "task_id": "T-000003",
  "head_sha_before": "8d49454f76b5c23f4d5e78fb52a13d30e3a7b8c1",
  "head_sha_after": "8d49454f76b5c23f4d5e78fb52a13d30e3a7b8c1",
  "status": "COMPLETED",
  "verdict": "PASS",
  "response": "The committed tests cover the required physics behavior and fail because the implementation is absent.",
  "stale": false,
  "duration_ms": 3717
}
```

### Failed Review Event

```json
{
  "event": "review_completed",
  "request_id": "01JXW91QZ7W2Y18ZPX0G5M7N4H",
  "timestamp_utc": "2026-06-14T17:44:05.022Z",
  "repo_path": "/work/gorillas-game",
  "review_type": "RED review",
  "task_id": "T-000003",
  "head_sha_before": "8d49454f76b5c23f4d5e78fb52a13d30e3a7b8c1",
  "head_sha_after": "8d49454f76b5c23f4d5e78fb52a13d30e3a7b8c1",
  "status": "COMPLETED",
  "verdict": "FAIL",
  "response": "The test fails because the module path is invalid, not because the required behavior is absent.",
  "stale": false,
  "duration_ms": 2915
}
```

### Reviewer Error Event

```json
{
  "event": "review_completed",
  "request_id": "01JXW9F1MWK0X9JB7R5C3A6T2V",
  "timestamp_utc": "2026-06-14T17:46:08.310Z",
  "repo_path": "/work/gorillas-game",
  "review_type": "architecture review",
  "task_id": null,
  "head_sha_before": "91a7c2fb011d5f3858c8c362db9ebc1681f01377",
  "head_sha_after": "91a7c2fb011d5f3858c8c362db9ebc1681f01377",
  "status": "ERROR",
  "verdict": null,
  "response": "Reviewer timeout",
  "stale": false,
  "duration_ms": 120000
}
```

### Stale Review Event

```json
{
  "event": "review_completed",
  "request_id": "01JXW98B9E2P7YJ4M3Q6V1A5KC",
  "timestamp_utc": "2026-06-14T17:47:23.616Z",
  "repo_path": "/work/gorillas-game",
  "review_type": "GREEN review",
  "task_id": "T-000003",
  "head_sha_before": "91a7c2fb011d5f3858c8c362db9ebc1681f01377",
  "head_sha_after": "ca3ef25139021fbda195e5b228793ad8548b8239",
  "status": "STALE",
  "verdict": "PASS",
  "response": "The reviewed implementation passes the requested checks.",
  "stale": true,
  "duration_ms": 4212
}
```

## User Stories

### Successful Review

As Hermes, I send a repository path, a free-form review type, an optional task ID, and a review prompt.

The server records the request, captures Git `HEAD`, performs the review, records the result, and returns `COMPLETED`.

### Failed Review

As Hermes, I receive `FAIL` when the reviewer finds a problem.

The access log preserves the original request, reviewed commit, verdict, and reviewer response.

### Reviewer Unavailable

As Hermes, I receive `ERROR` when the reviewer times out or cannot complete the request.

The access log preserves the request and the error.

### Repository Changed During Review

As Hermes, I receive `STALE` when repository `HEAD` changes before the review completes.

The access log preserves both commit SHAs and the reviewer response.

## Hermes Configuration

```yaml
mcp_servers:
  sddtdd_review:
    command: "uv"
    args:
      - "--directory"
      - "/absolute/path/to/sddtdd-mcp"
      - "run"
      - "server.py"
    timeout: 180
    connect_timeout: 30
    supports_parallel_tool_calls: true
    tools:
      include: [review]
      resources: false
      prompts: false
    sampling:
      enabled: true
      timeout: 120
```

Hermes registers the tool as:

```text
mcp_sddtdd_review_review
```

## Resulting Artifacts

```text
sddtdd-mcp/
├── pyproject.toml
├── server.py
├── README.md
└── tests/
    ├── test_review.py
    ├── test_access_log.py
    └── test_stale_review.py
```

Runtime artifact:

```text
~/.hermes/sddtdd-mcp/review-access.jsonl
```

## Acceptance Criteria

- Hermes discovers `mcp_sddtdd_review_review`.
- `review` accepts the four request fields.
- The server records `review_started` before reviewer execution.
- The server records `review_completed` after reviewer execution.
- Both events share the same `request_id`.
- The log contains the exact `review_type`, `task_id`, and `prompt` received from Hermes.
- The server records timestamps, branch, dirty state, and Git SHAs itself.
- `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, `ERROR`, and `STALE` are represented correctly.
- A changed `HEAD` produces `STALE`.
- Parallel reviews create independent request IDs and log records.
- Restarting the server preserves the access log.
- All automated tests pass.
