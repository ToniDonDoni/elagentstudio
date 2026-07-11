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
VERBOSE_OUTPUT = False


class U2UFailure(AssertionError):
    pass


def ok(message: str) -> None:
    if VERBOSE_OUTPUT:
        print(f"✅ {message}", flush=True)


def note(message: str) -> None:
    if VERBOSE_OUTPUT:
        print(f"   {message}", flush=True)


def event(message: str) -> None:
    if VERBOSE_OUTPUT:
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



def sampling_prompt_text(params: Json) -> str:
    messages = params.get("messages") or []
    parts: list[str] = []
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        blocks = content if isinstance(content, list) else [content]
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
    return "\n".join(parts)


# Helper to dump the sampling prompt for debugging.
def dump_sampling_prompt_for_debug(label: str, params: Json) -> None:
    if not VERBOSE_OUTPUT:
        return

    system_prompt = params.get("systemPrompt")
    if isinstance(system_prompt, str):
        print(f"\n===== BEGIN {label} SYSTEM PROMPT =====", flush=True)
        print(system_prompt, flush=True)
        print(f"===== END {label} SYSTEM PROMPT =====\n", flush=True)
    else:
        print(f"\n===== {label} SYSTEM PROMPT MISSING OR NON-STRING =====", flush=True)
        print(repr(system_prompt), flush=True)
        print(f"===== END {label} SYSTEM PROMPT MISSING OR NON-STRING =====\n", flush=True)

    messages = params.get("messages") or []
    print(f"\n===== BEGIN {label} MESSAGES =====", flush=True)
    for message_index, message in enumerate(messages):
        role = message.get("role") if isinstance(message, dict) else None
        print(f"----- BEGIN {label} MESSAGE {message_index} role={role!r} -----", flush=True)
        content = message.get("content") if isinstance(message, dict) else None
        blocks = content if isinstance(content, list) else [content]
        for block_index, block in enumerate(blocks):
            if isinstance(block, dict) and block.get("type") == "text":
                print(f"----- BEGIN {label} MESSAGE {message_index} TEXT BLOCK {block_index} -----", flush=True)
                print(str(block.get("text", "")), flush=True)
                print(f"----- END {label} MESSAGE {message_index} TEXT BLOCK {block_index} -----", flush=True)
            else:
                print(f"----- BEGIN {label} MESSAGE {message_index} NON-TEXT BLOCK {block_index} -----", flush=True)
                print(repr(block), flush=True)
                print(f"----- END {label} MESSAGE {message_index} NON-TEXT BLOCK {block_index} -----", flush=True)
        print(f"----- END {label} MESSAGE {message_index} role={role!r} -----", flush=True)
    print(f"===== END {label} MESSAGES =====\n", flush=True)

# === Test runner helpers ===

def banner(title: str) -> None:
    if VERBOSE_OUTPUT:
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
    assert_true("getNextTask" in names, f"tools/list must include getNextTask, got {names!r}")
    assert_true("taskStatus" in names, f"tools/list must include taskStatus, got {names!r}")
    assert_true("reviewTask" not in names, f"tools/list must not include removed reviewTask, got {names!r}")


async def call_review(
    client: MCPStdioClient,
    repo: Path,
    prompt: str,
    *,
    task_id: str = "T-U2U",
    timeout: float = 5.0,
) -> Json:
    result = await client.request(
        "tools/call",
        {
            "name": "review",
            "arguments": {
                "repo_path": str(repo),
                "review_type": "U2U_REVIEW",
                "task_id": task_id,
                "prompt": prompt,
            },
        },
        timeout=timeout,
    )
    return extract_tool_call_response(result)


async def call_mcp_tool(
    client: MCPStdioClient,
    name: str,
    arguments: Json,
    *,
    timeout: float = 5.0,
) -> Json:
    result = await client.request(
        "tools/call",
        {"name": name, "arguments": arguments},
        timeout=timeout,
    )
    return extract_tool_call_response(result)


async def test_task_status_tool(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: task_status_tool")
    updated = await call_mcp_tool(
        client,
        "taskStatus",
        {
            "repo_path": str(repo),
            "operation": "update",
            "task_id": "T-U2U-STATUS",
            "task_kind": "IMPLEMENTATION",
            "status": "RUNNING",
            "role": "implementer",
            "execution_id": "u2u-status-task",
        },
    )
    assert_eq(updated["status"], "COMPLETED", "taskStatus update status")
    assert_eq(updated["task"]["status"], "RUNNING", "taskStatus updated task state")

    fetched = await call_mcp_tool(
        client,
        "taskStatus",
        {"repo_path": str(repo), "operation": "get", "task_id": "T-U2U-STATUS"},
    )
    assert_eq(fetched["status"], "COMPLETED", "taskStatus get status")
    assert_eq(fetched["task"]["execution_id"], "u2u-status-task", "taskStatus execution id")
    assert_true(
        (repo / ".sddtdd_skill" / "task-status.json").is_file(),
        "taskStatus must persist task-status.json",
    )
    event("SCENARIO_DONE: task_status_tool")
    ok("taskStatus persists and reads delegated task state through MCP")



# --- Required installed skill policy file helpers and tests ---

REVIEW_REQUIRED_POLICY_FILES = [
    "SKILL.md",
    "SKILL-IMPLEMENTER.md",
    "ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md",
    "references/STAGES.md",
    "references/JOURNAL.md",
]

ORCHESTRATOR_REQUIRED_POLICY_FILES = [
    "SKILL.md",
    "SKILL-ORCHESTRATOR.md",
    "SKILL-IMPLEMENTER.md",
    "ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md",
    "references/STAGES.md",
    "references/JOURNAL.md",
]


def create_installed_skill_policy_root(root: Path, *, missing_file: str | None = None) -> Path:
    skill_root = root / ("installed-skill-missing-" + (missing_file or "none").replace("/", "-"))
    if skill_root.exists():
        shutil.rmtree(skill_root)
    (skill_root / "references").mkdir(parents=True)

    all_files = sorted(set(REVIEW_REQUIRED_POLICY_FILES + ORCHESTRATOR_REQUIRED_POLICY_FILES))
    for relative_path in all_files:
        if relative_path == missing_file:
            continue
        target = skill_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"# U2U installed policy file: {relative_path}\n\n"
            "This file exists only so missing-policy tests can isolate one absent required file.\n"
            "UI user journey rule\n"
            "Canvas onboarding journey\n",
            encoding="utf-8",
        )
    return skill_root


async def assert_missing_review_policy_file_returns_error(
    *,
    server_path: Path,
    base_env: dict[str, str],
    repo: Path,
    temp_root: Path,
    missing_file: str,
) -> None:
    skill_root = create_installed_skill_policy_root(temp_root, missing_file=missing_file)

    env = dict(base_env)
    env["SDDTDD_REVIEW_SKILL_ROOT"] = str(skill_root)
    env["SDDTDD_ORCHESTRATOR_SKILL_ROOT"] = str(skill_root)
    env["SDDTDD_LOG_PATH"] = str(temp_root / f"missing-review-{missing_file.replace('/', '-')}.jsonl")
    env["SDDTDD_ORCHESTRATOR_LOG_PATH"] = str(temp_root / f"missing-orchestrator-{missing_file.replace('/', '-')}.jsonl")

    async with MCPStdioClient(server_path=server_path, env=env, verbose=VERBOSE_OUTPUT) as isolated_client:
        await isolated_client.initialize()
        state = ScenarioState(f"missing_review_policy_{missing_file}")

        async def sampling(params: Json) -> Json:
            state.calls += 1
            fail(f"sampling must not be called when reviewer policy file is missing: {missing_file}")

        isolated_client.sampling_handler = sampling
        response = await call_review(
            isolated_client,
            repo,
            f"U2U missing reviewer installed skill policy file scenario: {missing_file}",
            task_id="T-U2U-MISSING-REVIEW-POLICY",
            timeout=5,
        )
        assert_eq(
            response["status"],
            "ERROR",
            f"review must fail before sampling when reviewer policy file is missing: {missing_file}",
        )
        assert_true(
            "Missing required installed SDDTDD skill policy files" in response["response"],
            f"review error must explain missing installed skill policy file: {missing_file}",
        )
        assert_true(
            missing_file in response["response"],
            f"review error must name the missing reviewer policy file: {missing_file}",
        )
        assert_eq(state.calls, 0, f"review missing policy file must fail before sampling: {missing_file}")


