"""sddtdd-mcp — Minimal MCP review proxy for Hermes Agent.

Single tool: review. Captures Git state, delegates to LLM via MCP sampling,
records everything in an append-only JSON Lines access log.
"""
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import mcp.server as mcp_server
import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class GitError(Exception):
    """Raised when a git command fails."""


# ---------------------------------------------------------------------------
# GitCapturer — read repo metadata via git CLI
# ---------------------------------------------------------------------------

class GitCapturer:
    """Capture repository branch, HEAD SHA, and dirty state."""

    def __init__(self, repo_path: str):
        self._repo = repo_path

    def _git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", self._repo, *args],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                raise GitError(
                    f"git {' '.join(args)} failed: {result.stderr.strip()}"
                )
            return result.stdout.strip()
        except FileNotFoundError as exc:
            raise GitError("git not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {' '.join(args)} timed out") from exc

    def branch(self) -> str:
        return self._git("rev-parse", "--abbrev-ref", "HEAD")

    def head_sha(self) -> str:
        return self._git("rev-parse", "HEAD")

    def is_dirty(self) -> bool:
        output = self._git("status", "--porcelain")
        return bool(output.strip())


# ---------------------------------------------------------------------------
# LogWriter — thread-safe append-only JSON Lines writer
# ---------------------------------------------------------------------------

class LogWriter:
    """Append-only JSON Lines access log."""

    def __init__(self, log_path: str):
        self._path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._file = open(log_path, "a", buffering=1)

    def append(self, event: dict) -> None:
        """Append one JSON line. Thread-safe via GIL + line-buffer."""
        line = json.dumps(event, ensure_ascii=False, default=str)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _get_log_path(repo_path: str) -> str:
    """Return log path: env var override or default under <repo>/.sddtdd_skill/.

    The reviewer access log is a runtime artifact, not a committed
    artifact. It is expected to be ignored by .gitignore via the
    `.sddtdd_skill/*.jsonl` pattern shipped with the spec-driven-tdd
    skill. Override with the ``SDDTDD_LOG_PATH`` env var.
    """
    env = os.environ.get("SDDTDD_LOG_PATH")
    if env:
        return env
    return os.path.join(repo_path, ".sddtdd_skill", "review-access.jsonl")


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

app = mcp_server.Server("sddtdd-mcp")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="review",
            description="Review committed repository state through an independent LLM reviewer",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Absolute path to the Git repository",
                    },
                    "review_type": {
                        "type": "string",
                        "description": "Free-form review label (e.g. 'RED review', 'architecture review')",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Optional free-form task identifier",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Complete review instruction for the LLM reviewer",
                    },
                },
                "required": ["repo_path", "review_type", "prompt"],
            },
        )
    ]


# ---------------------------------------------------------------------------
# Sampling tools — filesystem access for the reviewer LLM
# ---------------------------------------------------------------------------
# TODO4 issue #1: the reviewer LLM could only see the prompt text and had
# no way to read committed files. These tools give the sampled LLM access
# to read_file and shell_command. Hermes (mcp_tool.py:855-871) already
# forwards tools to the LLM call and returns CreateMessageResultWithTools
# when the LLM emits tool_calls. The loop in _sample_with_tools drives the
# tool-use round trip.

REVIEWER_TOOLS: list[types.Tool] = [
    types.Tool(
        name="read_file",
        description=(
            "Read a text file from the repository under review. "
            "Use absolute or repo-relative paths. Returns the file contents "
            "(truncated to 8000 chars if large)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to the file, absolute or relative to the "
                        "repository root."
                    ),
                },
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="shell_command",
        description=(
            "Run a shell command inside the repository. Use for `git log`, "
            "`git show`, `git diff`, `ls`, `cat`, etc. The working directory "
            "is the repository root. Output is truncated to 8000 chars."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run.",
                },
            },
            "required": ["command"],
        },
    ),
]


