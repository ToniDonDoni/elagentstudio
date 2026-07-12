import asyncio
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import server


def _tool_text(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def test_tools_list_exposes_task_status():
    tools = asyncio.run(server.list_tools())

    assert "taskStatus" in {tool.name for tool in tools}


def test_task_status_update_persists_state_and_get_reads_it(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    updated = _tool_text(
        asyncio.run(server.call_tool(
            "taskStatus",
            {
                "repo_path": str(repo),
                "operation": "update",
                "task_id": "T-001",
                "task_kind": "IMPLEMENTATION",
                "status": "RUNNING",
                "role": "implementer",
                "execution_id": "task-123",
                "worktree_path": str(repo / ".worktrees" / "T-001"),
            },
        ))
    )

    state_path = repo / ".sddtdd_skill" / "task-status.json"
    assert state_path.exists()
    assert updated["status"] == "COMPLETED"
    assert updated["task"]["status"] == "RUNNING"

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["tasks"]["T-001"]["execution_id"] == "task-123"

    fetched = _tool_text(
        asyncio.run(server.call_tool(
            "taskStatus",
            {
                "repo_path": str(repo),
                "operation": "get",
                "task_id": "T-001",
            },
        ))
    )
    assert fetched["status"] == "COMPLETED"
    assert fetched["task"]["status"] == "RUNNING"
    assert fetched["task"]["task_kind"] == "IMPLEMENTATION"


def test_task_status_requests_are_recorded_in_orchestrator_access_log(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    asyncio.run(
        server.call_tool(
            "taskStatus",
            {
                "repo_path": str(repo),
                "operation": "update",
                "task_id": "T-LOG",
                "task_kind": "IMPLEMENTATION",
                "status": "RUNNING",
                "role": "implementer",
                "execution_id": "log-task-1",
            },
        )
    )
    asyncio.run(
        server.call_tool(
            "taskStatus",
            {"repo_path": str(repo), "operation": "get", "task_id": "T-LOG"},
        )
    )

    log_path = repo / ".sddtdd_skill" / "orchestrator-access.jsonl"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == [
        "taskStatus_started",
        "taskStatus_completed",
        "taskStatus_started",
        "taskStatus_completed",
    ]
    assert [event["operation"] for event in events if event["event"].endswith("_started")] == [
        "update",
        "get",
    ]
    assert events[1]["task_id"] == "T-LOG"
    assert events[1]["task_status"] == "RUNNING"


def test_task_status_update_preserves_history_and_rejects_unknown_status(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    base = {
        "repo_path": str(repo),
        "operation": "update",
        "task_id": "T-002",
        "task_kind": "IMPLEMENTATION",
        "role": "reviewer",
        "execution_id": "task-456",
    }
    asyncio.run(server.call_tool("taskStatus", {**base, "status": "RUNNING"}))
    asyncio.run(server.call_tool("taskStatus", {**base, "status": "COMPLETED", "result": "PASS"}))

    fetched = _tool_text(
        asyncio.run(server.call_tool(
            "taskStatus",
            {"repo_path": str(repo), "operation": "get", "task_id": "T-002"},
        ))
    )
    assert fetched["task"]["status"] == "COMPLETED"
    assert fetched["task"]["result"] == "PASS"
    assert [entry["status"] for entry in fetched["task"]["history"]] == [
        "RUNNING",
        "COMPLETED",
    ]

    invalid = _tool_text(
        asyncio.run(server.call_tool(
            "taskStatus",
            {**base, "status": "NOT_A_STATUS"},
        ))
    )
    assert invalid["status"] == "ERROR"
    assert "status" in invalid["response"]


def test_task_status_update_requires_an_implementer_or_reviewer(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    result = _tool_text(
        asyncio.run(
            server.call_tool(
                "taskStatus",
                {
                    "repo_path": str(repo),
                    "operation": "update",
                    "task_id": "T-004",
                    "status": "RUNNING",
                    "role": "orchestrator",
                },
            )
        )
    )

    assert result["status"] == "ERROR"
    assert "role" in result["response"]


def test_task_status_expires_stale_running_task_and_marks_it_retryable(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("SDDTDD_TASK_TIMEOUT_SECONDS", "1")

    asyncio.run(
        server.call_tool(
            "taskStatus",
            {
                "repo_path": str(repo),
                "operation": "update",
                "task_id": "T-005",
                "task_kind": "IMPLEMENTATION",
                "status": "RUNNING",
                "role": "implementer",
                "execution_id": "task-timeout",
            },
        )
    )
    state_path = repo / ".sddtdd_skill" / "task-status.json"
    document = json.loads(state_path.read_text(encoding="utf-8"))
    stale_at = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    document["updated_at"] = stale_at
    document["tasks"]["T-005"]["updated_at"] = stale_at
    state_path.write_text(json.dumps(document), encoding="utf-8")

    fetched = _tool_text(
        asyncio.run(
            server.call_tool(
                "taskStatus",
                {"repo_path": str(repo), "operation": "get", "task_id": "T-005"},
            )
        )
    )
    assert fetched["task"]["status"] == "FAILED"
    assert fetched["task"]["retryable"] is True
    assert fetched["task"]["error"] == "TASK_TIMEOUT"

    server._record_issued_task(
        str(repo),
        {"status": "task", "next_task": {"task_id": "T-005", "task_kind": "IMPLEMENTATION"}},
    )
    retried = json.loads(state_path.read_text(encoding="utf-8"))["tasks"]["T-005"]
    assert retried["status"] == "PENDING"
    assert retried["retryable"] is False
    assert retried["attempt"] == 2


def test_get_next_task_returns_not_ready_when_registrar_has_no_available_task(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

    asyncio.run(
        server.call_tool(
            "taskStatus",
            {
                "repo_path": str(repo),
                "operation": "update",
                "task_id": "T-000001",
                "task_kind": "IMPLEMENTATION",
                "status": "RUNNING",
                "role": "implementer",
                "execution_id": "task-running",
            },
        )
    )
    monkeypatch.setattr(server, "_orchestrator_policy_bundle_text", lambda: "policy")
    result = _tool_text(
        asyncio.run(
            server._call_orchestrator_tool(
                "getNextTask",
                {
                    "repo_path": str(repo),
                    "task_kind": "INITIAL_USER_INPUT",
                    "task_id": None,
                    "claimed_result": None,
                    "work_journal_id": None,
                    "evidence": {"user_input": "test"},
                },
            )
        )
    )

    assert result["orchestrator_result"]["status"] == "notReady"
    assert result["orchestrator_result"]["next_task"] is None


def test_get_next_task_records_issued_task_as_pending(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

    server._record_issued_task(
        str(repo),
        {
            "status": "task",
            "next_task": {"task_id": "O-000001", "task_kind": "IMPLEMENTATION"},
        },
    )
    state = json.loads((repo / ".sddtdd_skill" / "task-status.json").read_text(encoding="utf-8"))
    assert state["tasks"]["O-000001"]["status"] == "PENDING"
    assert state["tasks"]["O-000001"]["role"] == "implementer"


def test_next_task_prompt_includes_persisted_task_status(tmp_path: Path):
    repo = tmp_path / "repo"
    status_dir = repo / ".sddtdd_skill"
    status_dir.mkdir(parents=True)
    (status_dir / "task-status.json").write_text(
        json.dumps({"version": 1, "updated_at": "now", "tasks": {"T-003": {"status": "RUNNING"}}}),
        encoding="utf-8",
    )
    git = SimpleNamespace(branch=lambda: "agent/test", head_sha=lambda: "abc123", is_dirty=lambda: False)

    prompt = server._get_next_prompt(
        str(repo),
        git,
        {
            "task_kind": "INITIAL_USER_INPUT",
            "task_id": None,
            "claimed_result": None,
            "work_journal_id": None,
            "evidence": {"user_input": "test"},
        },
    )

    assert "task-status.json" in prompt
    assert "T-003" in prompt
    assert "RUNNING" in prompt
