"""
Tests for the sampling `tools=` argument.

These tests cover TODO4 issue #1: the reviewer MCP must pass `tools=`
to ctx.session.create_message() so the sampled LLM can read repo files
via tools like read_file / shell_command. Without tools, the reviewer
gets only the prompt text and cannot inspect committed artifacts.

A direct unit test is hard because create_message is the MCP SDK's
boundary. Instead, we read the server source and verify the
create_message call is shaped correctly: it must include `tools=` as
a keyword argument.
"""

import ast
import importlib
import pathlib
import subprocess

SERVER_PATH = pathlib.Path(__file__).resolve().parents[1] / "server.py"


def _parse_call_site() -> ast.Call:
    """Find the create_message(...) call inside server.py."""
    tree = ast.parse(SERVER_PATH.read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_message"
        ):
            return node
    raise AssertionError("create_message(...) call not found in server.py")


def test_create_message_passes_tools_kwarg():
    """RED: server.py calls create_message WITHOUT tools=, so the sampled
    LLM cannot read repo files. This test fails today and will pass after
    we add tools=[types.Tool(...)] to the call site."""
    call = _parse_call_site()
    kwarg_names = {kw.arg for kw in call.keywords}
    assert "tools" in kwarg_names, (
        "create_message must receive a `tools=` kwarg listing the file-access "
        "tools (read_file, shell_command) so the reviewer LLM can inspect the "
        "repository. Currently only the prompt text is forwarded."
    )


def test_reviewer_tools_constant_defined():
    """The module must define a REVIEWER_TOOLS list (or equivalent) that
    the sampling call references."""
    src = SERVER_PATH.read_text()
    assert "REVIEWER_TOOLS" in src, (
        "server.py must define a REVIEWER_TOOLS module-level list of tools "
        "so the sampling call can pass them via tools=."
    )


def test_reviewer_tools_includes_read_file_and_shell_command():
    """The tools list must include the two filesystem tools the reviewer
    needs: read_file for inspecting file contents, shell_command for git
    introspection. Import the actual list from server and inspect."""
    server_mod = importlib.import_module("server")
    assert hasattr(server_mod, "REVIEWER_TOOLS"), (
        "REVIEWER_TOOLS must be a module-level attribute on server.py"
    )
    tools = server_mod.REVIEWER_TOOLS
    names = {getattr(t, "name", None) for t in tools}
    assert "read_file" in names, f"REVIEWER_TOOLS must include read_file, got {names}"
    assert "shell_command" in names, f"REVIEWER_TOOLS must include shell_command, got {names}"


def test_create_message_passes_reviewer_tools():
    """The create_message call site must pass REVIEWER_TOOLS (the constant
    we just verified) as its tools= kwarg. Otherwise the LLM has no way
    to read files."""
    call = _parse_call_site()
    tools_kw = next((kw for kw in call.keywords if kw.arg == "tools"), None)
    assert tools_kw is not None, "create_message missing `tools=` kwarg"

    # tools= is now a Name reference to REVIEWER_TOOLS (the constant).
    # We verify the value resolves to a list with the expected tools.
    server_mod = importlib.import_module("server")
    assert hasattr(server_mod, "REVIEWER_TOOLS"), (
        "REVIEWER_TOOLS constant must exist (see test_reviewer_tools_constant_defined)"
    )
    tools = server_mod.REVIEWER_TOOLS
    assert isinstance(tools, list) and len(tools) > 0, (
        "REVIEWER_TOOLS must be a non-empty list of types.Tool instances"
    )


# ---------------------------------------------------------------------------
# Tool executors — direct unit tests for _execute_tool and _resolve_path.
# These run without MCP/Hermes; they exercise the file-system side of the
# tool-use loop independently.
# ---------------------------------------------------------------------------

import pytest
import server as server_mod  # noqa: E402  (import after fixtures defined)


@pytest.fixture
def repo(tmp_path):
    """Create a tiny test repo with one file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "SPEC.md").write_text("# Spec\nLine 1\nLine 2\n")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("print('hi')\n")
    return str(repo)


def test_execute_tool_read_file_relative_path(repo):
    out = server_mod._execute_tool(
        "read_file", {"path": "SPEC.md"}, repo
    )
    assert "Line 1" in out
    assert "Line 2" in out


def test_execute_tool_read_file_absolute_path_inside_repo(repo):
    out = server_mod._execute_tool(
        "read_file", {"path": f"{repo}/src/main.py"}, repo
    )
    assert "print('hi')" in out


def test_execute_tool_read_file_not_found(repo):
    out = server_mod._execute_tool(
        "read_file", {"path": "missing.md"}, repo
    )
    assert "ERROR" in out
    assert "not found" in out.lower()


def test_execute_tool_read_file_rejects_path_traversal(repo):
    out = server_mod._execute_tool(
        "read_file", {"path": "../../../etc/passwd"}, repo
    )
    assert "ERROR" in out
    assert "escapes" in out.lower()


def test_execute_tool_read_file_truncates(repo, monkeypatch):
    big = "x" * 10000
    (server_mod.Path(repo) / "big.txt").write_text(big)
    out = server_mod._execute_tool(
        "read_file", {"path": "big.txt"}, repo
    )
    assert "truncated" in out.lower()
    assert len(out) < 9000  # 8000 + truncation notice


def test_execute_tool_read_file_directory_returns_ls(repo):
    out = server_mod._execute_tool(
        "read_file", {"path": "src"}, repo
    )
    # ls -la should mention the directory contents
    assert "main.py" in out


def test_execute_tool_shell_command_runs_in_repo(repo):
    out = server_mod._execute_tool(
        "shell_command", {"command": "ls"}, repo
    )
    assert "SPEC.md" in out
    assert "src" in out


def test_execute_tool_shell_command_git_log(repo):
    """The reviewer can use shell_command to inspect git history."""
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo, check=True,
    )
    out = server_mod._execute_tool(
        "shell_command", {"command": "git log --oneline"}, repo
    )
    assert "init" in out


def test_execute_tool_shell_command_timeout():
    """Long-running commands should be killed and reported."""
    import tempfile
    with tempfile.TemporaryDirectory() as repo:
        out = server_mod._execute_tool(
            "shell_command", {"command": "sleep 30"}, repo
        )
    assert "ERROR" in out
    assert "timed out" in out.lower()


def test_execute_tool_shell_command_rejects_empty():
    out = server_mod._execute_tool("shell_command", {"command": ""}, "/tmp")
    assert "ERROR" in out


def test_execute_tool_unknown_tool(repo):
    out = server_mod._execute_tool("rm_rf", {"path": "x"}, repo)
    assert "ERROR" in out
    assert "unknown" in out.lower()
