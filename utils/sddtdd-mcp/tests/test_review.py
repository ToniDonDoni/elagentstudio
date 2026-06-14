"""
Tests for the review MCP tool — tool registration, request format, response.
"""

import json

from server import app, _get_log_path


def test_tool_registered():
    """Server registers the review tool."""
    # Verify the tool definition exists by checking the handler map
    assert hasattr(app, '_tool_handlers') or hasattr(app, 'request_handlers')
    # Check request_handlers for CallToolRequest
    from mcp.types import CallToolRequest
    assert CallToolRequest in app.request_handlers


def test_get_log_path_default_under_git():
    """Access log path defaults under .git/sddtdd/."""
    path = _get_log_path("/work/gorillas-game")
    assert ".git/sddtdd/review-access.jsonl" in path


def test_get_log_path_env_var(monkeypatch):
    """SDDTDD_LOG_PATH overrides default."""
    monkeypatch.setenv("SDDTDD_LOG_PATH", "/tmp/test-log.jsonl")
    path = _get_log_path("/any/path")
    assert path == "/tmp/test-log.jsonl"


def test_server_name():
    """Server name is set correctly."""
    assert app.name == "sddtdd-mcp"
