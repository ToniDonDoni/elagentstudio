"""sddtdd-broker-mcp — MCP task broker for Spec-Driven TDD.

The server exposes a broker contract around three tools: init_task, verify_task,
and next_task. It reads repository state and asks the MCP sampling model to act
as a task broker using the shared SDDTDD process skill plus the broker skill.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

import mcp.server as mcp_server
import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server


app = mcp_server.Server("sddtdd-broker-mcp")

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESS_SKILL = REPO_ROOT / "skills" / "spec-driven-tdd" / "SKILL.md"
BROKER_SKILL = REPO_ROOT / "skills" / "sddtdd-task-broker" / "SKILL.md"


def _git(repo_path: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def capture_repo_state(repo_path: str) -> dict[str, Any]:
    path = Path(repo_path).resolve()
    if not path.exists():
        raise RuntimeError(f"repo_path does not exist: {repo_path}")

    state: dict[str, Any] = {
        "repo_path": str(path),
        "branch": _git(str(path), "rev-parse", "--abbrev-ref", "HEAD"),
        "head_sha": _git(str(path), "rev-parse", "HEAD"),
        "status_porcelain": _git(str(path), "status", "--porcelain"),
        "files": {},
    }

    for name in [
        "JOURNAL_SDD_TDD_SKILL.log",
        "SPEC-DRAFT.md",
        "SPEC.md",
        "ARCHITECTURE.md",
        "TASKS.md",
    ]:
        file_path = path / name
        if file_path.exists() and file_path.is_file():
            state["files"][name] = file_path.read_text(errors="replace")
        else:
            state["files"][name] = None

    return state


def _read_skill(path: Path) -> str:
    if not path.exists():
        return f"MISSING SKILL: {path}"
    return path.read_text(errors="replace")


def build_broker_prompt(tool_name: str, arguments: dict[str, Any], repo_state: dict[str, Any]) -> str:
    return "\n".join([
        "You are the SDDTDD MCP task broker.",
        "Return JSON only. Do not implement, edit files, run tests, or review artifacts.",
        "Decide according to the provided skills and current repository state.",
        "",
        "# Tool call",
        json.dumps({"tool": tool_name, "arguments": arguments}, ensure_ascii=False, indent=2),
        "",
        "# Process skill: spec-driven-tdd",
        _read_skill(PROCESS_SKILL),
        "",
        "# Broker skill: sddtdd-task-broker",
        _read_skill(BROKER_SKILL),
        "",
        "# Repository state",
        json.dumps(repo_state, ensure_ascii=False, indent=2),
    ])


def parse_json_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        data = {
            "status": "ERROR",
            "summary": "Broker sampling response was not valid JSON",
            "raw_response": text,
        }
    if not isinstance(data, dict):
        return {"status": "ERROR", "summary": "Broker response was not a JSON object", "raw_response": text}
    return data


def _tool_schema(required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Absolute path to the Git repository"},
            "user_input": {"type": "string", "description": "Original user request or pointer to it"},
            "task_id": {"type": "string", "description": "Broker-assigned task id"},
            "previous_task_id": {"type": "string", "description": "Previously verified broker task id"},
            "claimed_result": {"type": "string", "description": "Implementer completion summary"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "process_skill": {"type": "string"},
            "implementer_skill": {"type": "string"},
            "broker_skill": {"type": "string"},
        },
        "required": required,
    }


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="init_task",
            description="Initialize or resume brokered Spec-Driven TDD work and return the first legal task",
            inputSchema=_tool_schema(["repo_path", "user_input"]),
        ),
        types.Tool(
            name="verify_task",
            description="Verify that the implementer completed the currently assigned broker task",
            inputSchema=_tool_schema(["repo_path", "task_id", "claimed_result"]),
        ),
        types.Tool(
            name="next_task",
            description="Return the next legal Spec-Driven TDD task after a verified task",
            inputSchema=_tool_schema(["repo_path"]),
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name not in {"init_task", "verify_task", "next_task"}:
        raise ValueError(f"Unknown tool: {name}")

    request_id = uuid.uuid4().hex
    try:
        repo_state = capture_repo_state(arguments["repo_path"])
        prompt = build_broker_prompt(name, arguments, repo_state)
        ctx = app.request_context
        sampling_result = await ctx.session.create_message(
            messages=[
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(type="text", text=prompt),
                )
            ],
            max_tokens=4096,
        )
        content = sampling_result.content
        response_text = content.text if hasattr(content, "text") else str(content)
        result = parse_json_response(response_text)
        result.setdefault("request_id", request_id)
        result.setdefault("repo_head", repo_state["head_sha"])
    except Exception as exc:
        result = {
            "request_id": request_id,
            "status": "ERROR",
            "summary": str(exc),
        }

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="sddtdd-broker-mcp",
                server_version="1.0.0",
                capabilities=types.ServerCapabilities(),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
