import asyncio
import json
import subprocess

from server import (
    BROKER_TOOLS,
    _append_broker_event,
    _candidate_evidence_paths,
    _verify_get_next_task_gate,
    app,
    build_broker_prompt,
    capture_repo_state,
    list_tools,
    parse_json_response,
)


def test_server_name():
    assert app.name == "sddtdd-broker-mcp"


def test_tool_handlers_registered():
    from mcp.types import CallToolRequest

    assert CallToolRequest in app.request_handlers


def test_broker_tool_names():
    tool_defs = asyncio.run(list_tools())
    names = {tool.name for tool in tool_defs}
    assert names == {"init", "getNextTask", "reviewTask"}
    assert names == BROKER_TOOLS


def test_get_next_task_schema_optional_previous_task_id():
    tool_defs = asyncio.run(list_tools())
    next_tool = [tool for tool in tool_defs if tool.name == "getNextTask"][0]
    # previous_task_id is optional; the implementer is allowed to omit it on the first call.
    assert "previous_task_id" not in next_tool.inputSchema["required"]
    assert "repo_path" in next_tool.inputSchema["required"]


def test_review_task_schema_requires_task_id():
    tool_defs = asyncio.run(list_tools())
    review_tool = [tool for tool in tool_defs if tool.name == "reviewTask"][0]
    assert "repo_path" in review_tool.inputSchema["required"]
    assert "task_id" in review_tool.inputSchema["required"]
    assert "claimed_result" in review_tool.inputSchema["required"]


def test_init_schema_requires_user_input():
    tool_defs = asyncio.run(list_tools())
    init_tool = [tool for tool in tool_defs if tool.name == "init"][0]
    assert init_tool.inputSchema["required"] == ["repo_path", "user_input"]


def test_parse_json_response_plain_object():
    assert parse_json_response('{"status":"complete"}') == {"status": "complete"}


def test_parse_json_response_invalid_returns_error():
    result = parse_json_response("not json")
    assert result["status"] == "ERROR"
    assert "raw_response" in result


def test_build_broker_prompt_contains_skills_and_repo_state():
    prompt = build_broker_prompt(
        "getNextTask",
        {"repo_path": "/tmp/repo"},
        {"repo_path": "/tmp/repo", "head_sha": "abc", "files": {"JOURNAL_SDD_TDD_SKILL.log": ""}},
    )
    assert "spec-driven-tdd" in prompt
    assert "SKILL-ORCHESTRATOR" in prompt
    assert "getNextTask" in prompt
    assert "JOURNAL_SDD_TDD_SKILL.log" in prompt


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


def test_get_next_task_gate_no_previous_task_is_allowed(tmp_path):
    # No previous task: first call to getNextTask is allowed (the gate only fires
    # when a previous_task_id is given and not yet verified).
    assert _verify_get_next_task_gate(str(tmp_path), None) is None


def test_get_next_task_gate_requires_verified_previous_task(tmp_path):
    (tmp_path / ".git" / "sddtdd").mkdir(parents=True)

    blocked = _verify_get_next_task_gate(str(tmp_path), "B-000001")
    assert blocked is not None
    assert blocked["status"] == "blocked"

    _append_broker_event(str(tmp_path), {
        "event": "task_verified",
        "task_id": "B-000001",
        "status": "PASS",
    })
    assert _verify_get_next_task_gate(str(tmp_path), "B-000001") is None


def test_broker_log_event_roundtrip(tmp_path):
    (tmp_path / ".git" / "sddtdd").mkdir(parents=True)
    _append_broker_event(str(tmp_path), {
        "event": "task_verified",
        "task_id": "B-000002",
        "status": "PASS",
    })
    log_path = tmp_path / ".git" / "sddtdd" / "broker-access.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["task_id"] == "B-000002"
