import json
import subprocess

from server import (
    _append_broker_event,
    _candidate_evidence_paths,
    _verify_next_task_gate,
    app,
    build_broker_prompt,
    capture_repo_state,
    parse_json_response,
)


def test_server_name():
    assert app.name == "sddtdd-broker-mcp"


def test_tool_handlers_registered():
    from mcp.types import CallToolRequest

    assert CallToolRequest in app.request_handlers


def test_parse_json_response_plain_object():
    assert parse_json_response('{"status":"DONE"}') == {"status": "DONE"}


def test_parse_json_response_invalid_returns_error():
    result = parse_json_response('not json')
    assert result["status"] == "ERROR"
    assert "raw_response" in result


def test_build_broker_prompt_contains_skills_and_repo_state():
    prompt = build_broker_prompt(
        "next_task",
        {"repo_path": "/tmp/repo"},
        {"repo_path": "/tmp/repo", "head_sha": "abc", "files": {"JOURNAL_SDD_TDD_SKILL.log": ""}},
    )
    assert "spec-driven-tdd" in prompt
    assert "sddtdd-task-broker" in prompt
    assert "next_task" in prompt
    assert "JOURNAL_SDD_TDD_SKILL.log" in prompt


def test_next_task_schema_requires_previous_task_id():
    import asyncio

    from server import list_tools

    tool_defs = asyncio.run(list_tools())
    next_tool = [tool for tool in tool_defs if tool.name == "next_task"][0]
    assert "previous_task_id" in next_tool.inputSchema["required"]


def test_candidate_evidence_paths_from_journal_and_explicit():
    journal = "DETAIL: RED evidence at evidence/red.txt and `logs/green.json`. Ignore /tmp/x and ../secret"
    paths = _candidate_evidence_paths(journal, ["artifacts/manual.md"])
    assert "evidence/red.txt" in paths
    assert "logs/green.json" in paths
    assert "artifacts/manual.md" in paths
    assert "../secret" not in paths


def test_capture_repo_state_loads_evidence_files(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text("DETAIL: Evidence `evidence/red.txt`\n")
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "red.txt").write_text("RED failed for missing behavior")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    state = capture_repo_state(str(tmp_path), ["evidence/red.txt"])
    assert state["files"]["JOURNAL_SDD_TDD_SKILL.log"].startswith("DETAIL")
    assert state["evidence_files"]["evidence/red.txt"] == "RED failed for missing behavior"


def test_capture_repo_state_reads_committed_head_not_dirty_worktree(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text("DETAIL: committed journal\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text("DETAIL: dirty uncommitted journal\n")

    state = capture_repo_state(str(tmp_path))
    assert state["status_porcelain"]
    assert state["files"]["JOURNAL_SDD_TDD_SKILL.log"] == "DETAIL: committed journal\n"


def test_next_task_gate_requires_verified_task(tmp_path):
    git_dir = tmp_path / ".git" / "sddtdd"
    git_dir.mkdir(parents=True)

    blocked = _verify_next_task_gate(str(tmp_path), "B-000001")
    assert blocked is not None
    assert blocked["status"] == "BLOCKED"

    _append_broker_event(str(tmp_path), {"event": "task_verified", "task_id": "B-000001", "status": "PASS"})
    assert _verify_next_task_gate(str(tmp_path), "B-000001") is None
