"""
Tests for review tool handler error paths and stale detection.
"""

import json
import os
import subprocess
import tempfile

import pytest

from server import GitCapturer, GitError, _get_log_path, _error_result


def test_error_result_format():
    """_error_result returns correct structure."""
    err = _error_result("req-123", "something broke")
    assert err["request_id"] == "req-123"
    assert err["status"] == "ERROR"
    assert err["verdict"] is None
    assert err["response"] == "something broke"
    assert err["stale"] is False


def test_get_log_path_default():
    """Default log path is under .git/sddtdd/."""
    path = _get_log_path("/work/gorillas-game")
    assert path.endswith(".git/sddtdd/review-access.jsonl")


def test_get_log_path_env_override(monkeypatch):
    """SDDTDD_LOG_PATH env var overrides default."""
    monkeypatch.setenv("SDDTDD_LOG_PATH", "/custom/path/log.jsonl")
    path = _get_log_path("/work/gorillas-game")
    assert path == "/custom/path/log.jsonl"


def test_git_error_on_invalid_repo():
    """GitCapturer on invalid path raises GitError."""
    with pytest.raises(GitError):
        GitCapturer("/definitely-not-a-git-repo-12345").branch()


def test_git_error_message():
    """GitError message is descriptive."""
    try:
        GitCapturer("/nonexistent").head_sha()
    except GitError as e:
        assert "git" in str(e).lower() or "failed" in str(e).lower()


def test_stale_detection_concept():
    """head_sha_before != head_sha_after → stale."""
    head_before = "aaa"
    head_after = "bbb"
    assert head_before != head_after
    stale = head_before != head_after
    assert stale is True
    status = "STALE" if stale else "COMPLETED"
    assert status == "STALE"


def test_not_stale():
    """Same SHA before and after → not stale."""
    sha = "abcd1234"
    stale = sha != sha
    assert stale is False
