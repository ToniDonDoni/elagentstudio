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
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable



Json = dict[str, Any]

# Increase the stream reader limit to handle large JSON lines from MCP.
STREAM_READER_LIMIT = 16 * 1024 * 1024


class U2UFailure(AssertionError):
    pass


def ok(message: str) -> None:
    print(f"✅ {message}", flush=True)


def note(message: str) -> None:
    print(f"   {message}", flush=True)


def event(message: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [u2u] {message}", flush=True)



def summarize_json(value: Any, *, limit: int = 1200) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        text = repr(value)
    if len(text) > limit:
        return text[:limit] + f"... ({len(text)} chars total)"
    return text


# === Test runner helpers ===

def banner(title: str) -> None:
    line = "=" * 96
    print(f"\n{line}\nTEST: {title.upper()}\n{line}", flush=True)


def matches_test_mask(test_name: str, masks: list[str]) -> bool:
    if not masks:
        return True
    lowered_name = test_name.lower()
    return any(mask.lower() in lowered_name for mask in masks)


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
        event(f"START_SERVER: cmd={cmd!r} cwd={str(self.server_path.parent)!r}")
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.server_path.parent),
            env=self.env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=STREAM_READER_LIMIT,
        )
        event(f"START_SERVER: pid={self.process.pid}")
        self._reader_task = asyncio.create_task(self._read_loop(), name="mcp-stdout-reader")
        self._stderr_task = asyncio.create_task(self._stderr_loop(), name="mcp-stderr-reader")

    async def stop(self) -> None:
        proc = self.process
        if proc is None:
            return
        event(f"STOP_SERVER: returncode={proc.returncode}")

        if proc.returncode is None:
            try:
                event(f"STOP_SERVER: terminate pid={proc.pid}")
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                try:
                    event(f"STOP_SERVER: kill pid={proc.pid}")
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
        event("INITIALIZE: sending initialize")
        result = await self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "sampling": {
                        "tools": {},
                    },
                },
                "clientInfo": {
                    "name": "server-u2utest",
                    "version": "0.1",
                },
            },
            timeout=10,
        )
        event(f"INITIALIZE: response={summarize_json(result)}")
        assert_true("protocolVersion" in result, "initialize response must include protocolVersion")
        event("INITIALIZE: sending notifications/initialized")
        await self.notify("notifications/initialized", {})
        ok("server initialized")

    async def request(self, method: str, params: Json | None = None, *, timeout: float = 10.0) -> Json:
        req_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Json] = loop.create_future()
        self._pending[req_id] = fut
        event(f"REQUEST_BEGIN: id={req_id} method={method} timeout={timeout} params={summarize_json(params or {})}")
        message: Json = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        await self._send(message)
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            event(f"REQUEST_DONE: id={req_id} method={method} result={summarize_json(result)}")
            return result
        except Exception as exc:
            event(f"REQUEST_FAIL: id={req_id} method={method} error={type(exc).__name__}: {exc}")
            if self.stderr_lines:
                event("REQUEST_FAIL: recent server stderr:\n" + "\n".join(self.stderr_lines[-40:]))
            raise
        finally:
            self._pending.pop(req_id, None)

    async def notify(self, method: str, params: Json | None = None) -> None:
        message: Json = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params
        event(f"NOTIFY_SEND: method={method} params={summarize_json(params or {})}")
        await self._send(message)

    async def _send_response(self, req_id: int | str, result: Json) -> None:
        event(f"CLIENT_RESPONSE_SEND: id={req_id} result={summarize_json(result)}")
        await self._send({"jsonrpc": "2.0", "id": req_id, "result": result})

    async def _send_error(self, req_id: int | str, code: int, message: str) -> None:
        event(f"CLIENT_ERROR_SEND: id={req_id} code={code} message={message}")
        await self._send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})

    async def _send(self, payload: Json) -> None:
        proc = self.process
        assert proc is not None and proc.stdin is not None
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        event(f"JSONRPC_SEND: method={payload.get('method') or 'response'} id={payload.get('id')} bytes={len(data)} payload={summarize_json(payload)}")
        if self.verbose:
            print(f">>> {payload.get('method') or 'response'} id={payload.get('id')}")
        proc.stdin.write(data)
        await proc.stdin.drain()

    async def _read_loop(self) -> None:
        proc = self.process
        assert proc is not None and proc.stdout is not None
        event("STDOUT_READER: started")
        try:
            while True:
                message = await self._read_message(proc.stdout)
                if message is None:
                    event("STDOUT_READER: EOF")
                    return
                event(f"JSONRPC_RECV: method={message.get('method') or 'response'} id={message.get('id')} payload={summarize_json(message)}")
                if self.verbose:
                    print(f"<<< {message.get('method') or 'response'} id={message.get('id')}")
                await self._dispatch(message)
        except asyncio.CancelledError:
            event("STDOUT_READER: cancelled")
            raise
        except Exception as exc:
            event(f"STDOUT_READER: crashed {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(exc)
            raise

    async def _stderr_loop(self) -> None:
        proc = self.process
        assert proc is not None and proc.stderr is not None
        event("STDERR_READER: started")
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    event("STDERR_READER: EOF")
                    return
                text = line.decode("utf-8", errors="replace").rstrip()
                self.stderr_lines.append(text)
                event(f"SERVER_STDERR: {text}")
                if self.verbose:
                    print(f"[server stderr] {text}", file=sys.stderr)
        except asyncio.CancelledError:
            event("STDERR_READER: cancelled")
            raise

    async def _read_message(self, reader: asyncio.StreamReader) -> Json | None:
        while True:
            try:
                line = await reader.readline()
            except ValueError as exc:
                event(
                    "STDOUT_LINE_ERROR: readline exceeded stream limit "
                    f"limit={STREAM_READER_LIMIT} error={exc}"
                )
                raise
            event(f"STDOUT_LINE: bytes={len(line)} preview={line[:500]!r}")
            if not line:
                return None
            stripped = line.strip()
            if not stripped:
                continue
            return json.loads(stripped.decode("utf-8"))

    async def _dispatch(self, message: Json) -> None:
        event(f"DISPATCH: message={summarize_json(message)}")
        if "id" in message and ("result" in message or "error" in message) and "method" not in message:
            req_id = int(message["id"])
            fut = self._pending.get(req_id)
            if fut is not None and not fut.done():
                if "error" in message:
                    fut.set_exception(RuntimeError(message["error"]))
                else:
                    fut.set_result(message.get("result", {}))
            event(f"DISPATCH: completed pending request id={req_id}")
            return

        method = message.get("method")
        req_id = message.get("id")

        if method == "sampling/createMessage":
            if req_id is None:
                return
            event(f"DISPATCH: scheduling sampling/createMessage handler id={req_id}")
            task = asyncio.create_task(
                self._handle_sampling_create_message(req_id, message.get("params", {})),
                name=f"u2u-sampling-create-message-{req_id}",
            )
            task.add_done_callback(self._log_background_task_result)
            return

        if req_id is not None:
            await self._send_error(req_id, -32601, f"u2u client does not implement method {method!r}")


    def _log_background_task_result(self, task: asyncio.Task[Any]) -> None:
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            event(f"BACKGROUND_TASK_CANCELLED: {task.get_name()}")
            return
        if exc is not None:
            event(
                f"BACKGROUND_TASK_FAILED: {task.get_name()} {type(exc).__name__}: {exc}\n"
                f"{''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}"
            )
        else:
            event(f"BACKGROUND_TASK_DONE: {task.get_name()}")


    async def _handle_sampling_create_message(self, req_id: int | str, params: Json) -> None:
        event(f"SAMPLING_HANDLER_BEGIN: id={req_id} params={summarize_json(params)}")
        try:
            if self.sampling_handler is None:
                raise RuntimeError("no sampling_handler installed")
            result = await self.sampling_handler(params)
            event(f"SAMPLING_HANDLER_RESULT: id={req_id} result={summarize_json(result)}")
            await self._send_response(req_id, result)
        except Exception as exc:
            event(f"SAMPLING_HANDLER_ERROR: id={req_id} {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            await self._send_error(req_id, -32000, f"u2u sampling handler failed: {exc}")


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


async def call_review(client: MCPStdioClient, repo: Path, prompt: str, *, timeout: float = 5.0) -> Json:
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
    event("SCENARIO_BEGIN: startup_and_list_tools")
    listed = await tools_list(client)
    assert_review_tool(listed)
    event("SCENARIO_DONE: startup_and_list_tools")
    ok("tools/list returns review")


async def test_basic_review(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: basic_review")
    state = ScenarioState("basic_review")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        return text_result(valid_review_json("PASS", "basic mocked reviewer response"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U basic PASS scenario")
    assert_eq(response["status"], "COMPLETED", "basic review status")
    assert_eq(response["verdict"], "PASS", "basic review verdict")
    assert_eq(response["stale"], False, "basic review stale flag")
    assert_eq(state.calls, 1, "basic review must sample exactly once")
    event("SCENARIO_DONE: basic_review")
    ok("tools/call review returns mocked PASS JSON")


async def test_tool_use_roundtrip(client: MCPStdioClient, repo: Path, *, tool_use_type: str) -> None:
    event("SCENARIO_BEGIN: tool_use_roundtrip")
    state = ScenarioState("tool_use_roundtrip")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
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
    event("SCENARIO_DONE: tool_use_roundtrip")
    ok("sampling toolUse -> shell_command -> tool_result roundtrip works")


async def test_async_shell_command_does_not_block_list_tools(
    client: MCPStdioClient,
    repo: Path,
    *,
    tool_use_type: str,
) -> None:
    event("SCENARIO_BEGIN: async_shell_command_does_not_block_list_tools")
    state = ScenarioState("async_nonblocking")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
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
        call_review(client, repo, "U2U async nonblocking shell_command scenario", timeout=8),
        name="slow-review-call",
    )

    await asyncio.wait_for(state.first_sampling_answered.wait(), timeout=5)
    event("ASYNC_SHELL: waiting until mock returns toolUse")
    await asyncio.sleep(0.25)

    started = time.monotonic()
    event("ASYNC_SHELL: sending tools/list while shell_command should be running")
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
    event("SCENARIO_DONE: async_shell_command_does_not_block_list_tools")
    ok(f"tools/list answered during long shell_command in {elapsed:.3f}s")


async def test_invalid_review_triggers_repair(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: invalid_review_triggers_repair")
    state = ScenarioState("invalid_review_repair")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        if state.calls == 1:
            return text_result("this is not JSON, not PASS/FAIL/NEEDS_CLARIFICATION either")
        if state.calls == 2:
            return text_result(json_dumps({"verdict": "PASS"}))  # missing response
        if state.calls == 3:
            return text_result(json_dumps({"verdict": "MAYBE", "response": "MAYBE\nnope"}))
        return text_result(valid_review_json("PASS", "repair eventually produced valid JSON"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U invalid reviewer output repair scenario", timeout=5)
    assert_eq(response["status"], "COMPLETED", "repair review status")
    assert_eq(response["verdict"], "PASS", "repair review verdict")
    assert_true(state.calls >= 4, f"repair scenario should use primary + repair attempts, calls={state.calls}")
    event(f"SCENARIO_DONE: invalid_review_triggers_repair")
    ok(f"invalid reviewer output triggered repair and completed after {state.calls} sampling calls")


# Test that repair sampling create_message does not block tools/list.
async def test_repair_sampling_does_not_block_list_tools(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: repair_sampling_does_not_block_list_tools")
    state = ScenarioState("repair_sampling_nonblocking")
    repair_request_received = asyncio.Event()
    allow_repair_response = asyncio.Event()

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        if state.calls == 1:
            return text_result("this primary reviewer answer is deliberately invalid and must trigger repair")

        # The server is now inside await ctx.session.create_message(...) for the repair request.
        # Hold the mock LLM response back so the test can send tools/list while that await is pending.
        repair_request_received.set()
        event("REPAIR_NONBLOCKING: waiting until server sends repair sampling request")
        await asyncio.wait_for(allow_repair_response.wait(), timeout=5)
        return text_result(valid_review_json("PASS", "repair sampling did not block MCP tools/list"))

    client.sampling_handler = sampling
    call_task = asyncio.create_task(
        call_review(client, repo, "U2U repair sampling nonblocking scenario", timeout=5),
        name="repair-nonblocking-review-call",
    )

    await asyncio.wait_for(repair_request_received.wait(), timeout=10)

    started = time.monotonic()
    event("REPAIR_NONBLOCKING: sending tools/list while repair create_message is pending")
    listed = await client.request("tools/list", {}, timeout=1.0)
    elapsed = time.monotonic() - started
    assert_review_tool(listed)
    assert_true(
        elapsed < 1.0,
        f"tools/list should answer while repair sampling create_message is pending; took {elapsed:.3f}s",
    )

    event("REPAIR_NONBLOCKING: allowing mock repair response")
    allow_repair_response.set()
    response = await call_task
    assert_eq(response["status"], "COMPLETED", "repair nonblocking review status")
    assert_eq(response["verdict"], "PASS", "repair nonblocking review verdict")
    assert_true(state.calls >= 2, f"repair nonblocking scenario should sample at least twice, calls={state.calls}")
    event("SCENARIO_DONE: repair_sampling_does_not_block_list_tools")
    ok(f"tools/list answered during pending repair sampling in {elapsed:.3f}s")


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
            event("RUN_TEST: initialize")
            banner("initialize")
            await client.initialize()
            event("RUN_TEST_DONE: initialize")

            async def run_named_test(test_name: str, test_fn: Callable[[], Awaitable[None]]) -> None:
                if not matches_test_mask(test_name, args.test):
                    event(f"RUN_TEST_SKIP: {test_name} masks={args.test!r}")
                    return
                event(f"RUN_TEST: {test_name}")
                banner(test_name)
                await test_fn()
                event(f"RUN_TEST_DONE: {test_name}")

            await run_named_test("test_startup_and_list_tools", lambda: test_startup_and_list_tools(client))
            await run_named_test("test_basic_review", lambda: test_basic_review(client, repo))
            await run_named_test(
                "test_tool_use_roundtrip",
                lambda: test_tool_use_roundtrip(client, repo, tool_use_type=args.tool_use_type),
            )
            await run_named_test(
                "test_async_shell_command_does_not_block_list_tools",
                lambda: test_async_shell_command_does_not_block_list_tools(client, repo, tool_use_type=args.tool_use_type),
            )
            await run_named_test("test_invalid_review_triggers_repair", lambda: test_invalid_review_triggers_repair(client, repo))
            await run_named_test(
                "test_repair_sampling_does_not_block_list_tools",
                lambda: test_repair_sampling_does_not_block_list_tools(client, repo),
            )

        assert_true(log_path.exists(), f"access log must exist at {log_path}")
        lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        started = [e for e in lines if e.get("event") == "review_started"]
        completed = [e for e in lines if e.get("event") == "review_completed"]
        expected_review_events = 5 if not args.test else sum(
            1
            for name in (
                "test_basic_review",
                "test_tool_use_roundtrip",
                "test_async_shell_command_does_not_block_list_tools",
                "test_invalid_review_triggers_repair",
                "test_repair_sampling_does_not_block_list_tools",
            )
            if matches_test_mask(name, args.test)
        )
        assert_true(
            len(started) >= expected_review_events,
            f"expected at least {expected_review_events} review_started events, got {len(started)}",
        )
        assert_true(
            len(completed) >= expected_review_events,
            f"expected at least {expected_review_events} review_completed events, got {len(completed)}",
        )
        ok("access log contains review_started/review_completed records")

        print("\n🎉 U2U MCP test suite passed. Async server lives; communicate() department is closed.")
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
    parser.add_argument(
        "--test",
        action="append",
        default=[],
        metavar="MASK",
        help="Run only tests whose names contain MASK, case-insensitive. Can be specified multiple times. Default: run all tests.",
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
        print(f"\n❌ U2U FAILED: {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr, flush=True)
        return 130
    except Exception as exc:
        print(f"\n💥 U2U CRASHED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
