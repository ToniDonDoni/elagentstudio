"""sddtdd-broker-mcp — MCP task broker for Spec-Driven TDD.

The server exposes a two-step broker contract around two decision tools:
``getNextTask`` and ``reviewTask``. An ``init`` tool is also provided for
explicit start/resume of brokered work. The broker reads the committed
repository state, the SDDTDD journal, and the shared process skill plus the
in-folder orchestrator role file, then samples the LLM to make the decision.

The orchestrator role file is the source of truth for the workflow order,
the review rules, and the broker-level task verification policy. The
implementer only needs to know the two decision tools and the three
self-contained task fields (``instruction``, ``allowed_scope``,
``required_evidence``, ``independent_review_required``, ``review_type``).
The implementer does not pass role files to the broker on every call: the
broker is configured at startup with the paths to the process skill and the
orchestrator role file.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import mcp.server as mcp_server
import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server


app = mcp_server.Server("sddtdd-broker-mcp")

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROCESS_SKILL = REPO_ROOT / "skills" / "spec-driven-tdd" / "SKILL.md"
DEFAULT_ORCHESTRATOR_ROLE = REPO_ROOT / "skills" / "spec-driven-tdd" / "SKILL-ORCHESTRATOR.md"
DEFAULT_STAGES_REF = REPO_ROOT / "skills" / "spec-driven-tdd" / "references" / "STAGES.md"


def _configured_path(env_var: str, default: Path) -> Path:
    value = os.environ.get(env_var)
    if value:
        return Path(value).expanduser().resolve()
    return default


PROCESS_SKILL = _configured_path("SDDTDD_BROKER_PROCESS_SKILL", DEFAULT_PROCESS_SKILL)
ORCHESTRATOR_ROLE = _configured_path("SDDTDD_BROKER_ORCHESTRATOR_ROLE", DEFAULT_ORCHESTRATOR_ROLE)
STAGES_REF = _configured_path("SDDTDD_BROKER_STAGES_REF", DEFAULT_STAGES_REF)

BROKER_TOOLS = {"init", "getNextTask", "reviewTask"}


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


def _read_skill(path: Path) -> str:
    if not path.exists():
        return f"MISSING SKILL: {path}"
    return path.read_text(errors="replace")


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


def build_broker_prompt(tool_name: str, arguments: dict[str, Any], repo_state: dict[str, Any]) -> str:
    return "\n".join([
        "# Role",
        "You are the SDDTDD MCP task broker/orchestrator. Read the process skill and the orchestrator role below. Apply the broker-level task verification policy from the orchestrator role. Return JSON only. Do not implement, edit files, run tests, or perform the independent artifact review that belongs to mcp_sddtdd_review_review.",
        "",
        "# Tool call",
        json.dumps({"tool": tool_name, "arguments": arguments}, ensure_ascii=False, indent=2),
        "",
        f"# Process skill: {PROCESS_SKILL.name}",
        _read_skill(PROCESS_SKILL),
        "",
        f"# Orchestrator role: {ORCHESTRATOR_ROLE.name}",
        _read_skill(ORCHESTRATOR_ROLE),
        "",
        f"# Stage procedure (for context): {STAGES_REF.name}",
        _read_skill(STAGES_REF),
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


def _init_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Absolute path to the Git repository"},
            "user_input": {"type": "string", "description": "Original user request or pointer to it"},
        },
        "required": ["repo_path", "user_input"],
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
        },
        "required": ["repo_path"],
    }


def _review_task_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Absolute path to the Git repository"},
            "task_id": {"type": "string", "description": "Broker-assigned task id being verified"},
            "claimed_result": {"type": "string", "description": "Implementer completion summary"},
            "evidence": {
                "type": "object",
                "description": "Concrete evidence supporting completion",
                "properties": {
                    "commits": {"type": "array", "items": {"type": "string"}},
                    "journal_ids": {"type": "array", "items": {"type": "string"}},
                    "review_request_id": {"type": "string"},
                    "test_commands": {"type": "array", "items": {"type": "string"}},
                    "files": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "required": ["repo_path", "task_id", "claimed_result"],
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
            description="Ask the orchestrator to verify that the current task is genuinely complete (semantic broker-level task verification)",
            inputSchema=_review_task_schema(),
        ),
    ]


def _normalize_evidence(arguments: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    raw = arguments.get("evidence")
    explicit: list[str] = []
    if isinstance(raw, dict):
        for files in (raw.get("files") or []):
            if isinstance(files, str):
                explicit.append(files)
        for commits in (raw.get("commits") or []):
            if isinstance(commits, str):
                explicit.append(commits)
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                explicit.append(item)
    return explicit, raw if isinstance(raw, dict) else {}


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name not in BROKER_TOOLS:
        raise ValueError(f"Unknown tool: {name}")

    request_id = uuid.uuid4().hex
    started_at = time.monotonic()

    repo_path = str(Path(arguments["repo_path"]).resolve())
    explicit_evidence, evidence_obj = _normalize_evidence(arguments)
    task_id = arguments.get("task_id") if name == "reviewTask" else arguments.get("previous_task_id")

    head_sha_before = ""
    try:
        head_sha_before = _git(repo_path, "rev-parse", "HEAD")
    except Exception:
        pass

    # Log task_review_started for every reviewTask call.
    if name == "reviewTask":
        _append_broker_event(repo_path, {
            "event": "task_review_started",
            "request_id": request_id,
            "task_id": task_id,
            "head_sha_before": head_sha_before,
            "evidence": evidence_obj or arguments.get("evidence"),
        })

    try:
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
    except Exception as exc:
        result = {
            "request_id": request_id,
            "status": "ERROR",
            "summary": str(exc),
        }

    head_sha_after = ""
    try:
        head_sha_after = _git(repo_path, "rev-parse", "HEAD")
    except Exception:
        pass
    duration_ms = int((time.monotonic() - started_at) * 1000)

    if name == "reviewTask":
        verdict = result.get("status", "ERROR")
        if verdict not in {"PASS", "FAIL", "NEEDS_CLARIFICATION", "ERROR"}:
            verdict = "ERROR"
        _append_broker_event(repo_path, {
            "event": "task_review_completed",
            "request_id": request_id,
            "task_id": task_id,
            "head_sha_before": head_sha_before,
            "head_sha_after": head_sha_after,
            "status": verdict,
            "findings": result.get("findings", []),
            "summary": result.get("summary"),
            "duration_ms": duration_ms,
        })

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="sddtdd-broker-mcp",
                server_version="2.0.0",
                capabilities=types.ServerCapabilities(),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
