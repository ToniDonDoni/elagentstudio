"""sddtdd-broker-mcp — MCP task broker for Spec-Driven TDD.

The server exposes a two-step broker contract around two decision tools:
``getNextTask`` and ``reviewTask``. An ``init`` tool is also provided for
explicit start/resume of brokered work. The broker reads the committed
repository state, the SDDTDD journal, and the shared process skill plus the
in-folder orchestrator role file, then samples the LLM to make the decision.

The orchestrator role file is the source of truth for the workflow order and
review rules. The implementer only needs to know the two decision tools.

The implementer tells the broker who it is on every call: it passes the
``process_skill``, ``implementer_skill``, ``broker_skill`` file paths and a
plain ``instruction`` such as "Read the broker skill I gave you. You are the
broker." The broker loads the files the implementer names and uses them to
decide.
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

# Fallback skill paths used only when the implementer does not pass
# ``process_skill`` / ``broker_skill``. Real calls always pass them.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROCESS_SKILL = REPO_ROOT / "skills" / "spec-driven-tdd" / "SKILL.md"
DEFAULT_ORCHESTRATOR_ROLE = REPO_ROOT / "skills" / "spec-driven-tdd" / "SKILL-ORCHESTRATOR.md"

BROKER_TOOLS = {"init", "getNextTask", "reviewTask"}

DEFAULT_INSTRUCTION = (
    "Read the broker skill I gave you. You are the broker. "
    "Act according to it. Use the spec-driven-tdd process skill and this "
    "orchestrator role file to decide. Do not implement, review, or edit files."
)


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


def _verify_get_next_task_gate(repo_path: str, previous_task_id: str | None) -> dict[str, Any] | None:
    """Block getNextTask if the previous broker task has not been reviewTask-PASSed."""
    if previous_task_id is None:
        return None
    if previous_task_id in _verified_task_ids(repo_path):
        return None
    return {
        "status": "blocked",
        "summary": f"Task {previous_task_id} has not passed broker reviewTask",
        "required_action": "Complete the assigned task and obtain reviewTask PASS before asking for the next task",
    }


def _candidate_evidence_paths(journal: str | None, explicit: list[str] | None = None) -> list[str]:
    """Extract conservative repo-relative evidence path candidates.

    The journal DETAIL field is free text, so this intentionally recognizes only
    path-like tokens. The orchestrator receives these file contents as evidence
    context but still decides whether they are sufficient.
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


def _resolve_skill_path(repo_root: Path, requested: str | None, default: Path) -> Path:
    """Resolve a skill path provided by the implementer against the repo root.

    Relative paths are taken as repo-relative. Absolute paths must point inside
    the repository. Missing files raise ``FileNotFoundError``.
    """
    if not requested:
        return default
    candidate = Path(requested)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"skill file does not exist: {candidate}")
    return candidate


def build_broker_prompt(
    tool_name: str,
    arguments: dict[str, Any],
    repo_state: dict[str, Any],
    process_skill_path: Path,
    broker_skill_path: Path,
    implementer_skill_path: Path,
    instruction: str,
) -> str:
    return "\n".join([
        "# Implementer instruction (read first)",
        instruction.strip(),
        "",
        "# Role assignment",
        json.dumps({
            "role": "broker/orchestrator",
            "process_skill": str(process_skill_path),
            "broker_skill": str(broker_skill_path),
            "implementer_skill": str(implementer_skill_path),
        }, ensure_ascii=False, indent=2),
        "",
        "# How to act",
        (
            "You are the SDDTDD MCP task broker/orchestrator. "
            "Return JSON only. Do not implement, edit files, run tests, or review artifacts. "
            "Use the orchestrator role file to decide the workflow order and review rules. "
            "The implementer must not be exposed to the internal stage type."
        ),
        "",
        "# Tool call",
        json.dumps({"tool": tool_name, "arguments": arguments}, ensure_ascii=False, indent=2),
        "",
        f"# Process skill: {process_skill_path.name}",
        _read_skill(process_skill_path),
        "",
        f"# Broker/Orchestrator role: {broker_skill_path.name}",
        _read_skill(broker_skill_path),
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
        return {
            "status": "ERROR",
            "summary": "Broker sampling response was not valid JSON",
            "raw_response": text,
        }
    if not isinstance(data, dict):
        return {"status": "ERROR", "summary": "Broker response was not a JSON object", "raw_response": text}
    return data


def _skill_pointer_properties() -> dict[str, Any]:
    return {
        "process_skill": {
            "type": "string",
            "description": (
                "Path to the shared process skill the implementer wants the broker to use "
                "(e.g. 'spec-driven-tdd' or 'skills/spec-driven-tdd/SKILL.md')"
            ),
        },
        "implementer_skill": {
            "type": "string",
            "description": "Path to the implementer role file (skills/spec-driven-tdd/SKILL-IMPLEMENTER.md)",
        },
        "broker_skill": {
            "type": "string",
            "description": (
                "Path to the broker/orchestrator role file the implementer wants the broker to act as "
                "(skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md). The broker loads this file and applies its decision policy."
            ),
        },
        "instruction": {
            "type": "string",
            "description": (
                "Plain natural-language instruction from the implementer. The implementer tells the broker: "
                "'Read the broker skill I gave you. You are the broker. Act according to it.'"
            ),
        },
    }


def _init_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Absolute path to the Git repository"},
            "user_input": {"type": "string", "description": "Original user request or pointer to it"},
            **_skill_pointer_properties(),
        },
        "required": ["repo_path", "user_input", "process_skill", "implementer_skill", "broker_skill", "instruction"],
    }


