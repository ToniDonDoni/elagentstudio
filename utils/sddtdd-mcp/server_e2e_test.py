#!/usr/bin/env python3
"""
server_u2utest.py — one-file U2U/end-to-end MCP test harness for sddtdd-mcp.

Run from the directory that contains server.py:

    uv run python server_u2utest.py
    uv run python server_u2utest.py --server ./server.py --verbose

What it does:
  1. Starts the MCP server over stdio.
  2. Sends initialize + initialized.
  3. Verifies tools/list returns the review tool.
  4. Calls review while mocking MCP sampling/createMessage as the LLM.
  5. Exercises normal final JSON review.
  6. Exercises model toolUse -> server shell_command -> tool_result -> final JSON.
  7. Exercises async non-blocking behavior:
       while shell_command sleeps, this test sends tools/list and requires an immediate response.
       This catches sync subprocess.communicate() blocking the MCP event loop.
  8. Exercises invalid reviewer output -> repair sampling attempts -> valid repaired JSON.
  9. Uses a temporary real Git repository so GitCapturer/stale/log paths are real.

This file is intentionally framework-free: no pytest required. It speaks MCP JSON-RPC
over stdio directly and implements only the bits this server needs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable


Json = dict[str, Any]


class U2UFailure(AssertionError):
    pass


def ok(message: str) -> None:
    print(f"✅ {message}")


def note(message: str) -> None:
    print(f"   {message}")


def fail(message: str) -> None:
    raise U2UFailure(message)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def assert_eq(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        fail(f"{message}: expected={expected!r} actual={actual!r}")


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def text_result(text: str, *, stop_reason: str = "endTurn") -> Json:
    """Return a sampling/createMessage result containing assistant text."""
    return {
        "role": "assistant",
        "content": {
            "type": "text",
            "text": text,
        },
        "model": "u2u-mock-llm",
        "stopReason": stop_reason,
    }


def tool_use_result(
    *,
    tool_id: str,
    name: str,
    arguments: Json,
    tool_use_type: str = "tool_use",
) -> Json:
    """Return a sampling/createMessage result asking the MCP server to run a tool.

    Different MCP SDK/Hermes builds have used slightly different JSON spellings
    for tool-use content. The current sddtdd-mcp code builds ToolResultContent
    with type='tool_result', so the matching default here is type='tool_use'.
    Override with --tool-use-type toolUse if your local SDK expects camelCase.
    """
    return {
        "role": "assistant",
        "content": [
            {
                "type": tool_use_type,
                "id": tool_id,
                "name": name,
                "input": arguments,
            }
        ],
        "model": "u2u-mock-llm",
        "stopReason": "toolUse",
    }


def valid_review_json(verdict: str = "PASS", body: str = "U2U mock review passed.") -> str:
    return json_dumps({"verdict": verdict, "response": f"{verdict}\n{body}"})


def extract_text_content(value: Any) -> str:
    """Recursively collect MCP text content for cheap assertions."""
    parts: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            if x.get("type") == "text" and isinstance(x.get("text"), str):
                parts.append(x["text"])
            else:
                for v in x.values():
                    walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(value)
    return "\n".join(parts)


def extract_tool_call_response(result: Json) -> Json:
    """Parse the JSON string returned by server.py's review MCP tool."""
    text = extract_text_content(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise U2UFailure(f"tools/call result did not contain JSON text: {exc}\n{text}") from exc


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)}\n"
            f"cwd={cwd}\n"
            f"stdout={completed.stdout}\n"
            f"stderr={completed.stderr}"
        )
    return completed.stdout


def create_temp_git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    try:
        run(["git", "init", "-b", "main"], cwd=repo)
    except Exception:
        run(["git", "init"], cwd=repo)

    run(["git", "config", "user.email", "u2u@example.invalid"], cwd=repo)
    run(["git", "config", "user.name", "U2U Test"], cwd=repo)

    (repo / "README.md").write_text("# u2u repo\n", encoding="utf-8")
    (repo / ".sddtdd_skill").mkdir()
    (repo / ".sddtdd_skill" / "JOURNAL_SDD_TDD_SKILL.log").write_text(
        "U2U journal placeholder\n",
        encoding="utf-8",
    )
    (repo / ".sddtdd_skill" / "SPEC.md").write_text("U2U spec placeholder\n", encoding="utf-8")
    (repo / ".sddtdd_skill" / "ARCHITECTURE.md").write_text("U2U arch placeholder\n", encoding="utf-8")
    (repo / ".sddtdd_skill" / "TASKS.md").write_text("U2U tasks placeholder\n", encoding="utf-8")

    run(["git", "add", "."], cwd=repo)
    run(["git", "commit", "-m", "initial"], cwd=repo)
    return repo


