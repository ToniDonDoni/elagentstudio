"""E2E: sddtdd-mcp over stdio MCP protocol.

Sends real JSON-RPC messages matching the SPEC format,
verifies responses and access log behavior.
The test client also handles sampling/createMessage requests
from the server by providing a mock PASS response.
"""
import json
import os
import subprocess
import time
import uuid

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)


class MCPClient:
    """Bidirectional MCP client over stdio.
    Handles incoming server requests (e.g. sampling/createMessage)."""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._proc: subprocess.Popen | None = None
        self._buf = ""
        self._before_sampling_response = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, timeout: float = 10):
        env = {k: v for k, v in os.environ.items()}
        env["SDDTDD_LOG_PATH"] = self.log_path

        self._proc = subprocess.Popen(
            ["uv", "run", "server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT,
            text=True, bufsize=1,
            env=env,
        )

        result = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"sampling": {}},
            "clientInfo": {"name": "e2e-test", "version": "1.0"},
        })
        assert "result" in result, (
            f"Initialize failed: {result.get('error', result)}"
        )
        self._notify("notifications/initialized")

    def stop(self):
        if self._proc:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            self._proc = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    # ------------------------------------------------------------------
    # RPC helpers
    # ------------------------------------------------------------------

    def send(self, method: str, params: dict | None = None) -> dict:
        return self._rpc(method, params)

    def _rpc(self, method: str, params: dict | None) -> dict:
        """Send a request, handle any server-side requests (sampling),
        return the response to our original request."""
        msg_id = uuid.uuid4().hex[:12]
        request = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            request["params"] = params
        self._write(json.dumps(request, ensure_ascii=False))

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            msg = self._read()
            if msg is None:
                time.sleep(0.05)
                continue

            # Check if this is a server request we need to handle
            if "method" in msg and "id" in msg:
                # Server sent us a request — handle it
                self._handle_server_request(msg)
                continue

            # This is a response to our request
            if msg.get("id") == msg_id:
                return msg

        raise TimeoutError(f"No response for {method} (id={msg_id})")

    def _notify(self, method: str):
        self._write(json.dumps(
            {"jsonrpc": "2.0", "method": method}, ensure_ascii=False,
        ))

    def _handle_server_request(self, msg: dict):
        """Respond to server-side requests like sampling/createMessage."""
        method = msg.get("method", "")
        req_id = msg.get("id")

        if method == "sampling/createMessage":
            # Allow test to inject side effects before responding
            if self._before_sampling_response:
                self._before_sampling_response()

            # Read the prompt from the sampling request
            prompt = ""
            params = msg.get("params", {})
            messages = params.get("messages", [])
            for m in messages:
                c = m.get("content", {})
                if isinstance(c, dict):
                    prompt += c.get("text", "")
                elif hasattr(c, "text"):
                    prompt += c.text

            # Determine mock verdict from prompt content
            prompt_upper = prompt.strip().upper()
            if prompt_upper.startswith("FAIL"):
                mock_text = "FAIL: The implementation does not meet the requirements."
            elif prompt_upper.startswith("NEEDS_CLARIFICATION"):
                mock_text = "NEEDS_CLARIFICATION: The review scope is unclear."
            else:
                mock_text = "PASS: Everything looks good in this automated e2e test."

            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "role": "assistant",
                    "content": {"type": "text", "text": mock_text},
                    "model": "test-model",
                    "stopReason": "endTurn",
                },
            }
            self._write(json.dumps(response, ensure_ascii=False))
        else:
            # Unknown method — return error
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not supported: {method}"},
            }
            self._write(json.dumps(response, ensure_ascii=False))

    # ------------------------------------------------------------------
    # Raw I/O
    # ------------------------------------------------------------------

    def _write(self, line: str):
        assert self._proc and self._proc.stdin, "Server not running"
        self._proc.stdin.write(line + "\n")
        self._proc.stdin.flush()

    def _read(self) -> dict | None:
        """Read one JSON line from stdout, or None if no data yet."""
        assert self._proc and self._proc.stdout

        if self._proc.poll() is not None:
            stderr = self._proc.stderr.read() if self._proc.stderr else ""
            raise RuntimeError(
                f"Server died (exit {self._proc.returncode}). stderr:\n{stderr}"
            )

        line = self._proc.stdout.readline()
        if not line:
            return None
        return json.loads(line.strip())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def log_path(tmp_path):
    return str(tmp_path / "review-access.jsonl")


@pytest.fixture
def client(log_path):
    with MCPClient(log_path=log_path) as c:
        yield c


