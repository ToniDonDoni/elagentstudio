# sddtdd-mcp — Task Decomposition

**Reference:** `SPEC.md` (S-SDDTDD-MCP-01), `ARCHITECTURE.md`  
**Version:** 1.0

---

## Task Tree

```
T-000001  User Input (root)
├── T-000002  Project scaffolding (pyproject.toml, README.md)
├── T-000003  GitCapturer class (git state capture)
├── T-000004  LogWriter class (JSON Lines access log)
├── T-000005  server.py — MCP server + review tool handler
└── T-000006  Test suite (test_review, test_access_log, test_stale_review)
```

---

## T-000002 — Project Scaffolding

| Field | Value |
|---|---|
| **REQUIREMENT_IDS** | C-001, C-003, NFR-001, NFR-003 |
| **DEPENDENCIES** | — |

### Acceptance
- `pyproject.toml` with `mcp` dependency, `[project.scripts]` entry, pytest config
- `README.md` with install/run instructions
- `.gitignore` for Python artifacts
- `uv sync` succeeds
- `uv run python -c "import mcp"` succeeds

---

## T-000003 — GitCapturer Class

| Field | Value |
|---|---|
| **REQUIREMENT_IDS** | FR-004, FR-006 |
| **ARCHITECTURE_REFERENCES** | GitCapturer in ARCHITECTURE.md |
| **DEPENDENCIES** | T-000002 |

### Acceptance
- `GitCapturer(repo_path)` reads repo metadata via `git` CLI
- `.branch()` returns current branch name
- `.head_sha()` returns full HEAD SHA
- `.is_dirty()` returns True/False for working tree state
- Raises `GitError` on invalid repo path
- Tested via Pytest with real git repos

---

## T-000004 — LogWriter Class

| Field | Value |
|---|---|
| **REQUIREMENT_IDS** | FR-009, FR-010, FR-011, FR-014, NFR-004 |
| **ARCHITECTURE_REFERENCES** | LogWriter in ARCHITECTURE.md |
| **DEPENDENCIES** | T-000002 |

### Acceptance
- `LogWriter(log_path)` opens file in append mode
- `.append(event)` writes one JSON line + newline
- Multiple appends produce valid JSON Lines
- Works from temp directory test
- Thread-safe for concurrent appends

---

## T-000005 — MCP Server + review Tool Handler

| Field | Value |
|---|---|
| **REQUIREMENT_IDS** | FR-001, FR-002, FR-003, FR-005, FR-007, FR-008, FR-012, FR-013, NFR-002 |
| **ARCHITECTURE_REFERENCES** | handle_review flow in ARCHITECTURE.md |
| **DEPENDENCIES** | T-000002, T-000003, T-000004 |

### Acceptance
- `uv run python server.py` starts MCP server on stdio
- Server registers exactly one `review` tool
- MCP tool discovery lists `review` with 4 parameters
- Tool handler follows the 11-step flow
- Stale detection works (HEAD change)
- Error handling returns ERROR status
- Sampling via `context.session.create_message()` works
- Returns structured response

---

## T-000006 — Test Suite

| Field | Value |
|---|---|
| **REQUIREMENT_IDS** | C-004, all ACs |
| **DEPENDENCIES** | T-000002, T-000003, T-000004, T-000005 |

### Acceptance
- `tests/test_review.py` — unit tests for request flow
- `tests/test_access_log.py` — log format, persistence, concurrent writes
- `tests/test_stale_review.py` — stale detection, HEAD change
- `uv run pytest` passes all tests