class MCPStdioClient:
    def __init__(
        self,
        *,
        server_path: Path,
        env: dict[str, str],
        verbose: bool = False,
    ) -> None:
        self.server_path = server_path
        self.env = env
        self.verbose = verbose
        self.process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Json]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self.stderr_lines: list[str] = []
        self.sampling_handler: Callable[[Json], Awaitable[Json]] | None = None

    async def __aenter__(self) -> "MCPStdioClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    async def start(self) -> None:
        cmd = [sys.executable, str(self.server_path)]
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.server_path.parent),
            env=self.env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_loop(), name="mcp-stdout-reader")
        self._stderr_task = asyncio.create_task(self._stderr_loop(), name="mcp-stderr-reader")

    async def stop(self) -> None:
        proc = self.process
        if proc is None:
            return

        if proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()

        for task in (self._reader_task, self._stderr_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def initialize(self) -> None:
        result = await self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "sampling": {},
                },
                "clientInfo": {
                    "name": "server-u2utest",
                    "version": "0.1",
                },
            },
            timeout=10,
        )
        assert_true("protocolVersion" in result, "initialize response must include protocolVersion")
        await self.notify("notifications/initialized", {})
        ok("server initialized")

    async def request(self, method: str, params: Json | None = None, *, timeout: float = 10.0) -> Json:
        req_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Json] = loop.create_future()
        self._pending[req_id] = fut
        message: Json = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        await self._send(message)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(req_id, None)

    async def notify(self, method: str, params: Json | None = None) -> None:
        message: Json = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params
        await self._send(message)

    async def _send_response(self, req_id: int | str, result: Json) -> None:
        await self._send({"jsonrpc": "2.0", "id": req_id, "result": result})

    async def _send_error(self, req_id: int | str, code: int, message: str) -> None:
        await self._send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})

    async def _send(self, payload: Json) -> None:
        proc = self.process
        assert proc is not None and proc.stdin is not None
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        if self.verbose:
            print(f">>> {payload.get('method') or 'response'} id={payload.get('id')}")
        proc.stdin.write(data)
        await proc.stdin.drain()

    async def _read_loop(self) -> None:
        proc = self.process
        assert proc is not None and proc.stdout is not None
        while True:
            message = await self._read_message(proc.stdout)
            if message is None:
                return
            if self.verbose:
                print(f"<<< {message.get('method') or 'response'} id={message.get('id')}")
            await self._dispatch(message)

    async def _stderr_loop(self) -> None:
        proc = self.process
        assert proc is not None and proc.stderr is not None
        while True:
            line = await proc.stderr.readline()
            if not line:
                return
            text = line.decode("utf-8", errors="replace").rstrip()
            self.stderr_lines.append(text)
            if self.verbose:
                print(f"[server stderr] {text}", file=sys.stderr)

    async def _read_message(self, reader: asyncio.StreamReader) -> Json | None:
        while True:
            line = await reader.readline()
            if not line:
                return None
            stripped = line.strip()
            if not stripped:
                continue
            return json.loads(stripped.decode("utf-8"))

    async def _dispatch(self, message: Json) -> None:
        if "id" in message and ("result" in message or "error" in message) and "method" not in message:
            req_id = int(message["id"])
            fut = self._pending.get(req_id)
            if fut is not None and not fut.done():
                if "error" in message:
                    fut.set_exception(RuntimeError(message["error"]))
                else:
                    fut.set_result(message.get("result", {}))
            return

        method = message.get("method")
        req_id = message.get("id")

        if method == "sampling/createMessage":
            if req_id is None:
                return
            try:
                if self.sampling_handler is None:
                    raise RuntimeError("no sampling_handler installed")
                result = await self.sampling_handler(message.get("params", {}))
                await self._send_response(req_id, result)
            except Exception as exc:
                await self._send_error(req_id, -32000, f"u2u sampling handler failed: {exc}")
            return

        if req_id is not None:
            await self._send_error(req_id, -32601, f"u2u client does not implement method {method!r}")