def _resolve_path(repo_path: str, raw: str) -> Path:
    """Resolve a user-supplied path to an absolute path inside repo_path.

    Rejects absolute paths outside repo_path and parent traversals.
    """
    repo = Path(repo_path).resolve()
    p = Path(raw)
    if not p.is_absolute():
        p = repo / p
    p = p.resolve()
    # Containment check: must be inside repo
    if repo not in p.parents and p != repo:
        raise ValueError(f"path escapes repository: {raw}")
    return p


def _execute_tool(name: str, args: dict, repo_path: str) -> str:
    """Execute a reviewer tool call. Returns the text result."""
    if name == "read_file":
        try:
            path = _resolve_path(repo_path, args["path"])
        except (KeyError, ValueError) as exc:
            return f"ERROR: {exc}"
        if not path.exists():
            return f"ERROR: file not found: {path}"
        if path.is_dir():
            # ls -la for directories
            try:
                result = subprocess.run(
                    ["ls", "-la", str(path)],
                    capture_output=True, text=True, timeout=10,
                )
                return (result.stdout or "") + (result.stderr or "")
            except subprocess.TimeoutExpired:
                return "ERROR: ls timed out"
        try:
            text = path.read_text(errors="replace")
        except UnicodeDecodeError:
            return f"ERROR: not a text file: {path}"
        if len(text) > 8000:
            return text[:8000] + "\n... [truncated at 8000 chars]"
        return text

    if name == "shell_command":
        cmd = args.get("command", "")
        if not cmd:
            return "ERROR: empty command"
        # Run from repo root
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=15,
            )
            out = (result.stdout or "") + (result.stderr or "")
            if len(out) > 8000:
                out = out[:8000] + "\n... [truncated at 8000 chars]"
            return out if out else f"(no output, exit={result.returncode})"
        except subprocess.TimeoutExpired:
            return "ERROR: command timed out after 15s"
        except Exception as exc:
            return f"ERROR: {exc}"

    return f"ERROR: unknown tool: {name}"


def _extract_verdict(text: str) -> str:
    """Extract verdict from reviewer response text.

    Scans the entire text (case-insensitive) for known verdict keywords.
    Returns the first match: PASS > FAIL > NEEDS_CLARIFICATION.
    Defaults to NEEDS_CLARIFICATION if none found.
    """
    upper = text.strip().upper()
    for keyword in ("PASS", "FAIL", "NEEDS_CLARIFICATION"):
        if keyword in upper:
            return keyword
    return "NEEDS_CLARIFICATION"


async def _sample_with_tools(
    ctx,
    initial_prompt: str,
    repo_path: str,
    max_rounds: int = 5,
) -> tuple[str, str]:
    """Call create_message with tool-use loop.

    Sends the initial prompt, then handles any tool_use blocks the LLM
    returns by executing them and resending tool_result blocks. Loops
    up to ``max_rounds`` times or until the LLM returns text.

    Returns ``(response_text, stop_reason)``. ``response_text`` is the
    final assistant text (empty if the LLM never produced a final text
    answer, e.g. it kept calling tools until max_rounds).
    """
    messages = [
        types.SamplingMessage(
            role="user",
            content=types.TextContent(type="text", text=initial_prompt),
        )
    ]

    last_text = ""
    for _round in range(max_rounds):
        result = await ctx.session.create_message(
            messages=messages,
            max_tokens=128000,
            tools=REVIEWER_TOOLS,
        )

        # Extract any text in the content blocks
        for block in (result.content if isinstance(result.content, list) else [result.content]):
            if isinstance(block, types.TextContent):
                last_text = block.text

        # If the LLM didn't ask for tools, we're done
        stop_reason = getattr(result, "stopReason", None) or "endTurn"
        if stop_reason != "toolUse":
            return last_text, stop_reason

        # Tool use: execute each tool call and resend results
        tool_uses = [
            b for b in (result.content if isinstance(result.content, list) else [result.content])
            if isinstance(b, types.ToolUseContent)
        ]
        if not tool_uses:
            return last_text, stop_reason

        tool_results = []
        for tu in tool_uses:
            output = _execute_tool(tu.name, tu.input, repo_path)
            tool_results.append(
                types.ToolResultContent(
                    type="tool_result",
                    toolUseId=tu.id,
                    content=[types.TextContent(type="text", text=output)],
                )
            )

        # Append the assistant tool_use and the user tool_results to messages
        messages.append(
            types.SamplingMessage(role="assistant", content=result.content)
        )
        messages.append(
            types.SamplingMessage(role="user", content=tool_results)
        )

    return last_text, "maxRoundsExceeded"