# ---------------------------------------------------------------------------
# SPEC Example Messages
# ---------------------------------------------------------------------------

SPEC_REQUEST = {
    "repo_path": PROJECT_ROOT,
    "review_type": "RED review",
    "task_id": "T-000003",
    "prompt": (
        "PASS: Review the committed physics tests and RED evidence. "
        "Verify that the tests fail because the behavior is missing."
    ),
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInitialize:
    """Server must accept MCP initialize and respond."""

    def test_initialize_succeeds(self, client):
        """Initialize exchange completes without error."""
        resp = client.send("tools/list")
        assert "result" in resp


class TestToolDiscovery:
    """tools/list returns the review tool per SPEC."""

    def test_review_tool_is_registered(self, client):
        """Server exposes a tool named 'review'."""
        resp = client.send("tools/list")
        tools = resp.get("result", {}).get("tools", [])
        names = [t["name"] for t in tools]
        assert "review" in names, f"review not found in {names}"
        assert len(tools) == 1, f"Expected exactly 1 tool, got {len(tools)}"

    def test_review_tool_schema_matches_spec(self, client):
        """review tool input schema has spec-required fields."""
        resp = client.send("tools/list")
        tools = resp.get("result", {}).get("tools", [])
        review = next(t for t in tools if t["name"] == "review")
        props = review.get("inputSchema", {}).get("properties", {})
        required = review.get("inputSchema", {}).get("required", [])

        # SPEC requires: repo_path, review_type, prompt, task_id (optional)
        assert "repo_path" in props
        assert "review_type" in props
        assert "prompt" in props
        assert "task_id" in props  # declared as optional

        # SPEC: repo_path, review_type, prompt are required
        assert "repo_path" in required
        assert "review_type" in required
        assert "prompt" in required
        assert "task_id" not in required  # optional per SPEC


class TestReviewToolCall:
    """Calling the review tool per SPEC request/response format."""

    def test_review_returns_spec_structure(self, client):
        """Response matches SPEC: request_id, status, verdict, response, stale."""
        resp = client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })

        content = resp.get("result", {}).get("content", [])
        assert len(content) >= 1, "Expected content in response"
        result = json.loads(content[0].get("text", "{}"))

        # SPEC required fields
        assert "request_id" in result, "Missing request_id"
        assert "status" in result, "Missing status"
        assert "verdict" in result, "Missing verdict (may be null)"
        assert "response" in result, "Missing response text"
        assert "stale" in result, "Missing stale"

        # status must be one of SPEC values
        assert result["status"] in ("COMPLETED", "STALE", "ERROR"), \
            f"Unknown status: {result['status']}"

        # verdict must be one of SPEC values (or null)
        assert result["verdict"] in ("PASS", "FAIL", "NEEDS_CLARIFICATION", None), \
            f"Unknown verdict: {result['verdict']}"

        # stale must be boolean
        assert isinstance(result["stale"], bool), \
            f"stale should be bool, got {type(result['stale'])}"

    def test_review_completed_with_pass(self, client):
        """With a PASS prompt, status=COMPLETED, verdict=PASS, stale=false."""
        resp = client.send("tools/call", {
            "name": "review",
            "arguments": {
                "repo_path": PROJECT_ROOT,
                "review_type": "e2e test",
                "prompt": "PASS: This is a valid review. Everything checks out.",
            },
        })

        content = resp.get("result", {}).get("content", [])
        result = json.loads(content[0].get("text", "{}"))

        assert result["status"] == "COMPLETED", \
            f"Expected COMPLETED, got {result['status']}"
        assert result["verdict"] == "PASS", \
            f"Expected PASS, got {result['verdict']}"
        assert result["stale"] is False, \
            f"Expected stale=false, got {result['stale']}"

    def test_review_fail_verdict(self, client):
        """With a FAIL prompt, verdict=FAIL."""
        resp = client.send("tools/call", {
            "name": "review",
            "arguments": {
                "repo_path": PROJECT_ROOT,
                "review_type": "e2e test",
                "prompt": "FAIL: Something is wrong with the implementation.",
            },
        })

        content = resp.get("result", {}).get("content", [])
        result = json.loads(content[0].get("text", "{}"))

        assert result["verdict"] == "FAIL", \
            f"Expected FAIL, got {result['verdict']}"

    def test_review_needs_clarification_verdict(self, client):
        """With a NEEDS_CLARIFICATION prompt, verdict=NEEDS_CLARIFICATION."""
        resp = client.send("tools/call", {
            "name": "review",
            "arguments": {
                "repo_path": PROJECT_ROOT,
                "review_type": "e2e test",
                "prompt": "NEEDS_CLARIFICATION: The requirements are ambiguous.",
            },
        })

        content = resp.get("result", {}).get("content", [])
        result = json.loads(content[0].get("text", "{}"))

        assert result["verdict"] == "NEEDS_CLARIFICATION", \
            f"Expected NEEDS_CLARIFICATION, got {result['verdict']}"


