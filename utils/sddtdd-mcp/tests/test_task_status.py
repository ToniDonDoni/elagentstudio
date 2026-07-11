import asyncio
import json
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