@dataclass
class ScenarioState:
    name: str
    calls: int = 0
    seen_params: list[Json] = field(default_factory=list)
    first_sampling_answered: asyncio.Event = field(default_factory=asyncio.Event)
    tool_result_seen: asyncio.Event = field(default_factory=asyncio.Event)


async def tools_list(client: MCPStdioClient) -> Json:
    return await client.request("tools/list", {}, timeout=5)


def assert_review_tool(list_result: Json) -> None:
    tools = list_result.get("tools") or []
    names = [tool.get("name") for tool in tools]
    assert_true("review" in names, f"tools/list must include review, got {names!r}")


async def call_review(client: MCPStdioClient, repo: Path, prompt: str, *, timeout: float = 30.0) -> Json:
    result = await client.request(
        "tools/call",
        {
            "name": "review",
            "arguments": {
                "repo_path": str(repo),
                "review_type": "U2U_REVIEW",
                "task_id": "T-U2U",
                "prompt": prompt,
            },
        },
        timeout=timeout,
    )
    return extract_tool_call_response(result)


async def test_startup_and_list_tools(client: MCPStdioClient) -> None:
    listed = await tools_list(client)
    assert_review_tool(listed)
    ok("tools/list returns review")


async def test_basic_review(client: MCPStdioClient, repo: Path) -> None:
    state = ScenarioState("basic_review")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        state.seen_params.append(params)
        return text_result(valid_review_json("PASS", "basic mocked reviewer response"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U basic PASS scenario")
    assert_eq(response["status"], "COMPLETED", "basic review status")
    assert_eq(response["verdict"], "PASS", "basic review verdict")
    assert_eq(response["stale"], False, "basic review stale flag")
    assert_eq(state.calls, 1, "basic review must sample exactly once")
    ok("tools/call review returns mocked PASS JSON")


async def test_tool_use_roundtrip(client: MCPStdioClient, repo: Path, *, tool_use_type: str) -> None:
    state = ScenarioState("tool_use_roundtrip")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        state.seen_params.append(params)
        if state.calls == 1:
            return tool_use_result(
                tool_id="u2u-tool-1",
                name="shell_command",
                arguments={"command": "printf U2U_TOOL_RESULT"},
                tool_use_type=tool_use_type,
            )

        tool_text = extract_text_content(params)
        assert_true("U2U_TOOL_RESULT" in tool_text, "second sampling call must include shell_command tool_result")
        state.tool_result_seen.set()
        return text_result(valid_review_json("PASS", "tool use roundtrip passed"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U toolUse scenario")
    assert_eq(response["status"], "COMPLETED", "toolUse review status")
    assert_eq(response["verdict"], "PASS", "toolUse review verdict")
    assert_eq(state.calls, 2, "toolUse scenario must sample twice")
    assert_true(state.tool_result_seen.is_set(), "mock LLM must receive tool_result")
    ok("sampling toolUse -> shell_command -> tool_result roundtrip works")


async def test_async_shell_command_does_not_block_list_tools(
    client: MCPStdioClient,
    repo: Path,
    *,
    tool_use_type: str,
) -> None:
    state = ScenarioState("async_nonblocking")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        state.seen_params.append(params)
        if state.calls == 1:
            result = tool_use_result(
                tool_id="u2u-slow-tool",
                name="shell_command",
                arguments={"command": "sleep 3; printf SLOW_DONE"},
                tool_use_type=tool_use_type,
            )
            # Let the test send tools/list while the server is executing shell_command.
            state.first_sampling_answered.set()
            return result

        tool_text = extract_text_content(params)
        assert_true("SLOW_DONE" in tool_text, "second sampling call must include slow command output")
        return text_result(valid_review_json("PASS", "async shell command did not block MCP"))

    client.sampling_handler = sampling

    call_task = asyncio.create_task(
        call_review(client, repo, "U2U async nonblocking shell_command scenario", timeout=20),
        name="slow-review-call",
    )

    await asyncio.wait_for(state.first_sampling_answered.wait(), timeout=5)
    await asyncio.sleep(0.25)

    started = time.monotonic()
    listed = await client.request("tools/list", {}, timeout=1.0)
    elapsed = time.monotonic() - started
    assert_review_tool(listed)
    assert_true(
        elapsed < 1.0,
        f"tools/list should answer while shell_command sleeps; took {elapsed:.3f}s",
    )

    response = await call_task
    assert_eq(response["status"], "COMPLETED", "async nonblocking review status")
    assert_eq(response["verdict"], "PASS", "async nonblocking review verdict")
    ok(f"tools/list answered during long shell_command in {elapsed:.3f}s")


async def test_invalid_review_triggers_repair(client: MCPStdioClient, repo: Path) -> None:
    state = ScenarioState("invalid_review_repair")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        state.seen_params.append(params)
        if state.calls == 1:
            return text_result("this is not JSON, not PASS/FAIL/NEEDS_CLARIFICATION either")
        if state.calls == 2:
            return text_result(json_dumps({"verdict": "PASS"}))  # missing response
        if state.calls == 3:
            return text_result(json_dumps({"verdict": "MAYBE", "response": "MAYBE\nnope"}))
        return text_result(valid_review_json("PASS", "repair eventually produced valid JSON"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U invalid reviewer output repair scenario", timeout=30)
    assert_eq(response["status"], "COMPLETED", "repair review status")
    assert_eq(response["verdict"], "PASS", "repair review verdict")
    assert_true(state.calls >= 4, f"repair scenario should use primary + repair attempts, calls={state.calls}")
    ok(f"invalid reviewer output triggered repair and completed after {state.calls} sampling calls")


async def run_all(args: argparse.Namespace) -> None:
    server_path = Path(args.server).expanduser().resolve()
    if not server_path.exists():
        fail(f"server file does not exist: {server_path}")

    temp_root_obj = tempfile.TemporaryDirectory(prefix="sddtdd-mcp-u2u-")
    temp_root = Path(temp_root_obj.name)
    try:
        repo = create_temp_git_repo(temp_root)
        log_path = temp_root / "review-access.jsonl"

        env = os.environ.copy()
        env["SDDTDD_LOG_PATH"] = str(log_path)
        env.setdefault("SDDTDD_REVIEW_MAX_SAMPLING_TOKENS", "20000")
        env.setdefault("SDDTDD_REVIEW_MAX_SAMPLING_ROUNDS", "50")
        env.setdefault("SDDTDD_REVIEW_VERDICT_REPAIR_ATTEMPTS", "5")
        env.setdefault("PYTHONUNBUFFERED", "1")

        note(f"server: {server_path}")
        note(f"temp repo: {repo}")
        note(f"log path: {log_path}")

        async with MCPStdioClient(server_path=server_path, env=env, verbose=args.verbose) as client:
            await client.initialize()
            await test_startup_and_list_tools(client)
            await test_basic_review(client, repo)
            await test_tool_use_roundtrip(client, repo, tool_use_type=args.tool_use_type)
            await test_async_shell_command_does_not_block_list_tools(client, repo, tool_use_type=args.tool_use_type)
            await test_invalid_review_triggers_repair(client, repo)

        assert_true(log_path.exists(), f"access log must exist at {log_path}")
        lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        started = [e for e in lines if e.get("event") == "review_started"]
        completed = [e for e in lines if e.get("event") == "review_completed"]
        assert_true(len(started) >= 4, f"expected at least 4 review_started events, got {len(started)}")
        assert_true(len(completed) >= 4, f"expected at least 4 review_completed events, got {len(completed)}")
        ok("access log contains review_started/review_completed records")

        print("\n🎉 U2U MCP test suite passed. Async server lives; communicate() кафедра закрыта.")
    finally:
        if args.keep_temp:
            note(f"kept temp dir: {temp_root}")
        else:
            temp_root_obj.cleanup()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="U2U/end-to-end test harness for sddtdd-mcp server.py")
    parser.add_argument(
        "--server",
        default=str(Path(__file__).with_name("server.py")),
        help="Path to MCP server.py. Default: ./server.py next to this file.",
    )
    parser.add_argument(
        "--tool-use-type",
        default=os.environ.get("U2U_TOOL_USE_TYPE", "tool_use"),
        choices=["tool_use", "toolUse"],
        help="JSON type spelling for sampling tool-use content. Default: tool_use.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print raw MCP traffic and server stderr.")
    parser.add_argument("--keep-temp", action="store_true", help="Do not delete the temporary Git repo/log dir.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        asyncio.run(run_all(args))
        return 0
    except U2UFailure as exc:
        print(f"\n❌ U2U FAILED: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\n💥 U2U CRASHED: {type(exc).__name__}: {exc}", file=sys.stderr)
        if "--verbose" in argv:
            raise
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