@app.call_tool()
async def call_tool(
    name: str,
    arguments: dict,
) -> list[types.TextContent]:
    if name != "review":
        raise ValueError(f"Unknown tool: {name}")

    repo_path = arguments["repo_path"]
    review_type = arguments["review_type"]
    prompt = arguments["prompt"]
    task_id = arguments.get("task_id")

    request_id = uuid.uuid4().hex
    timestamp_before = datetime.now(timezone.utc).isoformat()
    t_before = time.monotonic()

    log = None
    try:
        # 1-2: Capture Git state before + open log
        git = GitCapturer(repo_path)
        branch = git.branch()
        head_before = git.head_sha()
        dirty = git.is_dirty()

        log_path = _get_log_path(repo_path)
        log = LogWriter(log_path)

        # 3: Write review_started event
        started_event = {
            "event": "review_started",
            "request_id": request_id,
            "timestamp_utc": timestamp_before,
            "repo_path": repo_path,
            "branch": branch,
            "head_sha": head_before,
            "working_tree_dirty": dirty,
            "review_type": review_type,
            "task_id": task_id,
            "prompt": prompt,
        }
        log.append(started_event)

        # 4: Perform review via MCP sampling (with tool-use loop so the
        # reviewer LLM can read files via read_file / shell_command).
        ctx = app.request_context
        response_text, stop_reason = await _sample_with_tools(
            ctx=ctx,
            initial_prompt=prompt,
            repo_path=repo_path,
            max_rounds=5555,
        )

        # Extract verdict from response.
        # The LLM may place PASS/FAIL/NEEDS_CLARIFICATION at the start,
        # middle, or end of its response. Search the whole text for the
        # first known verdict keyword.
        verdict = _extract_verdict(response_text)

        # 5: Capture Git state after
        head_after = git.head_sha()

        # 6: Stale detection
        stale = head_before != head_after
        status = "STALE" if stale else "COMPLETED"

        # 7: Compute duration
        duration_ms = int((time.monotonic() - t_before) * 1000)

        # 8: Write review_completed event
        timestamp_after = datetime.now(timezone.utc).isoformat()
        completed_event = {
            "event": "review_completed",
            "request_id": request_id,
            "timestamp_utc": timestamp_after,
            "repo_path": repo_path,
            "review_type": review_type,
            "task_id": task_id,
            "head_sha_before": head_before,
            "head_sha_after": head_after,
            "status": status,
            "verdict": verdict,
            "response": response_text,
            "stale": stale,
            "duration_ms": duration_ms,
        }
        log.append(completed_event)

        result = {
            "request_id": request_id,
            "status": status,
            "verdict": verdict,
            "response": response_text,
            "stale": stale,
        }

    except GitError as exc:
        result = _error_result(request_id, f"Git error: {exc}")
        if log:
            log.append(_error_event(request_id, repo_path, review_type, task_id, result["response"]))
    except Exception as exc:
        result = _error_result(request_id, str(exc))
        if log:
            log.append(_error_event(request_id, repo_path, review_type, task_id, result["response"]))

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


def _error_result(request_id: str, message: str) -> dict:
    return {
        "request_id": request_id,
        "status": "ERROR",
        "verdict": None,
        "response": message,
        "stale": False,
    }


def _error_event(request_id: str, repo_path: str, review_type: str, task_id: str | None, message: str) -> dict:
    return {
        "event": "review_completed",
        "request_id": request_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repo_path": repo_path,
        "review_type": review_type,
        "task_id": task_id,
        "status": "ERROR",
        "verdict": None,
        "response": message,
        "stale": False,
    }


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="sddtdd-mcp",
                server_version="1.0.0",
                capabilities=types.ServerCapabilities(),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