def _get_next_task_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Absolute path to the Git repository"},
            "previous_task_id": {
                "type": "string",
                "description": "Task id returned by a previous getNextTask that passed reviewTask; omit on first call",
            },
            **_skill_pointer_properties(),
        },
        "required": ["repo_path", "process_skill", "implementer_skill", "broker_skill", "instruction"],
    }


def _review_task_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Absolute path to the Git repository"},
            "task_id": {"type": "string", "description": "Broker-assigned task id being verified"},
            "claimed_result": {"type": "string", "description": "Implementer completion summary"},
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Commit hashes, journal entries, test commands, review request ids",
            },
            **_skill_pointer_properties(),
        },
        "required": [
            "repo_path",
            "task_id",
            "claimed_result",
            "process_skill",
            "implementer_skill",
            "broker_skill",
            "instruction",
        ],
    }


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="init",
            description="Start or resume brokered Spec-Driven TDD work for a repository",
            inputSchema=_init_schema(),
        ),
        types.Tool(
            name="getNextTask",
            description="Ask the orchestrator for the next task, or for 'complete' / 'blocked'",
            inputSchema=_get_next_task_schema(),
        ),
        types.Tool(
            name="reviewTask",
            description="Ask the orchestrator to verify that the current task is genuinely complete",
            inputSchema=_review_task_schema(),
        ),
    ]


def _missing_skill_pointers(arguments: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in ("process_skill", "implementer_skill", "broker_skill", "instruction"):
        value = arguments.get(field)
        if not value or not isinstance(value, str) or not value.strip():
            missing.append(field)
    return missing


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name not in BROKER_TOOLS:
        raise ValueError(f"Unknown tool: {name}")

    request_id = uuid.uuid4().hex
    try:
        missing_pointers = _missing_skill_pointers(arguments)
        if missing_pointers:
            result = {
                "request_id": request_id,
                "status": "ERROR",
                "summary": (
                    "Implementer did not tell the broker who it is. "
                    f"Missing required fields: {', '.join(missing_pointers)}. "
                    "The implementer must pass process_skill, implementer_skill, broker_skill, and an instruction such as: "
                    "'Read the broker skill I gave you. You are the broker.'"
                ),
            }
            return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        repo_path = str(Path(arguments["repo_path"]).resolve())
        repo_root = Path(repo_path)

        process_skill_path = _resolve_skill_path(repo_root, arguments.get("process_skill"), DEFAULT_PROCESS_SKILL)
        implementer_skill_path = _resolve_skill_path(repo_root, arguments.get("implementer_skill"), DEFAULT_PROCESS_SKILL.parent / "SKILL-IMPLEMENTER.md")
        broker_skill_path = _resolve_skill_path(repo_root, arguments.get("broker_skill"), DEFAULT_ORCHESTRATOR_ROLE)
        instruction = arguments.get("instruction") or DEFAULT_INSTRUCTION

        if name == "getNextTask":
            blocked = _verify_get_next_task_gate(repo_path, arguments.get("previous_task_id"))
            if blocked is not None:
                blocked["request_id"] = request_id
                return [types.TextContent(type="text", text=json.dumps(blocked, ensure_ascii=False, indent=2))]

        explicit_evidence = arguments.get("evidence") if isinstance(arguments.get("evidence"), list) else None
        repo_state = capture_repo_state(repo_path, explicit_evidence)
        prompt = build_broker_prompt(
            name,
            arguments,
            repo_state,
            process_skill_path,
            broker_skill_path,
            implementer_skill_path,
            instruction,
        )
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
        if name == "reviewTask" and result.get("status") == "PASS" and arguments.get("task_id"):
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
                server_version="1.2.0",
                capabilities=types.ServerCapabilities(),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
