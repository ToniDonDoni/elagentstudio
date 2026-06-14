# sddtdd-mcp — Specification

**Reference:** `SPEC-DRAFT.md` (derived from `SDDTDD_MCP_SPEC_FINAL.md`)  
**Spec ID:** S-SDDTDD-MCP-01  
**Version:** 1.0

---

## System Goal

Implement a minimal MCP server that acts as a review proxy for Hermes Agent. The server accepts review requests, captures repository Git state, delegates the review to an independent LLM via MCP sampling, records the full interaction in an append-only access log, and returns a structured verdict.

---

## Functional Requirements

### FR-001 — MCP Tool Registration
The server MUST register exactly one MCP tool named `review` via the MCP protocol.

### FR-002 — Review Request Fields
The `review` tool MUST accept these input fields:
- `repo_path` (string, required) — absolute path to a Git repository
- `review_type` (string, required) — free-form label for the review
- `task_id` (string, optional) — free-form task identifier
- `prompt` (string, required) — the complete review instruction

### FR-003 — Request ID Generation
The server MUST generate a unique `request_id` for each review call. The `request_id` MUST be a string that is unique across all calls within the same server instance.

### FR-004 — Git State Capture Before Review
Before executing the review, the server MUST capture:
- Current branch name
- Current `HEAD` commit SHA
- Working tree dirty state (true/false)

### FR-005 — Review Execution via MCP Sampling
The server MUST send the `prompt` to an independent LLM reviewer through MCP sampling (the `sampling` MCP capability). The server MUST NOT modify files in the repository.

### FR-006 — Git State Capture After Review
Immediately after receiving the reviewer response, the server MUST capture `HEAD` SHA again.

### FR-007 — Stale Detection
If `HEAD` changed between the before-review and after-review captures, the result MUST be marked `stale: true` and `status: STALE`. Otherwise `stale: false`.

### FR-008 — Structured Response
The `review` tool MUST return a response object containing:
- `request_id` — the unique request identifier
- `status` — `COMPLETED`, `STALE`, or `ERROR`
- `verdict` — `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, or `null` (on ERROR)
- `response` — the full reviewer response text or error message
- `stale` — boolean

### FR-009 — Access Log: review_started Event
Before executing the review, the server MUST append a `review_started` event to the access log. The event MUST contain:
- `event`: "review_started"
- `request_id`
- `timestamp_utc` (ISO 8601 UTC)
- `repo_path`
- `branch`
- `head_sha`
- `working_tree_dirty`
- `review_type`
- `task_id`
- `prompt`

### FR-010 — Access Log: review_completed Event
After receiving the reviewer result, the server MUST append a `review_completed` event to the access log. The event MUST contain:
- `event`: "review_completed"
- `request_id`
- `timestamp_utc`
- `repo_path`
- `review_type`
- `task_id`
- `head_sha_before`
- `head_sha_after`
- `status`
- `verdict`
- `response`
- `stale`
- `duration_ms`

### FR-011 — Access Log Persistence
The access log MUST be stored as JSON Lines (one JSON object per line) at the path `<repo>/.git/sddtdd/review-access.jsonl` by default, configurable via environment variable `SDDTDD_LOG_PATH`.

### FR-012 — Status Values
The server MUST support these status values:
- `COMPLETED` — review finished successfully
- `STALE` — repository changed during review
- `ERROR` — reviewer unavailable or unexpected error

### FR-013 — Error Handling
If the reviewer times out, returns an error, or an unexpected exception occurs, the server MUST:
- Set `status: ERROR`
- Set `verdict: null`
- Record the error in `response`
- Append a `review_completed` event to the access log

### FR-014 — Log Preservation Across Restarts
The access log file MUST be opened in append mode so that data persists across server restarts.

---

## Non-Functional Requirements

### NFR-001 — Python Implementation
The server MUST be implemented in Python 3.10+, using the MCP Python SDK.

### NFR-002 — No External Dependencies Beyond MCP SDK
The server MUST NOT require external databases or services. All state is stored in the access log file only.

### NFR-003 — Hermes-Discoverable
The server MUST be startable via `uv run server.py` and discoverable by Hermes via MCP protocol.

### NFR-004 — Parallel Reviews
Concurrent review calls MUST create independent request IDs and independent log records. Log appends MUST be thread-safe.

---

## Constraints

- C-001: Project located at `/work/sddtdd-mcp`
- C-002: Must follow spec-driven-tdd workflow
- C-003: Use `uv` for dependency management (pyproject.toml + uv.lock)
- C-004: Tests in `tests/` directory, runnable via `uv run pytest`
- C-005: Server entry point: `server.py`

---

## Observable Acceptance Criteria

1. `uv run server.py` starts an MCP server
2. Hermes discovers `mcp_sddtdd_review_review` tool
3. Sending a review request returns a structured response with request_id, status, verdict
4. The access log file is created with `review_started` and `review_completed` events
5. Both log events share the same `request_id`
6. The log contains exact `review_type`, `task_id`, and `prompt`
7. `PASS`, `FAIL`, `NEEDS_CLARIFICATION` are correctly returned
8. Changing `HEAD` during a review produces `STALE`
9. Concurrent reviews produce independent records
10. All automated tests pass

---

## Resulting Artifacts

```
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
```
<repo>/.git/sddtdd/review-access.jsonl
```