class TestStaleDetection:
    """FR-005: Changed HEAD during review produces STALE."""

    def test_stale_when_head_changes(self, log_path):
        """When HEAD changes during review, status=STALE and stale=true."""
        # Create a temporary repo to test stale detection
        import tempfile
        import subprocess as sp

        with tempfile.TemporaryDirectory() as tmpdir:
            # Init a git repo
            sp.run(["git", "init"], cwd=tmpdir, capture_output=True)
            sp.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            sp.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("initial")
            sp.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            sp.run(["git", "commit", "-m", "initial"], cwd=tmpdir, capture_output=True)

            with MCPClient(log_path=log_path) as c:
                # Set up: on sampling request, change HEAD
                def change_head():
                    with open(test_file, "w") as f:
                        f.write("changed")
                    sp.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
                    sp.run(["git", "commit", "-m", "stale change"], cwd=tmpdir, capture_output=True)

                c._before_sampling_response = change_head

                resp = c.send("tools/call", {
                    "name": "review",
                    "arguments": {
                        "repo_path": tmpdir,
                        "review_type": "stale test",
                        "prompt": "PASS: Test stale detection.",
                    },
                })

            content = resp.get("result", {}).get("content", [])
            result = json.loads(content[0].get("text", "{}"))

            assert result["status"] == "STALE", \
                f"Expected STALE, got {result['status']}"
            assert result["stale"] is True, \
                f"Expected stale=true, got {result['stale']}"


class TestAccessLog:
    """Access log (JSON Lines) matches SPEC format."""

    def test_log_created(self, client, log_path):
        """After review call, log file exists at expected path."""
        client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })
        assert os.path.exists(log_path), f"Log not found: {log_path}"

    def test_log_contains_started_and_completed(self, client, log_path):
        """Log has review_started and review_completed events."""
        client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })

        with open(log_path) as f:
            events = [json.loads(l) for l in f if l.strip()]

        event_types = [e["event"] for e in events]
        assert "review_started" in event_types
        assert "review_completed" in event_types

    def test_log_events_share_request_id(self, client, log_path):
        """Started and completed events share the same request_id."""
        client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })

        with open(log_path) as f:
            events = [json.loads(l) for l in f if l.strip()]

        started = [e for e in events if e["event"] == "review_started"]
        completed = [e for e in events if e["event"] == "review_completed"]
        assert len(started) == 1
        assert len(completed) == 1
        assert started[0]["request_id"] == completed[0]["request_id"]

    def test_log_has_git_metadata(self, client, log_path):
        """review_started contains branch, head_sha, working_tree_dirty."""
        client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })

        with open(log_path) as f:
            started = json.loads(f.readline())

        assert "branch" in started
        assert "head_sha" in started
        assert "working_tree_dirty" in started
        assert isinstance(started["working_tree_dirty"], bool)
        assert len(started["branch"]) > 0
        # head_sha should be 40 hex chars
        assert len(started["head_sha"]) == 40
        assert all(c in "0123456789abcdef" for c in started["head_sha"])

    def test_log_preserves_review_type_and_prompt(self, client, log_path):
        """Log preserves exact review_type, task_id, prompt."""
        client.send("tools/call", {
            "name": "review",
            "arguments": {
                "repo_path": PROJECT_ROOT,
                "review_type": "ARCHITECTURE review",
                "task_id": "T-999999",
                "prompt": "PASS: Verify log preservation.",
            },
        })

        with open(log_path) as f:
            started = json.loads(f.readline())

        assert started["review_type"] == "ARCHITECTURE review"
        assert started["task_id"] == "T-999999"
        assert "Verify log preservation" in started["prompt"]

    def test_log_review_completed_has_head_shas(self, client, log_path):
        """review_completed has head_sha_before and head_sha_after fields."""
        client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })

        with open(log_path) as f:
            events = [json.loads(l) for l in f if l.strip()]

        completed = [e for e in events if e["event"] == "review_completed"]
        assert len(completed) == 1
        assert "head_sha_before" in completed[0]
        assert "head_sha_after" in completed[0]
        # Both should be 40-char hex SHAs
        for field in ("head_sha_before", "head_sha_after"):
            sha = completed[0][field]
            assert len(sha) == 40, f"{field} has wrong length: {len(sha)}"
            assert all(c in "0123456789abcdef" for c in sha), \
                f"{field} has non-hex chars"

    def test_log_has_duration_ms(self, client, log_path):
        """review_completed contains duration_ms (int)."""
        client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })

        with open(log_path) as f:
            events = [json.loads(l) for l in f if l.strip()]

        completed = [e for e in events if e["event"] == "review_completed"]
        assert "duration_ms" in completed[0]
        assert isinstance(completed[0]["duration_ms"], int)

    def test_log_timestamp_is_iso8601(self, client, log_path):
        """Log timestamps are ISO 8601 UTC format."""
        import re
        iso_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })

        with open(log_path) as f:
            events = [json.loads(l) for l in f if l.strip()]

        for event in events:
            ts = event.get("timestamp_utc", "")
            assert re.match(iso_pattern, ts), \
                f"timestamp_utc not ISO 8601: {ts}"

    def test_log_working_tree_dirty_false(self, client, log_path):
        """In a clean working tree, working_tree_dirty is False."""
        client.send("tools/call", {
            "name": "review",
            "arguments": SPEC_REQUEST,
        })

        with open(log_path) as f:
            started = json.loads(f.readline())

        assert started["working_tree_dirty"] is False


