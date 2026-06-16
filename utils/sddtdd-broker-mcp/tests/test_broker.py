import json
from pathlib import Path

from server import app, build_broker_prompt, parse_json_response


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
