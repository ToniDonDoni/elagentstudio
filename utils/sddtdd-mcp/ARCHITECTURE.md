# sddtdd-mcp — Architecture

**Reference:** `SPEC.md` (S-SDDTDD-MCP-01)  
**Version:** 1.0

---

## Overview

`sddtdd-mcp` is a Python MCP server implementing a single `review` tool. When called, it captures Git state, delegates the review to an LLM via MCP sampling, records the interaction in a JSON Lines access log, and returns a structured response.

---

## Technology

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.10+ | Hermes environment standard |
| MCP SDK | `mcp` (PyPI) | Official MCP protocol implementation |
| Git introspection | `subprocess` (git CLI) | No GitPython dependency; repo already has git |
| Testing | `pytest` | Standard Python test framework |
| Dependency mgmt | `uv` / `pyproject.toml` | Per constraint C-003 |

---

## Components

```
server.py              ← MCP server entry point
├── handle_review()    ← review tool handler (the only tool)
│   ├── GitCapturer    ← captures branch, HEAD, dirty state
│   ├── LogWriter      ← appends JSON Lines events
│   └── MCP sampling   ← delegates prompt to LLM via context.session.create_message()
└── main()             ← async entry point, runs MCP server
```

### `GitCapturer`

Stateless helper that runs `git` commands on the given `repo_path`.

```python
class GitCapturer:
    def __init__(self, repo_path: str): ...
    def branch(self) -> str: ...
    def head_sha(self) -> str: ...
    def is_dirty(self) -> bool: ...
```

Raises `GitError` (subclass of `Exception`) if git commands fail.

### `LogWriter`

Thread-safe append-only JSON Lines writer. Opens the log file once at construction and appends each event as a single JSON line.

```python
class LogWriter:
    def __init__(self, log_path: str): ...
    def append(self, event: dict) -> None: ...
```

Default log path: `{repo_path}/.git/sddtdd/review-access.jsonl`. Override via `SDDTDD_LOG_PATH` env var.

### `handle_review` (MCP tool handler)

The async function registered as the `review` MCP tool. Flow:

1. Parse inputs: `repo_path`, `review_type`, `task_id`, `prompt`
2. Generate `request_id` (UUID4 hex)
3. Capture Git state before (branch, HEAD, dirty) via `GitCapturer`
4. Record `timestamp_utc` before
5. Append `review_started` log event
6. Send prompt via `context.session.create_message()` (MCP sampling)
7. Capture Git state after (HEAD only)
8. Check stale: `head_before != head_after`
9. Compute duration
10. Append `review_completed` log event
11. Return structured response

On error at any step: set status=ERROR, verdict=null, append review_completed, return error response.

---

## Data Flow

```
Hermes Agent                    sddtdd-mcp server
    │                                │
    │  MCP call: review()            │
    │──────────────────────────────► │
    │                                │
    │                        1. Parse input
    │                        2. Generate request_id (uuid4)
    │                        3. GitCapturer: branch, HEAD, dirty
    │                        4. LogWriter: review_started
    │                        5. MCP sampling: create_message(prompt)
    │◄────────────────────────────  (LLM responds via sampling)
    │                        6. GitCapturer: HEAD after
    │                        7. Compare SHAs → stale?
    │                        8. LogWriter: review_completed
    │                        9. Return response
    │◄──────────────────────────────
```

---

## Access Log Schema

JSON Lines, one event per line, two event types:

### review_started
```json
{"event":"review_started","request_id":"...","timestamp_utc":"...",
 "repo_path":"...","branch":"...","head_sha":"...",
 "working_tree_dirty":false,"review_type":"...","task_id":"...","prompt":"..."}
```

### review_completed
```json
{"event":"review_completed","request_id":"...","timestamp_utc":"...",
 "repo_path":"...","review_type":"...","task_id":"...",
 "head_sha_before":"...","head_sha_after":"...",
 "status":"COMPLETED","verdict":"PASS","response":"...",
 "stale":false,"duration_ms":1234}
```

---

## Stale Detection

```python
if head_sha_before != head_sha_after:
    status = "STALE"
    stale = True
```

The reviewer response is still preserved in the log even when STALE.

---

## Error Handling

| Scenario | Status | Verdict |
|---|---|---|
| Normal completion | COMPLETED | PASS/FAIL/NEEDS_CLARIFICATION |
| HEAD changed during review | STALE | (preserved) |
| Sampling timeout/error | ERROR | null |
| Git command failure | ERROR | null |
| Unexpected exception | ERROR | null |

---

## Requirement Mapping

| Requirement | Component |
|---|---|
| FR-001 MCP tool registration | `server.py` — `mcp.tool()` decorator |
| FR-002 Request fields | `handle_review` args |
| FR-003 Request ID | `uuid.uuid4().hex` |
| FR-004 Git state before | `GitCapturer` |
| FR-005 MCP sampling | `context.session.create_message()` |
| FR-006 Git state after | `GitCapturer.head_sha()` |
| FR-007 Stale detection | SHA comparison |
| FR-008 Structured response | return dict |
| FR-009 review_started log | `LogWriter.append()` |
| FR-010 review_completed log | `LogWriter.append()` |
| FR-011 Log persistence | append-mode file |
| FR-012 Status values | response dict status field |
| FR-013 Error handling | try/except around all steps |
| FR-014 Log preservation | `open(log_path, 'a')` |
| NFR-001 Python 3.10+ | Python 3.10.12 available |
| NFR-002 No external deps | Only MCP SDK |
| NFR-003 Hermes-discoverable | MCP protocol stdio transport |
| NFR-004 Parallel reviews | One LogWriter instance, thread-safe append |