class TestErrorHandling:
    """Error cases per SPEC."""

    def test_invalid_repo_returns_error(self, client):
        """Non-existent repo_path -> status=ERROR, verdict=null."""
        resp = client.send("tools/call", {
            "name": "review",
            "arguments": {
                "repo_path": "/nonexistent/path/to/repo",
                "review_type": "test",
                "prompt": "PASS: Should not reach reviewer.",
            },
        })

        content = resp.get("result", {}).get("content", [])
        result = json.loads(content[0].get("text", "{}"))

        assert result["status"] == "ERROR"
        assert result["verdict"] is None
        assert result["stale"] is False

    def test_missing_repo_path_returns_error(self, client):
        """Missing repo_path -> MCP protocol error (isError flag)."""
        resp = client.send("tools/call", {
            "name": "review",
            "arguments": {
                "review_type": "test",
                "prompt": "test",
            },
        })

        # The MCP SDK should return an error for missing required params
        err = resp.get("error")
        result_err = (resp.get("result") or {}).get("isError")

        assert err is not None or result_err is not None, \
            f"Expected error but got: {resp}"


class TestLogSurvivesRestart:
    """Log is append-only across server restarts (SPEC requirement)."""

    def test_log_preserved_across_restarts(self, log_path):
        """Two sessions append to the same log file."""
        for session_num in (1, 2):
            with MCPClient(log_path=log_path) as c:
                c.send("tools/call", {
                    "name": "review",
                    "arguments": {
                        "repo_path": PROJECT_ROOT,
                        "review_type": f"session-{session_num}",
                        "prompt": "PASS: Session test.",
                    },
                })

        with open(log_path) as f:
            lines = [l for l in f if l.strip()]

        # 2 sessions * 2 events each = 4 lines
        assert len(lines) == 4, f"Expected 4 log lines, got {len(lines)}"

    def test_log_old_entries_survive(self, log_path):
        """Old log entries are NOT overwritten by new sessions."""
        # Session 1
        with MCPClient(log_path=log_path) as c:
            c.send("tools/call", {
                "name": "review",
                "arguments": {
                    "repo_path": PROJECT_ROOT,
                    "review_type": "very-first-session",
                    "prompt": "PASS: First session.",
                },
            })

        # Session 2
        with MCPClient(log_path=log_path) as c:
            c.send("tools/call", {
                "name": "review",
                "arguments": {
                    "repo_path": PROJECT_ROOT,
                    "review_type": "second-session",
                    "prompt": "PASS: Second session.",
                },
            })

        # Read log: must contain BOTH review_types
        with open(log_path) as f:
            events = [json.loads(l) for l in f if l.strip()]

        started = [e for e in events if e["event"] == "review_started"]
        assert len(started) == 2, \
            f"Expected 2 review_started entries, got {len(started)}"

        types_found = [e["review_type"] for e in started]
        assert "very-first-session" in types_found, \
            f"First session entry missing: {types_found}"
        assert "second-session" in types_found, \
            f"Second session entry missing: {types_found}"
        # First entry must be from session 1 (order preserved)
        assert started[0]["review_type"] == "very-first-session", \
            "Old entries were overwritten — first entry should be from session 1"
