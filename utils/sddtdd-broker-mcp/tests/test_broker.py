import asyncio
import json
import subprocess

from server import (
    BROKER_TOOLS,
    _append_broker_event,
    _broker_log_path,
    _candidate_evidence_paths,
    _normalize_evidence,
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


def test_schemas_do_not_require_skill_pointer_fields():
    """Implementer no longer hands the broker role files on every call. The
    broker is configured with the process skill and the orchestrator role at
    startup."""
    tool_defs = asyncio.run(list_tools())
    for tool in tool_defs:
        required = tool.inputSchema["required"]
        for field in ("process_skill", "implementer_skill", "broker_skill", "instruction"):
            assert field not in required, (
                f"{tool.name} schema still requires {field}; "
                "the broker is configured with the role files at startup, not per call"
            )


def test_get_next_task_schema_optional_previous_task_id():
    tool_defs = asyncio.run(list_tools())
    next_tool = [tool for tool in tool_defs if tool.name == "getNextTask"][0]
    assert "previous_task_id" not in next_tool.inputSchema["required"]
    assert "repo_path" in next_tool.inputSchema["required"]


def test_review_task_schema_requires_task_id_and_accepts_structured_evidence():
    tool_defs = asyncio.run(list_tools())
    review_tool = [tool for tool in tool_defs if tool.name == "reviewTask"][0]
    assert set(review_tool.inputSchema["required"]) == {"repo_path", "task_id", "claimed_result"}
    evidence_schema = review_tool.inputSchema["properties"]["evidence"]
    assert evidence_schema["type"] == "object"
    assert "commits" in evidence_schema["properties"]
    assert "journal_ids" in evidence_schema["properties"]
    assert "review_request_id" in evidence_schema["properties"]
    assert "test_commands" in evidence_schema["properties"]
    assert "files" in evidence_schema["properties"]


def test_init_schema_requires_user_input():
    tool_defs = asyncio.run(list_tools())
    init_tool = [tool for tool in tool_defs if tool.name == "init"][0]
    required = set(init_tool.inputSchema["required"])
    assert "repo_path" in required
    assert "user_input" in required


def test_parse_json_response_plain_object():
    assert parse_json_response('{"status":"complete"}') == {"status": "complete"}


def test_parse_json_response_invalid_returns_error():
    result = parse_json_response("not json")
    assert result["status"] == "ERROR"
    assert "raw_response" in result


def test_build_broker_prompt_includes_process_orchestrator_and_stages():
    prompt = build_broker_prompt(
        "getNextTask",
        {"repo_path": "/tmp/repo"},
        {"repo_path": "/tmp/repo", "head_sha": "abc", "files": {"JOURNAL_SDD_TDD_SKILL.log": ""}},
    )
    assert "spec-driven-tdd" in prompt
    assert "SKILL-ORCHESTRATOR" in prompt
    assert "STAGES" in prompt
    assert "getNextTask" in prompt
    assert "JOURNAL_SDD_TDD_SKILL.log" in prompt
    # The broker is told its role in the prompt itself; the broker does not
    # need the implementer to remind it on every call.
    assert "task broker/orchestrator" in prompt
    # The broker is told that semantic verification is its job.
    assert "broker-level task verification" in prompt
    # The broker is told to return self-contained tasks with the new fields.
    assert "allowed_scope" in prompt
    assert "required_evidence" in prompt


def test_normalize_evidence_accepts_structured_object():
    """explicit collects path-like tokens (files, commit hashes) for the
    journal/evidence path helper. journal_ids are identifiers, not paths,
    so they live in the structured object but not in ``explicit``."""
    explicit, obj = _normalize_evidence({
        "evidence": {
            "commits": ["abc123"],
            "journal_ids": ["J-20260616-001"],
            "files": ["src/foo.py"],
            "test_commands": ["pytest -q"],
        }
    })
    assert "abc123" in explicit
    assert "src/foo.py" in explicit
    assert "J-20260616-001" not in explicit
    assert obj["commits"] == ["abc123"]
    assert obj["journal_ids"] == ["J-20260616-001"]
    assert obj["test_commands"] == ["pytest -q"]


def test_normalize_evidence_accepts_legacy_list():
    explicit, obj = _normalize_evidence({"evidence": ["evidence/red.txt", "commit abc"]})
    assert "evidence/red.txt" in explicit
    assert "commit abc" in explicit
    assert obj == {}


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


def test_broker_log_path_is_under_dot_git_sddtdd(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    path = _broker_log_path(str(tmp_path))
    assert path == tmp_path / ".git" / "sddtdd" / "broker-access.jsonl"


def test_broker_log_event_roundtrip(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    _append_broker_event(str(tmp_path), {
        "event": "task_review_started",
        "task_id": "B-000001",
        "head_sha_before": "abc",
    })
    _append_broker_event(str(tmp_path), {
        "event": "task_review_completed",
        "task_id": "B-000001",
        "head_sha_before": "abc",
        "head_sha_after": "def",
        "status": "FAIL",
        "findings": ["missing evidence"],
        "duration_ms": 42,
    })
    log_path = tmp_path / ".git" / "sddtdd" / "broker-access.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    started = json.loads(lines[0])
    completed = json.loads(lines[1])
    assert started["event"] == "task_review_started"
    assert started["task_id"] == "B-000001"
    assert completed["event"] == "task_review_completed"
    assert completed["status"] == "FAIL"
    assert completed["findings"] == ["missing evidence"]


def test_broker_log_writes_both_started_and_completed_for_every_verdict(tmp_path):
    """The broker must write task_review_started and task_review_completed
    for every reviewTask call, not just on PASS. This is what makes
    investigations possible."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    for verdict in ("PASS", "FAIL", "NEEDS_CLARIFICATION", "ERROR"):
        _append_broker_event(str(tmp_path), {
            "event": "task_review_started",
            "task_id": f"B-{verdict}",
            "head_sha_before": "abc",
        })
        _append_broker_event(str(tmp_path), {
            "event": "task_review_completed",
            "task_id": f"B-{verdict}",
            "head_sha_before": "abc",
            "head_sha_after": "abc",
            "status": verdict,
            "duration_ms": 1,
        })
    log_path = tmp_path / ".git" / "sddtdd" / "broker-access.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 8
    statuses = [json.loads(line)["status"] for line in lines if json.loads(line)["event"] == "task_review_completed"]
    assert statuses == ["PASS", "FAIL", "NEEDS_CLARIFICATION", "ERROR"]