async def assert_missing_orchestrator_policy_file_returns_error(
    *,
    server_path: Path,
    base_env: dict[str, str],
    repo: Path,
    temp_root: Path,
    missing_file: str,
) -> None:
    skill_root = create_installed_skill_policy_root(temp_root, missing_file=missing_file)

    env = dict(base_env)
    env["SDDTDD_REVIEW_SKILL_ROOT"] = str(skill_root)
    env["SDDTDD_ORCHESTRATOR_SKILL_ROOT"] = str(skill_root)
    env["SDDTDD_LOG_PATH"] = str(temp_root / f"missing-review-{missing_file.replace('/', '-')}.jsonl")
    env["SDDTDD_ORCHESTRATOR_LOG_PATH"] = str(temp_root / f"missing-orchestrator-{missing_file.replace('/', '-')}.jsonl")

    async with MCPStdioClient(server_path=server_path, env=env, verbose=VERBOSE_OUTPUT) as isolated_client:
        await isolated_client.initialize()
        state = ScenarioState(f"missing_orchestrator_policy_{missing_file}")

        async def sampling(params: Json) -> Json:
            state.calls += 1
            fail(f"sampling must not be called when orchestrator policy file is missing: {missing_file}")

        isolated_client.sampling_handler = sampling
        response = await call_mcp_tool(
            isolated_client,
            "getNextTask",
            {
                "repo_path": str(repo),
                "task_kind": "INITIAL_USER_INPUT",
                "task_id": None,
                "claimed_result": None,
                "work_journal_id": None,
                "evidence": {
                    "user_input": f"U2U missing orchestrator installed skill policy file scenario: {missing_file}",
                },
            },
            timeout=5,
        )
        assert_eq(
            response["status"],
            "ERROR",
            f"getNextTask must fail before sampling when orchestrator policy file is missing: {missing_file}",
        )
        assert_true(
            "Missing required installed SDDTDD skill policy files" in response["error"],
            f"getNextTask error must explain missing installed skill policy file: {missing_file}",
        )
        assert_true(
            missing_file in response["error"],
            f"getNextTask error must name the missing orchestrator policy file: {missing_file}",
        )
        assert_eq(state.calls, 0, f"orchestrator missing policy file must fail before sampling: {missing_file}")

def read_access_log_events(log_path: Path) -> list[Json]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def count_access_events(log_path: Path, event_name: str) -> int:
    return sum(1 for event_record in read_access_log_events(log_path) if event_record.get("event") == event_name)


async def test_access_log_records_review_start_and_completion(
    client: MCPStdioClient,
    repo: Path,
    log_path: Path,
) -> None:
    event("SCENARIO_BEGIN: access_log_records_review_start_and_completion")
    state = ScenarioState("access_log_happy_path")
    started_before = count_access_events(log_path, "review_started")
    completed_before = count_access_events(log_path, "review_completed")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        return text_result(valid_review_json("PASS", "access log happy path response"))

    client.sampling_handler = sampling
    response = await call_review(
        client,
        repo,
        "U2U access log happy path scenario",
        task_id="T-U2U-ACCESS-LOG",
    )
    assert_eq(response["status"], "COMPLETED", "access log review status")
    assert_eq(response["verdict"], "PASS", "access log review verdict")
    assert_eq(state.calls, 1, "access log test must sample exactly once")

    started_after = count_access_events(log_path, "review_started")
    completed_after = count_access_events(log_path, "review_completed")
    assert_eq(
        started_after,
        started_before + 1,
        "access log must record exactly one review_started event for this review",
    )
    assert_eq(
        completed_after,
        completed_before + 1,
        "access log must record exactly one review_completed event for this review",
    )
    event("SCENARIO_DONE: access_log_records_review_start_and_completion")
    ok("access log records review_started and review_completed for a happy-path review")


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


