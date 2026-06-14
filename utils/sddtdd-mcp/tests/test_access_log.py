"""
Tests for GitCapturer and LogWriter — core infrastructure of sddtdd-mcp.
"""

import json
import os
import subprocess
import tempfile

import pytest

from server import GitCapturer, GitError, LogWriter


# ---------------------------------------------------------------------------
# GitCapturer
# ---------------------------------------------------------------------------

def test_git_capturer_branch():
    """Capturer reads branch name from a real git repo."""
    cap = GitCapturer(os.path.dirname(os.path.abspath(__file__)))
    branch = cap.branch()
    assert isinstance(branch, str)
    assert len(branch) > 0


def test_git_capturer_head_sha():
    """head_sha returns a full SHA."""
    cap = GitCapturer(os.path.dirname(os.path.abspath(__file__)))
    sha = cap.head_sha()
    assert isinstance(sha, str)
    assert len(sha) == 40
    # hex chars only
    int(sha, 16)


def test_git_capturer_is_dirty():
    """is_dirty returns bool."""
    cap = GitCapturer(os.path.dirname(os.path.abspath(__file__)))
    dirty = cap.is_dirty()
    assert isinstance(dirty, bool)


def test_git_capturer_invalid_path():
    """Invalid repo path raises GitError."""
    with pytest.raises(GitError):
        GitCapturer("/nonexistent/path").branch()


def test_git_capturer_head_sha_is_commit():
    """head_sha exists as a git commit (rev-parse --verify)."""
    cap = GitCapturer(os.path.dirname(os.path.abspath(__file__)))
    sha = cap.head_sha()
    result = subprocess.run(
        ["git", "cat-file", "-t", sha],
        capture_output=True, text=True, timeout=5,
    )
    assert result.stdout.strip() == "commit"


# ---------------------------------------------------------------------------
# LogWriter
# ---------------------------------------------------------------------------

def test_log_writer_creates_file():
    """LogWriter creates parent directory and file."""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "sub", "test.jsonl")
        writer = LogWriter(log_path)
        writer.append({"event": "test"})
        writer.close()
        assert os.path.isfile(log_path)


def test_log_writer_appends_json_lines():
    """Multiple appends produce valid JSON Lines."""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "log.jsonl")
        writer = LogWriter(log_path)
        writer.append({"event": "a", "n": 1})
        writer.append({"event": "b", "n": 2})
        writer.close()
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"event": "a", "n": 1}
        assert json.loads(lines[1]) == {"event": "b", "n": 2}


def test_log_writer_preserves_across_instances():
    """Reopening the same file appends, not overwrites."""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "log.jsonl")
        w1 = LogWriter(log_path)
        w1.append({"event": "first"})
        w1.close()

        w2 = LogWriter(log_path)
        w2.append({"event": "second"})
        w2.close()

        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 2


def test_log_writer_special_chars():
    """Non-ASCII and special chars in event dict are handled."""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "log.jsonl")
        writer = LogWriter(log_path)
        writer.append({"event": "тест", "path": "/work/gorillas-game"})
        writer.close()
        with open(log_path) as f:
            obj = json.loads(f.readline())
        assert obj["event"] == "тест"
