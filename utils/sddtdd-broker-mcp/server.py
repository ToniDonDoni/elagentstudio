"""sddtdd-broker-mcp — MCP task broker for Spec-Driven TDD.

The server exposes a broker contract around three tools: init_task, verify_task,
and next_task. It reads repository state and asks the MCP sampling model to act
as a task broker using the shared SDDTDD process skill plus the in-folder
orchestrator role file.
"""

from __future__ import annotations

import json
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
BROKER_SKILL = REPO_ROOT / "skills" / "spec-driven-tdd" / "SKILL-ORCHESTRATOR.md"


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


def _git_show(repo_path: str, ref: str, file_path: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", repo_path, "show", f"{ref}:{file_path}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _broker_log_path(repo_path: str) -> Path:
    return Path(repo_path) / ".git" / "sddtdd" / "broker-access.jsonl"


def _append_broker_event(repo_path: str, event: dict[str, Any]) -> None:
    path = _broker_log_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _verified_task_ids(repo_path: str) -> set[str]:
    path = _broker_log_path(repo_path)
    if not path.exists():
        return set()
    verified: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "task_verified" and event.get("status") == "PASS" and event.get("task_id"):
            verified.add(str(event["task_id"]))
    return verified


def _verify_next_task_gate(repo_path: str, previous_task_id: str | None) -> dict[str, Any] | None:
    if not previous_task_id:
        return {
            "status": "BLOCKED",
            "summary": "next_task requires previous_task_id from a broker task that passed verify_task",
            "required_action": "Call verify_task for the current broker task and pass its task_id as previous_task_id",
        }
    if previous_task_id not in _verified_task_ids(repo_path):
        return {
            "status": "BLOCKED",
            "summary": f"Task {previous_task_id} has not passed broker verify_task",
            "required_action": "Complete the assigned task and obtain verify_task PASS before asking for next_task",
        }
    return None


def _candidate_evidence_paths(journal: str | None, explicit: list[str] | None = None) -> list[str]:
    """Extract conservative repo-relative evidence path candidates.

    The journal DETAIL field is free text, so this intentionally recognizes only
    path-like tokens. The broker receives these file contents as evidence context
    but still decides whether they are sufficient.
    """
    candidates: list[str] = []
    for source in [*(explicit or []), *(journal or "").replace("`", " ").split()]:
        token = source.strip().strip(",.;:()[]{}<>\"'")
        if not token or token.startswith("/") or ".." in Path(token).parts:
            continue
        if "/" in token or token.endswith((".md", ".log", ".txt", ".json", ".jsonl", ".xml", ".yaml", ".yml")):
            candidates.append(token)
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


def capture_repo_state(repo_path: str, explicit_evidence: list[str] | None = None) -> dict[str, Any]:
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

    core_files = [
        "JOURNAL_SDD_TDD_SKILL.log",
        "SPEC-DRAFT.md",
        "SPEC.md",
        "ARCHITECTURE.md",
        "TASKS.md",
    ]
    head_sha = state["head_sha"]
    for name in core_files:
        state["files"][name] = _git_show(str(path), head_sha, name)

    state["evidence_files"] = {}
    journal = state["files"].get("JOURNAL_SDD_TDD_SKILL.log")
    for name in _candidate_evidence_paths(journal, explicit_evidence):
        if name in core_files:
            continue
        content = _git_show(str(path), head_sha, name)
        if content is not None:
            state["evidence_files"][name] = content

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
        "# Orchestrator role: spec-driven-tdd/SKILL-ORCHESTRATOR.md",
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
            inputSchema=_tool_schema(["repo_path", "previous_task_id"]),
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name not in {"init_task", "verify_task", "next_task"}:
        raise ValueError(f"Unknown tool: {name}")

    request_id = uuid.uuid4().hex
    try:
        repo_path = str(Path(arguments["repo_path"]).resolve())
        if name == "next_task":
            blocked = _verify_next_task_gate(repo_path, arguments.get("previous_task_id"))
            if blocked is not None:
                blocked["request_id"] = request_id
                return [types.TextContent(type="text", text=json.dumps(blocked, ensure_ascii=False, indent=2))]

        explicit_evidence = arguments.get("evidence") if isinstance(arguments.get("evidence"), list) else None
        repo_state = capture_repo_state(repo_path, explicit_evidence)
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
        if name == "verify_task" and result.get("status") == "PASS" and arguments.get("task_id"):
            _append_broker_event(repo_path, {
                "event": "task_verified",
                "request_id": request_id,
                "task_id": arguments.get("task_id"),
                "status": "PASS",
                "repo_head": repo_state["head_sha"],
            })
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