async def test_reviewer_system_prompt_happy_path(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: reviewer_system_prompt_happy_path")
    state = ScenarioState("reviewer_system_prompt_happy_path")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        dump_sampling_prompt_for_debug("reviewer_system_prompt_happy_path", params)

        system_prompt = params.get("systemPrompt")
        assert_true(isinstance(system_prompt, str), "sampling/createMessage must receive a string systemPrompt")
        assert_true(
            "You are the independent Spec-Driven TDD reviewer MCP for a target repository." in system_prompt,
            "review sampling systemPrompt must identify this server as the independent reviewer",
        )
        assert_true(
            "You are NOT the implementer. You are NOT the orchestrator/orchestrator." in system_prompt,
            "review sampling systemPrompt must explicitly separate reviewer from implementer and orchestrator/orchestrator roles",
        )
        assert_true(
            "read-only independent reviewer" in system_prompt,
            "review sampling systemPrompt must preserve read-only reviewer identity",
        )
        assert_true(
            "You are the implementer" not in system_prompt,
            "review sampling systemPrompt must not use implementer identity",
        )
        assert_true(
            "You are the orchestrator" not in system_prompt and "You are the orchestrator" not in system_prompt,
            "review sampling systemPrompt must not use orchestrator/orchestrator identity",
        )
        assert_true(
            "ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md" in system_prompt,
            "review sampling systemPrompt must include the acceptance criteria boundary guide filename",
        )
        assert_true(
            "UI user journey rule" in system_prompt,
            "review sampling systemPrompt must include the UI user journey rule from the acceptance boundary guide",
        )
        assert_true(
            "Canvas onboarding journey" in system_prompt,
            "review sampling systemPrompt must include the acceptance boundary guide examples",
        )

        return text_result(valid_review_json("PASS", "reviewer system prompt happy path response"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U reviewer system prompt happy path scenario")
    assert_eq(response["status"], "COMPLETED", "reviewer system prompt review status")
    assert_eq(response["verdict"], "PASS", "reviewer system prompt review verdict")
    assert_eq(state.calls, 1, "reviewer system prompt test must sample exactly once")
    event("SCENARIO_DONE: reviewer_system_prompt_happy_path")
    ok("sampling/createMessage receives reviewer systemPrompt, not implementer/orchestrator prompt")


async def test_orchestrator_get_next_task_system_prompt_happy_path(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: orchestrator_get_next_task_system_prompt_happy_path")
    state = ScenarioState("orchestrator_get_next_task_system_prompt_happy_path")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        dump_sampling_prompt_for_debug("orchestrator_get_next_task_system_prompt_happy_path", params)

        system_prompt = params.get("systemPrompt")
        assert_true(isinstance(system_prompt, str), "getNextTask sampling/createMessage must receive a string systemPrompt")
        assert_true(
            "You are the Spec-Driven TDD MCP task orchestrator for a repository." in system_prompt,
            "getNextTask systemPrompt must identify the orchestrator/orchestrator role",
        )
        assert_true(
            "read-only orchestrator/orchestrator" in system_prompt,
            "getNextTask systemPrompt must preserve read-only orchestrator/orchestrator identity",
        )
        assert_true(
            "You are NOT the independent reviewer." in system_prompt,
            "getNextTask systemPrompt must explicitly separate orchestrator from reviewer role",
        )
        assert_true(
            "independent Spec-Driven TDD reviewer MCP" not in system_prompt,
            "getNextTask systemPrompt must not use reviewer identity",
        )
        assert_true(
            "You are the implementer" not in system_prompt,
            "getNextTask systemPrompt must not use implementer identity",
        )
        assert_true(
            "ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md" in system_prompt,
            "getNextTask systemPrompt must include the acceptance criteria boundary guide filename",
        )
        assert_true(
            "UI user journey rule" in system_prompt,
            "getNextTask systemPrompt must include the UI user journey rule from the acceptance boundary guide",
        )
        assert_true(
            "Canvas onboarding journey" in system_prompt,
            "getNextTask systemPrompt must include the acceptance boundary guide examples",
        )

        prompt_text = sampling_prompt_text(params)
        assert_true('"task_kind": "INITIAL_USER_INPUT"' in prompt_text, "initial getNextTask prompt must include task_kind=INITIAL_USER_INPUT")
        assert_true('"user_input": "U2U orchestrator getNextTask happy path scenario"' in prompt_text, "initial getNextTask prompt must carry user_input in evidence")
        assert_true("There is no reviewTask tool." in prompt_text, "getNextTask schema must remove reviewTask tool")

        return text_result(json_dumps({
            "status": "task",
            "task_review": None,
            "next_task": {
                "task_id": "O-000001",
                "task_kind": "USER_INPUT_CAPTURE",
                "instruction": "Capture the user's request in .sddtdd_skill/SPEC-DRAFT.md and journal it.",
                "allowed_scope": [".sddtdd_skill/SPEC-DRAFT.md", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
                "required_evidence": ["Committed SPEC-DRAFT.md and USER_INPUT journal entry."],
                "independent_review_required": False,
                "review_type": None,
                "rationale": "Fresh workflow starts by preserving user input.",
            },
            "rationale": "Initial user input received; issuing first task.",
        }))

    client.sampling_handler = sampling
    response = await call_mcp_tool(
        client,
        "getNextTask",
        {
            "repo_path": str(repo),
            "task_kind": "INITIAL_USER_INPUT",
            "task_id": None,
            "claimed_result": None,
            "work_journal_id": None,
            "evidence": {
                "user_input": "U2U orchestrator getNextTask happy path scenario",
            },
        },
        timeout=5,
    )
    assert_eq(response["status"], "COMPLETED", "getNextTask MCP status")
    assert_eq(response["stale"], False, "getNextTask stale flag")
    assert_eq(response["orchestrator_result"]["status"], "task", "getNextTask orchestrator result status")
    assert_eq(response["orchestrator_result"]["task_review"], None, "initial getNextTask must not return task_review")
    assert_eq(response["orchestrator_result"]["next_task"]["task_id"], "O-000001", "getNextTask orchestrator next task id")
    assert_eq(state.calls, 1, "getNextTask system prompt test must sample exactly once")
    event("SCENARIO_DONE: orchestrator_get_next_task_system_prompt_happy_path")
    ok("getNextTask sampling/createMessage receives orchestrator/orchestrator systemPrompt")


async def test_orchestrator_get_next_task_completed_task_process_gate_happy_path(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: orchestrator_get_next_task_completed_task_process_gate_happy_path")
    state = ScenarioState("orchestrator_get_next_task_completed_task_process_gate_happy_path")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        dump_sampling_prompt_for_debug("orchestrator_get_next_task_completed_task_process_gate_happy_path", params)

        system_prompt = params.get("systemPrompt")
        assert_true(isinstance(system_prompt, str), "completed-task getNextTask sampling/createMessage must receive a string systemPrompt")
        assert_true(
            "You are the Spec-Driven TDD MCP task orchestrator for a repository." in system_prompt,
            "completed-task getNextTask systemPrompt must identify the orchestrator/orchestrator role",
        )
        assert_true(
            "read-only orchestrator/orchestrator" in system_prompt,
            "completed-task getNextTask systemPrompt must preserve read-only orchestrator/orchestrator identity",
        )
        assert_true(
            "You are NOT the independent reviewer." in system_prompt,
            "completed-task getNextTask systemPrompt must explicitly separate orchestrator from reviewer role",
        )
        assert_true(
            "independent Spec-Driven TDD reviewer MCP" not in system_prompt,
            "completed-task getNextTask systemPrompt must not use reviewer identity",
        )
        assert_true(
            "ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md" in system_prompt,
            "completed-task getNextTask systemPrompt must include the acceptance criteria boundary guide filename",
        )
        assert_true(
            "UI user journey rule" in system_prompt,
            "completed-task getNextTask systemPrompt must include the UI user journey rule from the acceptance boundary guide",
        )
        assert_true(
            "Canvas onboarding journey" in system_prompt,
            "completed-task getNextTask systemPrompt must include the acceptance boundary guide examples",
        )

        prompt_text = sampling_prompt_text(params)
        assert_true('"task_kind": "USER_INPUT_CAPTURE"' in prompt_text, "completed-task getNextTask prompt must include submitted task_kind")
        assert_true('"task_id": "O-000001"' in prompt_text, "completed-task getNextTask prompt must include submitted task_id")
        assert_true('"work_journal_id": "J-U2U-WORK-0001"' in prompt_text, "completed-task getNextTask prompt must include work_journal_id")
        assert_true("Derive the required independent reviewer verdict from the submitted task_kind" in prompt_text, "schema must tell orchestrator to derive review type from task_kind")

        return text_result(json_dumps({
            "status": "task",
            "task_review": {
                "status": "PASS",
                "findings": ["The USER_INPUT_CAPTURE work entry is present and process-complete."],
                "required_fixes": [],
                "parent_for_orchestrator_review": "J-U2U-WORK-0001",
                "detail_suggestion": "Orchestrator gate PASS for O-000001.",
                "rationale": "Required process evidence is present.",
            },
            "next_task": {
                "task_id": "O-000002",
                "task_kind": "SPEC_SPEC",
                "instruction": "Derive .sddtdd_skill/SPEC.md from the captured raw user input.",
                "allowed_scope": [".sddtdd_skill/SPEC.md", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
                "required_evidence": ["Committed SPEC.md and SPEC_SPEC journal entry."],
                "independent_review_required": True,
                "review_type": "SPEC_REVIEW",
                "rationale": "Captured user input is process-complete, so SPEC_SPEC is next.",
            },
            "rationale": "Previous task passed process verification; issuing the next task.",
        }))

    client.sampling_handler = sampling
    response = await call_mcp_tool(
        client,
        "getNextTask",
        {
            "repo_path": str(repo),
            "task_kind": "USER_INPUT_CAPTURE",
            "task_id": "O-000001",
            "claimed_result": "Captured user input.",
            "work_journal_id": "J-U2U-WORK-0001",
            "evidence": {"files": [".sddtdd_skill/SPEC-DRAFT.md"]},
        },
        timeout=5,
    )
    assert_eq(response["status"], "COMPLETED", "completed-task getNextTask MCP status")
    assert_eq(response["stale"], False, "completed-task getNextTask stale flag")
    assert_eq(response["orchestrator_result"]["status"], "task", "completed-task getNextTask orchestrator result status")
    assert_eq(response["orchestrator_result"]["task_review"]["status"], "PASS", "completed-task process gate status")
    assert_eq(response["orchestrator_result"]["next_task"]["task_id"], "O-000002", "completed-task orchestrator next task id")
    assert_eq(state.calls, 1, "completed-task getNextTask system prompt test must sample exactly once")
    event("SCENARIO_DONE: orchestrator_get_next_task_completed_task_process_gate_happy_path")
    ok("completed-task getNextTask performs process gate and returns next task")


async def test_missing_installed_skill_policy_returns_error(
    server_path: Path,
    base_env: dict[str, str],
    repo: Path,
    temp_root: Path,
) -> None:
    event("SCENARIO_BEGIN: missing_installed_skill_policy_returns_error")

    for missing_file in REVIEW_REQUIRED_POLICY_FILES:
        event(f"MISSING_POLICY_SUBCASE_BEGIN: reviewer missing {missing_file}")
        await assert_missing_review_policy_file_returns_error(
            server_path=server_path,
            base_env=base_env,
            repo=repo,
            temp_root=temp_root,
            missing_file=missing_file,
        )
        event(f"MISSING_POLICY_SUBCASE_DONE: reviewer missing {missing_file}")

    for missing_file in ORCHESTRATOR_REQUIRED_POLICY_FILES:
        event(f"MISSING_POLICY_SUBCASE_BEGIN: orchestrator missing {missing_file}")
        await assert_missing_orchestrator_policy_file_returns_error(
            server_path=server_path,
            base_env=base_env,
            repo=repo,
            temp_root=temp_root,
            missing_file=missing_file,
        )
        event(f"MISSING_POLICY_SUBCASE_DONE: orchestrator missing {missing_file}")

    event("SCENARIO_DONE: missing_installed_skill_policy_returns_error")
    ok("each missing required installed skill policy file returns ERROR before sampling")


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
                arguments={"command": "sleep 1.25; printf SLOW_DONE"},
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



async def test_empty_response_with_verdict_returns_retry_error_without_repair(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: empty_response_with_verdict_returns_retry_error_without_repair")
    state = ScenarioState("empty_response_with_verdict")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        if state.calls == 1:
            return text_result(json_dumps({"verdict": "PASS", "response": ""}))
        return text_result(valid_review_json("PASS", "repair must not replace an empty review response"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U empty response with verdict scenario", timeout=5)
    assert_eq(response["status"], "ERROR", "empty response with verdict status")
    assert_eq(response["verdict"], None, "empty response with verdict must not produce a verdict")
    assert_true("retry the review" in response["response"].lower(), "empty response with verdict must ask caller to retry")
    assert_eq(state.calls, 1, "empty response with verdict must not enter repair sampling")
    event("SCENARIO_DONE: empty_response_with_verdict_returns_retry_error_without_repair")
    ok("empty response with verdict returns retry ERROR without repair")


async def test_empty_response_without_verdict_returns_retry_error_without_repair(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: empty_response_without_verdict_returns_retry_error_without_repair")
    state = ScenarioState("empty_response_without_verdict")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        if state.calls == 1:
            return text_result(json_dumps({"response": ""}))
        return text_result(valid_review_json("PASS", "repair must not replace an empty review response"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U empty response without verdict scenario", timeout=5)
    assert_eq(response["status"], "ERROR", "empty response without verdict status")
    assert_eq(response["verdict"], None, "empty response without verdict must not produce a verdict")
    assert_true("retry the review" in response["response"].lower(), "empty response without verdict must ask caller to retry")
    assert_eq(state.calls, 1, "empty response without verdict must not enter repair sampling")
    event("SCENARIO_DONE: empty_response_without_verdict_returns_retry_error_without_repair")
    ok("empty response without verdict returns retry ERROR without repair")



#
# Test that any repair sampling response with stopReason=maxTokens is retried before acceptance.
async def test_repair_maxtokens_retries_before_accepting_result(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: repair_maxtokens_retries_before_accepting_result")
    state = ScenarioState("repair_maxtokens_retry")
    raw_reviewer_response = "this primary reviewer answer is invalid and must trigger repair"
    maxtokens_repair_json = valid_review_json(
        "PASS",
        "this repair JSON must not be accepted because stopReason=maxTokens",
    )
    saw_maxtokens_retry_prompt = False

    async def sampling(params: Json) -> Json:
        nonlocal saw_maxtokens_retry_prompt
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        prompt_text = extract_text_content(params)

        if state.calls == 1:
            return text_result(raw_reviewer_response)

        if state.calls == 2:
            assert_true(
                raw_reviewer_response in prompt_text,
                "first repair prompt must include the original raw reviewer response",
            )
            return text_result(maxtokens_repair_json, stop_reason="maxTokens")

        assert_true(
            "maxTokens" in prompt_text,
            "repair retry prompt after maxTokens repair output must mention maxTokens",
        )
        assert_true(
            raw_reviewer_response in prompt_text,
            "repair retry prompt must preserve the original raw reviewer response after maxTokens",
        )
        saw_maxtokens_retry_prompt = True
        return text_result(valid_review_json("PASS", "repair retried after maxTokens output"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U repair maxTokens retry scenario", timeout=5)
    assert_eq(response["status"], "COMPLETED", "repair maxTokens retry review status")
    assert_eq(response["verdict"], "PASS", "repair maxTokens retry review verdict")
    assert_true(
        saw_maxtokens_retry_prompt,
        "repair response returned with stopReason=maxTokens must force a retry instead of being accepted",
    )
    assert_eq(state.calls, 3, "repair maxTokens scenario must use primary + maxTokens repair + successful retry")
    event("SCENARIO_DONE: repair_maxtokens_retries_before_accepting_result")
    ok("repair maxTokens output is retried before acceptance")


# Test that a repair retry prompt after stopReason=maxTokens tells the sampler the current output budget
# and explicitly asks it to keep reasoning and final JSON output shorter to fit that budget.
async def test_repair_maxtokens_retry_prompt_includes_budget_guidance(
    client: MCPStdioClient,
    repo: Path,
) -> None:
    event("SCENARIO_BEGIN: repair_maxtokens_retry_prompt_includes_budget_guidance")
    state = ScenarioState("repair_maxtokens_budget_guidance")
    raw_reviewer_response = "this primary reviewer answer is invalid and must trigger repair budget guidance"
    retry_prompt_text = ""

    async def sampling(params: Json) -> Json:
        nonlocal retry_prompt_text
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        prompt_text = extract_text_content(params)

        if state.calls == 1:
            return text_result(raw_reviewer_response)

        if state.calls == 2:
            assert_true(
                raw_reviewer_response in prompt_text,
                "first repair prompt must include the original raw reviewer response",
            )
            return text_result("", stop_reason="maxTokens")

        retry_prompt_text = prompt_text
        return text_result(valid_review_json("PASS", "repair retried after maxTokens with budget guidance"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U repair maxTokens budget guidance scenario", timeout=5)
    assert_eq(response["status"], "COMPLETED", "repair maxTokens budget guidance review status")
    assert_eq(response["verdict"], "PASS", "repair maxTokens budget guidance review verdict")
    assert_true(retry_prompt_text, "did not observe repair retry prompt after maxTokens")
    assert_true(
        "stop_reason=maxTokens" in retry_prompt_text or "stopReason=maxTokens" in retry_prompt_text,
        "repair retry prompt after maxTokens must mention maxTokens",
    )
    assert_true(
        "sampling max output budget" in retry_prompt_text,
        "repair retry prompt after maxTokens must mention the sampling max output budget",
    )
    assert_true(
        "20000 tokens" in retry_prompt_text,
        "repair retry prompt after maxTokens must include the configured sampling token budget",
    )
    assert_true(
        "reasoning and final JSON output shorter" in retry_prompt_text,
        "repair retry prompt after maxTokens must ask for shorter reasoning and final JSON output",
    )
    assert_true(
        raw_reviewer_response in retry_prompt_text,
        "repair retry prompt must preserve the original raw reviewer response after maxTokens",
    )
    assert_eq(state.calls, 3, "repair maxTokens budget guidance scenario must use primary + empty repair + successful retry")
    event("SCENARIO_DONE: repair_maxtokens_retry_prompt_includes_budget_guidance")
    ok("repair maxTokens retry prompt includes sampling budget guidance")



# Test that primary sampling response with stopReason=maxTokens is retried before acceptance.
async def test_primary_sampling_maxtokens_retries_before_accepting_result(
    client: MCPStdioClient,
    repo: Path,
) -> None:
    event("SCENARIO_BEGIN: primary_sampling_maxtokens_retries_before_accepting_result")
    state = ScenarioState("primary_maxtokens_retry")
    maxtokens_primary_json = valid_review_json(
        "PASS",
        "this primary JSON must not be accepted because stopReason=maxTokens",
    )
    saw_maxtokens_retry_prompt = False

    async def sampling(params: Json) -> Json:
        nonlocal saw_maxtokens_retry_prompt
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        prompt_text = extract_text_content(params)

        if state.calls == 1:
            return text_result(maxtokens_primary_json, stop_reason="maxTokens")

        assert_true(
            "maxTokens" in prompt_text,
            "primary retry prompt after maxTokens output must mention maxTokens",
        )
        saw_maxtokens_retry_prompt = True
        return text_result(valid_review_json("PASS", "primary sampling retried after maxTokens output"))

    client.sampling_handler = sampling
    response = await call_review(
        client,
        repo,
        "U2U primary maxTokens retry scenario",
        timeout=5,
    )

    assert_eq(response["status"], "COMPLETED", "primary maxTokens retry review status")
    assert_eq(response["verdict"], "PASS", "primary maxTokens retry review verdict")
    assert_true(
        saw_maxtokens_retry_prompt,
        "primary response returned with stopReason=maxTokens must force a retry instead of being accepted",
    )
    assert_eq(state.calls, 2, "primary maxTokens scenario must use maxTokens response + successful retry")
    event("SCENARIO_DONE: primary_sampling_maxtokens_retries_before_accepting_result")
    ok("primary maxTokens output is retried before acceptance")


# Test that a primary sampling result that still has stopReason=maxTokens after retry exhaustion
# is not accepted as a completed review, even if the last text is valid reviewer JSON.
async def test_primary_sampling_maxtokens_exhaustion_is_not_accepted_as_completed_review(
    client: MCPStdioClient,
    repo: Path,
) -> None:
    event("SCENARIO_BEGIN: primary_sampling_maxtokens_exhaustion_is_not_accepted_as_completed_review")
    state = ScenarioState("primary_maxtokens_exhaustion")
    maxtokens_primary_json = valid_review_json(
        "PASS",
        "this primary JSON must not be accepted after maxTokens retry exhaustion",
    )

    async def sampling(params: Json) -> Json:
        state.calls += 1
        event(f"MOCK_SAMPLING[{state.name}]: call={state.calls} params={summarize_json(params)}")
        state.seen_params.append(params)
        return text_result(maxtokens_primary_json, stop_reason="maxTokens")

    client.sampling_handler = sampling
    response = await call_review(
        client,
        repo,
        "U2U primary maxTokens exhaustion scenario",
        timeout=8,
    )

    assert_true(
        state.calls >= 2,
        f"primary maxTokens exhaustion scenario should retry before giving up, calls={state.calls}",
    )
    assert_true(
        not (response.get("status") == "COMPLETED" and response.get("verdict") == "PASS"),
        "a final response returned with stopReason=maxTokens after retry exhaustion must not be accepted as COMPLETED/PASS, even if its text is valid JSON",
    )
    event("SCENARIO_DONE: primary_sampling_maxtokens_exhaustion_is_not_accepted_as_completed_review")
    ok("primary maxTokens retry exhaustion is not accepted as completed PASS review")


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



async def test_sampling_jsonrpc_error_returns_error_and_logs_completion(
    client: MCPStdioClient,
    repo: Path,
    log_path: Path,
) -> None:
    event("SCENARIO_BEGIN: sampling_jsonrpc_error_returns_error_and_logs_completion")
    state = ScenarioState("sampling_jsonrpc_error")
    completed_before = count_access_events(log_path, "review_completed")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        raise RuntimeError("deliberate primary sampling failure")

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U primary sampling JSON-RPC error scenario", timeout=5)
    assert_eq(response["status"], "ERROR", "primary sampling error review status")
    assert_eq(response["verdict"], None, "primary sampling error must not produce verdict")
    assert_true("deliberate primary sampling failure" in response.get("response", ""), "error response must include sampling failure detail")
    assert_eq(state.calls, 1, "primary sampling error should call sampling exactly once")
    completed_after = count_access_events(log_path, "review_completed")
    assert_eq(completed_after, completed_before + 1, "sampling error must still write review_completed")
    last_completed = [e for e in read_access_log_events(log_path) if e.get("event") == "review_completed"][-1]
    assert_eq(last_completed.get("status"), "ERROR", "sampling error access log status")
    event("SCENARIO_DONE: sampling_jsonrpc_error_returns_error_and_logs_completion")
    ok("sampling JSON-RPC error returns ERROR and writes review_completed")


async def test_repair_sampling_error_returns_error_and_logs_completion(
    client: MCPStdioClient,
    repo: Path,
    log_path: Path,
) -> None:
    event("SCENARIO_BEGIN: repair_sampling_error_returns_error_and_logs_completion")
    state = ScenarioState("repair_sampling_error")
    completed_before = count_access_events(log_path, "review_completed")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        if state.calls == 1:
            return text_result("this primary response is not parseable and must trigger repair")
        raise RuntimeError("deliberate repair sampling failure")

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U repair sampling JSON-RPC error scenario", timeout=5)
    assert_eq(response["status"], "ERROR", "repair sampling error review status")
    assert_eq(response["verdict"], None, "repair sampling error must not produce verdict")
    assert_true("deliberate repair sampling failure" in response.get("response", ""), "error response must include repair sampling failure detail")
    assert_eq(state.calls, 2, "repair sampling error should use primary + first repair attempt")
    completed_after = count_access_events(log_path, "review_completed")
    assert_eq(completed_after, completed_before + 1, "repair sampling error must still write review_completed")
    last_completed = [e for e in read_access_log_events(log_path) if e.get("event") == "review_completed"][-1]
    assert_eq(last_completed.get("status"), "ERROR", "repair sampling error access log status")
    event("SCENARIO_DONE: repair_sampling_error_returns_error_and_logs_completion")
    ok("repair sampling JSON-RPC error returns ERROR and writes review_completed")


async def test_primary_sampling_maxrounds_exceeded_is_not_accepted_as_completed_review(
    client: MCPStdioClient,
    repo: Path,
) -> None:
    event("SCENARIO_BEGIN: primary_sampling_maxrounds_exceeded_is_not_accepted_as_completed_review")
    state = ScenarioState("primary_maxrounds_exceeded")
    maxrounds_primary_json = valid_review_json(
        "PASS",
        "this primary JSON must not be accepted because stopReason=maxRoundsExceeded",
    )

    async def sampling(params: Json) -> Json:
        state.calls += 1
        return text_result(maxrounds_primary_json, stop_reason="maxRoundsExceeded")

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U primary maxRoundsExceeded scenario", timeout=5)
    assert_eq(response["status"], "ERROR", "primary maxRoundsExceeded review status")
    assert_eq(response["verdict"], None, "primary maxRoundsExceeded must not produce verdict")
    assert_eq(state.calls, 1, "primary maxRoundsExceeded should not repair valid-but-execution-error JSON")
    event("SCENARIO_DONE: primary_sampling_maxrounds_exceeded_is_not_accepted_as_completed_review")
    ok("primary maxRoundsExceeded output is not accepted as completed review")


async def test_repair_maxrounds_exceeded_retries_before_accepting_result(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: repair_maxrounds_exceeded_retries_before_accepting_result")
    state = ScenarioState("repair_maxrounds_exceeded_retry")
    raw_reviewer_response = "this primary reviewer answer is invalid and must trigger repair maxRoundsExceeded"
    maxrounds_repair_json = valid_review_json(
        "PASS",
        "this repair JSON must not be accepted because stopReason=maxRoundsExceeded",
    )
    saw_retry_prompt = False

    async def sampling(params: Json) -> Json:
        nonlocal saw_retry_prompt
        state.calls += 1
        prompt_text = extract_text_content(params)
        if state.calls == 1:
            return text_result(raw_reviewer_response)
        if state.calls == 2:
            assert_true(raw_reviewer_response in prompt_text, "first repair prompt must include original raw reviewer response")
            return text_result(maxrounds_repair_json, stop_reason="maxRoundsExceeded")
        assert_true(
            "maxRoundsExceeded" in prompt_text,
            "repair retry prompt after maxRoundsExceeded repair output must mention maxRoundsExceeded",
        )
        assert_true(raw_reviewer_response in prompt_text, "repair retry prompt must preserve original raw reviewer response")
        saw_retry_prompt = True
        return text_result(valid_review_json("PASS", "repair retried after maxRoundsExceeded output"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U repair maxRoundsExceeded retry scenario", timeout=5)
    assert_eq(response["status"], "COMPLETED", "repair maxRoundsExceeded retry review status")
    assert_eq(response["verdict"], "PASS", "repair maxRoundsExceeded retry verdict")
    assert_true(saw_retry_prompt, "repair response returned with stopReason=maxRoundsExceeded must force retry")
    assert_eq(state.calls, 3, "repair maxRoundsExceeded scenario must use primary + failed repair + retry")
    event("SCENARIO_DONE: repair_maxrounds_exceeded_retries_before_accepting_result")
    ok("repair maxRoundsExceeded output is retried before acceptance")


async def test_unknown_tool_use_name_returns_error_tool_result_and_allows_final_verdict(
    client: MCPStdioClient,
    repo: Path,
    *,
    tool_use_type: str,
) -> None:
    event("SCENARIO_BEGIN: unknown_tool_use_name_returns_error_tool_result_and_allows_final_verdict")
    state = ScenarioState("unknown_tool_use")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        if state.calls == 1:
            return tool_use_result(
                tool_id="u2u-unknown-tool",
                name="does_not_exist",
                arguments={},
                tool_use_type=tool_use_type,
            )
        tool_text = extract_text_content(params)
        assert_true("ERROR: unknown tool: does_not_exist" in tool_text, "unknown tool must be returned as deterministic tool_result error")
        return text_result(valid_review_json("PASS", "unknown tool error was surfaced and handled"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U unknown toolUse name scenario", timeout=5)
    assert_eq(response["status"], "COMPLETED", "unknown toolUse review status")
    assert_eq(response["verdict"], "PASS", "unknown toolUse review verdict")
    assert_eq(state.calls, 2, "unknown toolUse scenario must use tool call + final verdict")
    event("SCENARIO_DONE: unknown_tool_use_name_returns_error_tool_result_and_allows_final_verdict")
    ok("unknown toolUse name returns deterministic error tool_result and final verdict is handled")


async def test_malformed_shell_command_tool_args_return_deterministic_errors(
    client: MCPStdioClient,
    repo: Path,
    *,
    tool_use_type: str,
) -> None:
    event("SCENARIO_BEGIN: malformed_shell_command_tool_args_return_deterministic_errors")
    state = ScenarioState("malformed_shell_args")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        if state.calls == 1:
            return {
                "role": "assistant",
                "content": [
                    {"type": tool_use_type, "id": "missing-command", "name": "shell_command", "input": {}},
                    {"type": tool_use_type, "id": "empty-command", "name": "shell_command", "input": {"command": "   "}},
                    {"type": tool_use_type, "id": "none-command", "name": "shell_command", "input": {"command": None}},
                ],
                "model": "u2u-mock-llm",
                "stopReason": "toolUse",
            }
        tool_text = extract_text_content(params)
        assert_true(tool_text.count("ERROR: empty command") >= 3, "malformed shell_command args must return deterministic empty-command errors")
        return text_result(valid_review_json("PASS", "malformed shell_command arguments returned deterministic errors"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U malformed shell_command tool args scenario", timeout=5)
    assert_eq(response["status"], "COMPLETED", "malformed shell args review status")
    assert_eq(response["verdict"], "PASS", "malformed shell args review verdict")
    assert_eq(state.calls, 2, "malformed shell args scenario must use tool calls + final verdict")
    event("SCENARIO_DONE: malformed_shell_command_tool_args_return_deterministic_errors")
    ok("malformed shell_command tool args return deterministic tool_result errors")


async def test_shell_command_timeout_returns_timed_out_result_and_continues(
    client: MCPStdioClient,
    repo: Path,
    *,
    tool_use_type: str,
) -> None:
    event("SCENARIO_BEGIN: shell_command_timeout_returns_timed_out_result_and_continues")
    state = ScenarioState("shell_timeout")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        if state.calls == 1:
            return tool_use_result(
                tool_id="u2u-timeout-tool",
                name="shell_command",
                arguments={"command": "python3 -c 'import time; time.sleep(10)'"},
                tool_use_type=tool_use_type,
            )
        tool_text = extract_text_content(params)
        assert_true("TIMED_OUT: true" in tool_text, "timeout tool_result must include TIMED_OUT: true")
        assert_true("[TOOL_COMMAND_TIMED_OUT]" in tool_text, "timeout tool_result must include TOOL_COMMAND_TIMED_OUT marker")
        return text_result(valid_review_json("PASS", "shell command timeout was surfaced and review continued"))

    client.sampling_handler = sampling
    started = time.monotonic()
    response = await call_review(client, repo, "U2U shell command timeout scenario", timeout=15)
    elapsed = time.monotonic() - started
    assert_eq(response["status"], "COMPLETED", "shell timeout review status")
    assert_eq(response["verdict"], "PASS", "shell timeout review verdict")
    assert_true(elapsed < 7.5, f"timeout scenario should not hang indefinitely; elapsed={elapsed:.3f}s")
    assert_eq(state.calls, 2, "shell timeout scenario must use tool call + final verdict")
    event("SCENARIO_DONE: shell_command_timeout_returns_timed_out_result_and_continues")
    ok("shell_command timeout returns TIMED_OUT marker and review continues")


async def test_shell_command_process_leak_warning_and_cleanup(
    client: MCPStdioClient,
    repo: Path,
    *,
    tool_use_type: str,
) -> None:
    event("SCENARIO_BEGIN: shell_command_process_leak_warning_and_cleanup")
    state = ScenarioState("process_leak_warning")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        if state.calls == 1:
            return tool_use_result(
                tool_id="u2u-leak-tool",
                name="shell_command",
                arguments={"command": "sh -c 'sleep 30 >/dev/null 2>&1 < /dev/null & printf LEAK_PARENT_DONE'"},
                tool_use_type=tool_use_type,
            )
        tool_text = extract_text_content(params)
        assert_true("TIMED_OUT: false" in tool_text, "process leak scenario must not depend on command timeout")
        assert_true("STDOUT:\nLEAK_PARENT_DONE" in tool_text, "process leak scenario must include parent command stdout")
        assert_true("[PROCESS_LEAK_WARNING]" in tool_text, "process leak scenario must include PROCESS_LEAK_WARNING")
        return text_result(valid_review_json("PASS", "process leak warning was surfaced"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U process leak warning scenario", timeout=8)
    assert_eq(response["status"], "COMPLETED", "process leak warning review status")
    assert_eq(response["verdict"], "PASS", "process leak warning review verdict")
    assert_eq(state.calls, 2, "process leak scenario must use tool call + final verdict")
    event("SCENARIO_DONE: shell_command_process_leak_warning_and_cleanup")
    ok("shell_command process leak warning is surfaced and cleanup path runs")


async def test_large_tool_output_is_truncated(client: MCPStdioClient, repo: Path, *, tool_use_type: str) -> None:
    event("SCENARIO_BEGIN: large_tool_output_is_truncated")
    state = ScenarioState("large_tool_output_truncation")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        if state.calls == 1:
            return tool_use_result(
                tool_id="u2u-large-output-tool",
                name="shell_command",
                arguments={"command": "printf '%*s' 5000 '' | tr ' ' X"},
                tool_use_type=tool_use_type,
            )
        tool_text = extract_text_content(params)
        assert_true("[TOOL_OUTPUT_TRUNCATED]" in tool_text, "large tool output must include truncation marker")
        assert_true("Original chars:" in tool_text, "large tool output truncation must report original size")
        return text_result(valid_review_json("PASS", "large tool output truncation was surfaced"))

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U large tool output truncation scenario", timeout=5)
    assert_eq(response["status"], "COMPLETED", "large tool output truncation review status")
    assert_eq(response["verdict"], "PASS", "large tool output truncation review verdict")
    assert_eq(state.calls, 2, "large tool output scenario must use tool call + final verdict")
    event("SCENARIO_DONE: large_tool_output_is_truncated")
    ok("large shell_command output is truncated before being returned to sampler")


async def test_malformed_tools_call_arguments_return_error(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: malformed_tools_call_arguments_return_error")
    malformed_calls = [
        ({"review_type": "U2U_REVIEW", "prompt": "missing repo_path"}, "missing repo_path"),
        ({"repo_path": str(repo), "prompt": "missing review_type"}, "missing review_type"),
        ({"repo_path": str(repo), "review_type": "U2U_REVIEW"}, "missing prompt"),
    ]
    for arguments, label in malformed_calls:
        result = await client.request("tools/call", {"name": "review", "arguments": arguments}, timeout=5)
        assert_true(result.get("isError") is True, f"malformed tools/call arguments should return isError=true: {label}")
        result_text = extract_text_content(result)
        assert_true("Input validation error" in result_text, f"malformed tools/call error text: {label}: {result_text}")

    non_git_dir = repo.parent / "not-a-git-repo"
    non_git_dir.mkdir()
    response = await call_review(client, non_git_dir, "U2U non-git repo_path scenario", timeout=5)
    assert_eq(response["status"], "ERROR", "non-git repo_path review status")
    assert_eq(response["verdict"], None, "non-git repo_path must not produce verdict")
    event("SCENARIO_DONE: malformed_tools_call_arguments_return_error")
    ok("malformed tools/call arguments and non-git repo_path return errors")


async def test_plain_text_verdict_fallback_accepts_pass_with_body(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: plain_text_verdict_fallback_accepts_pass_with_body")
    state = ScenarioState("plain_text_verdict_fallback")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        return text_result("PASS\nPlain text fallback review body.")

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U plain-text PASS verdict fallback scenario", timeout=5)
    assert_eq(response["status"], "COMPLETED", "plain-text fallback review status")
    assert_eq(response["verdict"], "PASS", "plain-text fallback review verdict")
    assert_true(response.get("response", "").startswith("PASS\n"), "plain-text fallback response must preserve verdict line and body")
    assert_eq(state.calls, 1, "plain-text fallback should not invoke repair")
    event("SCENARIO_DONE: plain_text_verdict_fallback_accepts_pass_with_body")
    ok("plain-text PASS verdict fallback is accepted when it has a body")


async def test_repair_exhaustion_returns_error_not_completed_review(client: MCPStdioClient, repo: Path) -> None:
    event("SCENARIO_BEGIN: repair_exhaustion_returns_error_not_completed_review")
    state = ScenarioState("repair_exhaustion")

    async def sampling(params: Json) -> Json:
        state.calls += 1
        if state.calls == 1:
            return text_result("this primary response is invalid and must trigger repair exhaustion")
        return text_result(valid_review_json("PASS", "valid JSON text must still not be accepted because repair stopReason=maxTokens"), stop_reason="maxTokens")

    client.sampling_handler = sampling
    response = await call_review(client, repo, "U2U repair exhaustion scenario", timeout=8)
    assert_true(state.calls >= 2, f"repair exhaustion should attempt repairs before giving up, calls={state.calls}")
    assert_true(
        not (response.get("status") == "COMPLETED" and response.get("verdict") == "PASS"),
        "repair exhaustion must not be accepted as COMPLETED/PASS, even when repair text is valid JSON with stopReason=maxTokens",
    )
    assert_eq(response["status"], "ERROR", "repair exhaustion review status")
    event("SCENARIO_DONE: repair_exhaustion_returns_error_not_completed_review")
    ok("repair exhaustion returns ERROR instead of completed review")

async def run_all(args: argparse.Namespace) -> None:
    global VERBOSE_OUTPUT
    VERBOSE_OUTPUT = args.verbose
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
        checkout_skill_root = server_path.parents[2] / "skills" / "spec-driven-tdd"
        env.setdefault("SDDTDD_REVIEW_SKILL_ROOT", str(checkout_skill_root))
        env.setdefault("SDDTDD_ORCHESTRATOR_SKILL_ROOT", str(checkout_skill_root))
        env.setdefault("SDDTDD_REVIEW_MAX_SAMPLING_TOKENS", "20000")
        env.setdefault("SDDTDD_REVIEW_MAX_SAMPLING_ROUNDS", "50")
        env.setdefault("SDDTDD_REVIEW_VERDICT_REPAIR_ATTEMPTS", "5")
        env.setdefault("SDDTDD_REVIEW_SHELL_COMMAND_SECONDS", "2")
        env.setdefault("SDDTDD_REVIEW_TOOL_OUTPUT_CHARS", "2000")
        env.setdefault("PYTHONUNBUFFERED", "1")

        note(f"server: {server_path}")
        note(f"temp repo: {repo}")
        note(f"log path: {log_path}")

        async with MCPStdioClient(server_path=server_path, env=env, verbose=args.verbose) as client:
            test_name = "initialize"
            event(f"RUN_TEST: {test_name}")
            banner(test_name)
            try:
                await client.initialize()
            except Exception as exc:
                print(f"FAIL {test_name}: {type(exc).__name__}: {exc}", flush=True)
                raise
            print(f"PASS {test_name}", flush=True)
            event(f"RUN_TEST_DONE: {test_name}")

            test_results: list[tuple[str, bool, str | None]] = []

            async def run_named_test(test_name: str, test_fn: Callable[[], Awaitable[None]]) -> None:
                if not matches_test_mask(test_name, args.test):
                    event(f"RUN_TEST_SKIP: {test_name} masks={args.test!r}")
                    return
                event(f"RUN_TEST: {test_name}")
                banner(test_name)
                try:
                    await test_fn()
                except Exception as exc:
                    message = f"{type(exc).__name__}: {exc}"
                    test_results.append((test_name, False, message))
                    print(f"FAIL {test_name}: {message}", flush=True)
                    if VERBOSE_OUTPUT:
                        traceback.print_exc()
                    event(f"RUN_TEST_FAIL: {test_name} error={message}")
                else:
                    test_results.append((test_name, True, None))
                    print(f"PASS {test_name}", flush=True)
                    event(f"RUN_TEST_DONE: {test_name}")

            await run_named_test("test_startup_and_list_tools", lambda: test_startup_and_list_tools(client))
            await run_named_test("test_task_status_tool", lambda: test_task_status_tool(client, repo))
            await run_named_test("test_basic_review", lambda: test_basic_review(client, repo))
            await run_named_test(
                "test_reviewer_system_prompt_happy_path",
                lambda: test_reviewer_system_prompt_happy_path(client, repo),
            )
            await run_named_test(
                "test_orchestrator_get_next_task_system_prompt_happy_path",
                lambda: test_orchestrator_get_next_task_system_prompt_happy_path(client, repo),
            )
            await run_named_test(
                "test_orchestrator_get_next_task_completed_task_process_gate_happy_path",
                lambda: test_orchestrator_get_next_task_completed_task_process_gate_happy_path(client, repo),
            )
            await run_named_test(
                "test_missing_installed_skill_policy_returns_error",
                lambda: test_missing_installed_skill_policy_returns_error(server_path, env, repo, temp_root),
            )
            await run_named_test(
                "test_access_log_records_review_start_and_completion",
                lambda: test_access_log_records_review_start_and_completion(client, repo, log_path),
            )
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
                "test_empty_response_with_verdict_returns_retry_error_without_repair",
                lambda: test_empty_response_with_verdict_returns_retry_error_without_repair(client, repo),
            )
            await run_named_test(
                "test_empty_response_without_verdict_returns_retry_error_without_repair",
                lambda: test_empty_response_without_verdict_returns_retry_error_without_repair(client, repo),
            )
            await run_named_test(
                "test_repair_maxtokens_retries_before_accepting_result",
                lambda: test_repair_maxtokens_retries_before_accepting_result(client, repo),
            )
            await run_named_test(
                "test_repair_maxtokens_retry_prompt_includes_budget_guidance",
                lambda: test_repair_maxtokens_retry_prompt_includes_budget_guidance(client, repo),
            )
            await run_named_test(
                "test_primary_sampling_maxtokens_retries_before_accepting_result",
                lambda: test_primary_sampling_maxtokens_retries_before_accepting_result(client, repo),
            )
            await run_named_test(
                "test_primary_sampling_maxtokens_exhaustion_is_not_accepted_as_completed_review",
                lambda: test_primary_sampling_maxtokens_exhaustion_is_not_accepted_as_completed_review(client, repo),
            )
            await run_named_test(
                "test_repair_sampling_does_not_block_list_tools",
                lambda: test_repair_sampling_does_not_block_list_tools(client, repo),
            )
            await run_named_test(
                "test_sampling_jsonrpc_error_returns_error_and_logs_completion",
                lambda: test_sampling_jsonrpc_error_returns_error_and_logs_completion(client, repo, log_path),
            )
            await run_named_test(
                "test_repair_sampling_error_returns_error_and_logs_completion",
                lambda: test_repair_sampling_error_returns_error_and_logs_completion(client, repo, log_path),
            )
            await run_named_test(
                "test_primary_sampling_maxrounds_exceeded_is_not_accepted_as_completed_review",
                lambda: test_primary_sampling_maxrounds_exceeded_is_not_accepted_as_completed_review(client, repo),
            )
            await run_named_test(
                "test_repair_maxrounds_exceeded_retries_before_accepting_result",
                lambda: test_repair_maxrounds_exceeded_retries_before_accepting_result(client, repo),
            )
            await run_named_test(
                "test_unknown_tool_use_name_returns_error_tool_result_and_allows_final_verdict",
                lambda: test_unknown_tool_use_name_returns_error_tool_result_and_allows_final_verdict(client, repo, tool_use_type=args.tool_use_type),
            )
            await run_named_test(
                "test_malformed_shell_command_tool_args_return_deterministic_errors",
                lambda: test_malformed_shell_command_tool_args_return_deterministic_errors(client, repo, tool_use_type=args.tool_use_type),
            )
            await run_named_test(
                "test_shell_command_timeout_returns_timed_out_result_and_continues",
                lambda: test_shell_command_timeout_returns_timed_out_result_and_continues(client, repo, tool_use_type=args.tool_use_type),
            )
            await run_named_test(
                "test_shell_command_process_leak_warning_and_cleanup",
                lambda: test_shell_command_process_leak_warning_and_cleanup(client, repo, tool_use_type=args.tool_use_type),
            )
            await run_named_test(
                "test_large_tool_output_is_truncated",
                lambda: test_large_tool_output_is_truncated(client, repo, tool_use_type=args.tool_use_type),
            )
            await run_named_test(
                "test_malformed_tools_call_arguments_return_error",
                lambda: test_malformed_tools_call_arguments_return_error(client, repo),
            )
            await run_named_test(
                "test_plain_text_verdict_fallback_accepts_pass_with_body",
                lambda: test_plain_text_verdict_fallback_accepts_pass_with_body(client, repo),
            )
            await run_named_test(
                "test_repair_exhaustion_returns_error_not_completed_review",
                lambda: test_repair_exhaustion_returns_error_not_completed_review(client, repo),
            )

        expected_review_events = 10 if not args.test else sum(
            1
            for name in (
                "test_basic_review",
                "test_reviewer_system_prompt_happy_path",
                "test_access_log_records_review_start_and_completion",
                "test_tool_use_roundtrip",
                "test_async_shell_command_does_not_block_list_tools",
                "test_invalid_review_triggers_repair",
                "test_empty_response_with_verdict_returns_retry_error_without_repair",
                "test_empty_response_without_verdict_returns_retry_error_without_repair",
                "test_repair_maxtokens_retries_before_accepting_result",
                "test_repair_maxtokens_retry_prompt_includes_budget_guidance",
                "test_primary_sampling_maxtokens_retries_before_accepting_result",
                "test_primary_sampling_maxtokens_exhaustion_is_not_accepted_as_completed_review",
                "test_repair_sampling_does_not_block_list_tools",
                "test_sampling_jsonrpc_error_returns_error_and_logs_completion",
                "test_repair_sampling_error_returns_error_and_logs_completion",
                "test_primary_sampling_maxrounds_exceeded_is_not_accepted_as_completed_review",
                "test_repair_maxrounds_exceeded_retries_before_accepting_result",
                "test_unknown_tool_use_name_returns_error_tool_result_and_allows_final_verdict",
                "test_malformed_shell_command_tool_args_return_deterministic_errors",
                "test_shell_command_timeout_returns_timed_out_result_and_continues",
                "test_shell_command_process_leak_warning_and_cleanup",
                "test_large_tool_output_is_truncated",
                "test_malformed_tools_call_arguments_return_error",
                "test_plain_text_verdict_fallback_accepts_pass_with_body",
                "test_repair_exhaustion_returns_error_not_completed_review",
            )
            if matches_test_mask(name, args.test)
        )
        if expected_review_events > 0:
            assert_true(log_path.exists(), f"access log must exist at {log_path}")
            lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            started = [e for e in lines if e.get("event") == "review_started"]
            completed = [e for e in lines if e.get("event") == "review_completed"]
            assert_true(
                len(started) >= expected_review_events,
                f"expected at least {expected_review_events} review_started events, got {len(started)}",
            )
            assert_true(
                len(completed) >= expected_review_events,
                f"expected at least {expected_review_events} review_completed events, got {len(completed)}",
            )
            if VERBOSE_OUTPUT:
                ok("access log contains review_started/review_completed records")
        elif VERBOSE_OUTPUT:
            ok("no reviewer access-log events expected for selected orchestrator-only tests")

        total = len(test_results)
        passed = sum(1 for _, ok_result, _ in test_results if ok_result)
        failed = total - passed
        print(f"SUMMARY u2u_test_suite: passed={passed} failed={failed} total={total}", flush=True)
        if failed:
            failed_names = ", ".join(name for name, ok_result, _ in test_results if not ok_result)
            print(f"FAIL u2u_test_suite: {passed}/{total} passed; failed tests: {failed_names}", flush=True)
            return 1
        print(f"PASS u2u_test_suite: {passed}/{total} passed", flush=True)
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
    except U2UFailure:
        return 1
    except KeyboardInterrupt:
        print("FAIL interrupted", file=sys.stderr, flush=True)
        return 130
    except Exception as exc:
        print(f"FAIL u2u_test_suite: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        if VERBOSE_OUTPUT:
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
