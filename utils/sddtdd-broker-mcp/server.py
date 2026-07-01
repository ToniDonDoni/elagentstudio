"""sddtdd-broker-mcp — LLM-based MCP task broker for Spec-Driven TDD.

Two tools:
  * getNextTask — inspect committed repo state and issue the next self-contained task.
  * reviewTask — verify that the issued task is process-complete.

The broker is deliberately read-only: it never edits repository files, never
writes the SDDTDD journal, never commits, and never performs independent artifact
review. It only orchestrates the next task and checks process-gate state.
"""
from __future__ import annotations

import json
import logging
import os
import re
import signal
import shlex
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mcp.server as mcp_server
import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("sddtdd-broker-mcp")
logging.basicConfig(
    level=logging.DEBUG,
    force=True,
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVER_NAME = "sddtdd-broker-mcp"
SERVER_VERSION = "1.0.0"
DEFAULT_SKILL_ROOT = Path.home() / ".hermes" / "skills" / "spec-driven-tdd"
MAX_TOOL_OUTPUT_CHARS = int(os.environ.get("SDDTDD_BROKER_TOOL_OUTPUT_CHARS", "200000"))
MAX_SAMPLING_ROUNDS = int(os.environ.get("SDDTDD_BROKER_MAX_SAMPLING_ROUNDS", "5555"))
MAX_SAMPLING_TOKENS = int(os.environ.get("SDDTDD_BROKER_MAX_SAMPLING_TOKENS", "128000"))
MAX_JSON_REPAIR_ATTEMPTS = int(os.environ.get("SDDTDD_BROKER_JSON_REPAIR_ATTEMPTS", "21"))
MAX_MAXTOKEN_CONTINUES = int(os.environ.get("SDDTDD_BROKER_MAXTOKEN_CONTINUES", "6"))
JSON_ERROR_PREFIX_CHARS = 300

READ_ONLY_DENY_RE = re.compile(
    r"""
    (^|[;&|`$()<>])\s*(
        rm|rmdir|mv|cp|touch|mkdir|chmod|chown|truncate|tee|sed\s+-i|perl\s+-i|
        python\b|python3\b|node\b|ruby\b|bash\b|sh\b|zsh\b|fish\b|
        git\s+(add|commit|reset|checkout|switch|restore|merge|rebase|cherry-pick|am|apply|clean|stash|tag|branch\s+-D)|
        npm\s+(install|ci|run)|pnpm\s+|yarn\s+|pip\s+|poetry\s+|cargo\s+|go\s+|
        make\s+|cmake\s+|ninja\s+
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Errors and helpers
# ---------------------------------------------------------------------------

class GitError(Exception):
    """Raised when a git command fails."""


class BrokerError(Exception):
    """Raised for broker-local validation or sampling errors."""


class GitCapturer:
    """Read repository metadata through git CLI."""

    def __init__(self, repo_path: str):
        self.repo_path = str(Path(repo_path).resolve())

    def git(self, *args: str, timeout: int = 15) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", self.repo_path, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise GitError("git not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {' '.join(args)} timed out") from exc
        if result.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def branch(self) -> str:
        return self.git("rev-parse", "--abbrev-ref", "HEAD")

    def head_sha(self) -> str:
        return self.git("rev-parse", "HEAD")

    def is_dirty(self) -> bool:
        return bool(self.git("status", "--porcelain"))


class LogWriter:
    """Append-only JSON Lines broker access log."""

    def __init__(self, log_path: str):
        self.path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._file = open(log_path, "a", buffering=1, encoding="utf-8")

    def append(self, event: dict[str, Any]) -> None:
        self._file.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _get_log_path(repo_path: str) -> str:
    env = os.environ.get("SDDTDD_BROKER_LOG_PATH")
    if env:
        return env
    return str(Path(repo_path) / ".sddtdd_skill" / "broker-access.jsonl")


def _resolve_repo_path(repo_path: str) -> Path:
    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists():
        raise BrokerError(f"repo_path does not exist: {repo}")
    if not (repo / ".git").exists():
        # Worktrees can lack .git directory but have a .git file.
        if not (repo / ".git").is_file():
            raise BrokerError(f"repo_path is not a Git repository root: {repo}")
    return repo


def _resolve_path(repo_path: str, raw: str) -> Path:
    repo = Path(repo_path).resolve()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = repo / p
    p = p.resolve()
    if p != repo and repo not in p.parents:
        raise ValueError(f"path escapes repository: {raw}")
    return p



def _trim(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    original_len = len(text)
    if original_len > limit:
        return (
            text[:limit]
            + "\n\n[TOOL_OUTPUT_TRUNCATED]\n"
            + f"Returned chars: {limit}\n"
            + f"Original chars: {original_len}\n"
            + "The command output exceeded the tool output limit. "
            + "The omitted content was not reviewed unless another command reads it explicitly.\n"
            + "Run a narrower command to inspect the missing content."
        )
    return text



def _safe_log_text(value: object, limit: int = 300) -> str:
    """Return ASCII-only text safe for stderr logs.

    MCP stderr logs are later searched with grep. Never write raw sampled
    text into them: model/tool arguments can contain control bytes, ANSI
    escapes, or other non-printable characters that make grep treat the log
    as binary. Use unicode_escape so NUL becomes `\\x00` text instead of a
    real NUL byte.
    """
    text = str(value)
    if len(text) > limit:
        text = text[:limit] + f"... ({len(text)} chars total)"
    return text.encode("unicode_escape", "backslashreplace").decode("ascii")


def _cleanup_process_groups(process_groups: list[int], leaked_pids: list[int]) -> None:
    """Terminate broker shell_command groups and observed leftover PIDs.

    Broker shell_command starts each command in a new session, so the command's
    initial PID is also its process group id. Group cleanup is the normal path
    for child trees such as npm -> sh -> vite -> esbuild.

    The leaked_pids list is a fallback for concrete PIDs observed after a command
    returned. It is useful if a child survives, gets reparented, or escapes the
    original group/session before final MCP cleanup; killpg(pgid) may miss that,
    but the exact PID can still be terminated directly.
    """
    pgids = sorted(set(process_groups))
    pids = sorted(set(leaked_pids))
    if not pgids and not pids:
        return

    for pgid in pgids:
        try:
            os.killpg(pgid, signal.SIGTERM)
            logger.info("cleanup: sent SIGTERM to process group pgid=%d", pgid)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("cleanup: SIGTERM failed pgid=%d error=%s", pgid, exc)

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("cleanup: sent SIGTERM to leaked pid=%d", pid)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("cleanup: SIGTERM failed leaked pid=%d error=%s", pid, exc)

    time.sleep(1)

    for pgid in pgids:
        try:
            os.killpg(pgid, signal.SIGKILL)
            logger.info("cleanup: sent SIGKILL to process group pgid=%d", pgid)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("cleanup: SIGKILL failed pgid=%d error=%s", pgid, exc)

    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
            logger.info("cleanup: sent SIGKILL to leaked pid=%d", pid)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("cleanup: SIGKILL failed leaked pid=%d error=%s", pid, exc)


def _process_group_pids(pgid: int) -> list[int]:
    """Return live process IDs that still belong to a process group."""
    pids: list[int] = []
    proc = Path("/proc")
    if not proc.exists():
        return pids

    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(errors="replace")
            # /proc/<pid>/stat is: pid (comm) state ppid pgrp session ...
            # `comm` may contain spaces, so split after the final ") " first.
            # After that split, fields[0]=state, fields[1]=ppid, fields[2]=pgrp.
            after_comm = stat.rsplit(") ", 1)[1]
            fields = after_comm.split()
            process_pgid = int(fields[2])
        except Exception:
            continue
        if process_pgid == pgid:
            pids.append(int(entry.name))

    return sorted(pids)


def _extract_first_json_object(text: str) -> dict[str, Any]:
    """Extract the first balanced JSON object from an LLM response."""
    stripped = text.strip()
    response_prefix = stripped[:JSON_ERROR_PREFIX_CHARS]
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start < 0:
        raise BrokerError(
            "LLM response did not contain JSON object; "
            f"response_len={len(stripped)} response_prefix={response_prefix!r}"
        )

    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(stripped[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start:i + 1]
                parsed = json.loads(candidate)
                if not isinstance(parsed, dict):
                    raise BrokerError("LLM JSON response was not an object")
                return parsed
    raise BrokerError(
        "LLM response contained incomplete JSON object; "
        f"response_len={len(stripped)} response_prefix={response_prefix!r}"
    )


def _read_skill_file(relative_path: str) -> str:
    root = Path(os.environ.get("SDDTDD_SKILL_ROOT", str(DEFAULT_SKILL_ROOT))).expanduser()
    path = (root / relative_path).resolve()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return f"[MISSING: {path}]"
    return _trim(text, 20000)


# ---------------------------------------------------------------------------
# MCP app and schemas
# ---------------------------------------------------------------------------

app = mcp_server.Server(SERVER_NAME)


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="getNextTask",
            description=(
                "Inspect committed SDDTDD repository state and issue exactly one "
                "self-contained next broker task, or return complete/blocked. The "
                "broker is read-only and does not modify the repository."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Absolute path to the Git repository.",
                    },
                    "user_input": {
                        "type": "string",
                        "description": (
                            "Original user request. Required only for the first "
                            "broker call of a delivery."
                        ),
                    },
                    "previous_task_id": {
                        "type": "string",
                        "description": "Broker task id that was just completed, e.g. B-000003.",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        types.Tool(
            name="reviewTask",
            description=(
                "Verify that one issued broker task is process-complete. This is "
                "not semantic artifact review; it checks journal, commit, reviewer "
                "verdict chain, and broker-task gate evidence."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string"},
                    "task_id": {"type": "string", "description": "Broker task id, e.g. B-000003."},
                    "task_kind": {"type": "string"},
                    "review_type": {
                        "type": ["string", "null"],
                        "description": "Expected independent reviewer entry type, or null.",
                    },
                    "claimed_result": {
                        "type": "string",
                        "description": "Implementer's concise claim of what was completed.",
                    },
                    "work_journal_id": {
                        "type": "string",
                        "description": "JID of the work entry for this broker task.",
                    },
                    "evidence": {
                        "type": "object",
                        "description": (
                            "Concrete evidence. Use evidence.review_journal_id when "
                            "independent_review_required was true. Include commit hashes, "
                            "commands, file paths, and reviewer request ids when available."
                        ),
                        "additionalProperties": True,
                    },
                },
                "required": [
                    "repo_path",
                    "task_id",
                    "task_kind",
                    "claimed_result",
                    "work_journal_id",
                    "evidence",
                ],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Sampling tools available to the broker LLM
# ---------------------------------------------------------------------------

BROKER_TOOLS: list[types.Tool] = [
    types.Tool(
        name="shell_command",
        description=(
            "Run a read-only shell command in the repository for inspection only: "
            "git status, git log/show/diff/ls-files, grep, find, ls, cat, wc, head, "
            "tail. Mutating commands are rejected. Output is truncated."
        ),
        inputSchema={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    ),
]


def _execute_broker_tool(
    name: str,
    args: dict[str, Any],
    repo_path: str,
    process_groups: list[int],
    leaked_pids: list[int],
) -> str:
    if name == "shell_command":
        cmd = str(args.get("command", "")).strip()
        if not cmd:
            return "ERROR: empty command"
        if READ_ONLY_DENY_RE.search(cmd):
            return "ERROR: command rejected by read-only broker policy"
        try:
            # shlex.split catches obvious malformed quoting before shell=True.
            shlex.split(cmd)
            process = subprocess.Popen(
                cmd,
                shell=True,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            process_groups.append(process.pid)
            try:
                stdout, stderr = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate()
                output = (stdout or "") + (stderr or "")
                output += (
                    "\n\n[TOOL_COMMAND_TIMED_OUT]\n"
                    "Timeout seconds: 30\n"
                    "The command exceeded the broker shell command timeout and its process group was terminated."
                )
            else:
                output = (stdout or "") + (stderr or "")

            leftover_pids = _process_group_pids(process.pid)
            if leftover_pids:
                leaked_pids.extend(leftover_pids)
                logger.warning(
                    "PROCESS_LEAK_DETECTED: broker shell_command returned with live process group members pgid=%d pids=%s",
                    process.pid,
                    ", ".join(str(pid) for pid in leftover_pids),
                )

            if not output:
                output = f"(no output, exit={process.returncode})"
            return _trim(output)
        except ValueError as exc:
            return f"ERROR: invalid command: {exc}"
        except Exception as exc:
            return f"ERROR: {exc}"

    return f"ERROR: unknown tool: {name}"


# ---------------------------------------------------------------------------
# Broker prompts
# ---------------------------------------------------------------------------

SYSTEM_PROJECT = """
You are the Spec-Driven TDD MCP task broker for a repository.

You are a read-only broker/orchestrator. You MUST NOT modify files, write the
journal, change the working tree, stage files, commit, run formatters, or alter
repository state. You only inspect committed repository state and runtime broker
logs, then return either the next self-contained task or a process-gate verdict.

You MUST reference and apply the installed skill files:
- ~/.hermes/skills/spec-driven-tdd/SKILL.md
- ~/.hermes/skills/spec-driven-tdd/SKILL-IMPLEMENTER.md
- ~/.hermes/skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md
- ~/.hermes/skills/spec-driven-tdd/references/JOURNAL.md
- ~/.hermes/skills/spec-driven-tdd/references/STAGES.md

The implementer does not read SKILL-ORCHESTRATOR.md or references/STAGES.md in
broker mode. You, the broker, own the workflow order and issue exactly one next
task. The implementer only receives your task and must not cut corners.

You are NOT the independent reviewer. The reviewer MCP performs semantic
artifact review and records SPEC_REVIEW, ARCHITECTURE_REVIEW, TASK_REVIEW,
RED_REVIEW, GREEN_REVIEW, REGRESSION_REVIEW, and FINAL_REVIEW. You only verify
process completion and decide the next task from committed state, journal state,
and broker/reviewer evidence.

Return JSON only. Do not wrap it in Markdown.
""".strip()

GET_NEXT_SCHEMA = """
For getNextTask, return exactly one JSON object in one of these shapes:

Task response:
{
  "status": "task",
  "task_id": "B-000001",
  "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
  "instruction": "one concrete instruction in English",
  "allowed_scope": ["exact repo paths or artifact globs the implementer may touch"],
  "required_evidence": ["concrete required evidence the implementer must produce"],
  "independent_review_required": true,
  "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
  "rationale": "brief process reason for this task"
}

Blocked response:
{
  "status": "blocked",
  "reason": "why no next task can be issued",
  "unverified_task_ids": ["B-000003"],
  "required_action": "Call reviewTask for the outstanding broker task before getNextTask."
}

Clarification response:
{
  "status": "needs_clarification",
  "question": "question for the implementer/user",
  "rationale": "why this is required before issuing a task"
}

Complete response:
{
  "status": "complete",
  "rationale": "why the workflow is complete"
}

Rules:
- Issue only one task.
- Use monotonically increasing broker task ids B-000001, B-000002, etc. Infer the next id from broker-access.jsonl and journal evidence.
- If a previous broker task lacks a committed BROKER_TASK_REVIEW with STATUS: PASS and TASK_ID equal to that broker task id, return blocked.
- The first task for a fresh delivery is USER_INPUT_CAPTURE and must preserve the user's input exactly in .sddtdd_skill/SPEC-DRAFT.md plus create the USER_INPUT journal entry.
- For agent-generated artifacts, require independent reviewer verdict before broker PASS.
- Architecture is a mandatory stage between SPEC_REVIEW PASS and DECOMPOSE.
- Do not let implementation begin before TASK_REVIEW PASS.
- Do not allow GREEN before RED_REVIEW PASS for that task.
- Do not allow final completion before regression review PASS and final review PASS.
- Instructions must be in English and self-contained; the implementer should not need to know the workflow order.
""".strip()

REVIEW_TASK_SCHEMA = """
For reviewTask, return exactly one JSON object:
{
  "status": "PASS | FAIL | NEEDS_CLARIFICATION | ERROR",
  "findings": ["specific process findings"],
  "required_fixes": ["specific required fixes before retry; empty on PASS"],
  "parent_for_broker_review": "JID that BROKER_TASK_REVIEW should point to",
  "detail_suggestion": "English DETAIL text the implementer may paste into BROKER_TASK_REVIEW",
  "rationale": "brief explanation"
}

Process gate rules:
- Check only process completeness, not semantic artifact quality.
- Verify the work_journal_id exists in .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log.
- Verify the work entry TYPE matches task_kind's journal stage and STATUS is COMPLETED.
- If review_type is non-null, verify evidence.review_journal_id exists, has TYPE equal to review_type, STATUS: PASS, and PARENT equal to work_journal_id.
- If review_type is null, parent_for_broker_review must be work_journal_id.
- Verify the relevant artifacts/evidence are committed at HEAD where possible.
- Verify the repository did not advance during your review; stale state must be ERROR.
- On PASS, parent_for_broker_review is the reviewer verdict JID, or work_journal_id for capture tasks.
- Do not require BROKER_TASK_REVIEW to already exist for the task being reviewed; the implementer writes it after your PASS/FAIL response.
""".strip()


def _base_repo_context(repo_path: str, git: GitCapturer) -> dict[str, Any]:
    return {
        "repo_path": repo_path,
        "branch": git.branch(),
        "head_sha": git.head_sha(),
        "working_tree_dirty": git.is_dirty(),
        "important_paths": {
            "skill_root": str(Path(os.environ.get("SDDTDD_SKILL_ROOT", str(DEFAULT_SKILL_ROOT))).expanduser()),
            "working_area": ".sddtdd_skill/",
            "journal": ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log",
            "review_log": ".sddtdd_skill/review-access.jsonl",
            "broker_log": ".sddtdd_skill/broker-access.jsonl",
        },
    }


def _get_next_prompt(repo_path: str, git: GitCapturer, args: dict[str, Any]) -> str:
    payload = {
        "operation": "getNextTask",
        "repo": _base_repo_context(repo_path, git),
        "user_input": args.get("user_input"),
        "previous_task_id": args.get("previous_task_id"),
    }
    return (
        SYSTEM_PROJECT
        + "\n\n"
        + GET_NEXT_SCHEMA
        + "\n\nInspect the repository using tools before deciding. Read the skill files listed above as needed. "
          "Return JSON only.\n\nREQUEST:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _review_task_prompt(repo_path: str, git: GitCapturer, args: dict[str, Any]) -> str:
    payload = {
        "operation": "reviewTask",
        "repo": _base_repo_context(repo_path, git),
        "task_id": args.get("task_id"),
        "task_kind": args.get("task_kind"),
        "review_type": args.get("review_type"),
        "claimed_result": args.get("claimed_result"),
        "work_journal_id": args.get("work_journal_id"),
        "evidence": args.get("evidence", {}),
    }
    return (
        SYSTEM_PROJECT
        + "\n\n"
        + REVIEW_TASK_SCHEMA
        + "\n\nInspect the committed repository and journal using tools before giving a verdict. "
          "Return JSON only.\n\nREQUEST:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


# ---------------------------------------------------------------------------
# JSON schema helper for repair
# ---------------------------------------------------------------------------
def _expected_json_schema_for_operation(operation: str) -> str:
    if operation == "getNextTask":
        return GET_NEXT_SCHEMA
    if operation == "reviewTask":
        return REVIEW_TASK_SCHEMA
    return "Return one valid JSON object."


# ---------------------------------------------------------------------------
# Sampling loop
# ---------------------------------------------------------------------------

async def _sample_with_tools(
    ctx: Any,
    initial_prompt: str,
    repo_path: str,
    process_groups: list[int],
    leaked_pids: list[int],
) -> tuple[str, str]:
    messages: list[types.SamplingMessage] = [
        types.SamplingMessage(
            role="user",
            content=types.TextContent(type="text", text=initial_prompt),
        )
    ]

    last_text = ""
    max_token_continues = 0
    for round_no in range(1, MAX_SAMPLING_ROUNDS + 1):
        logger.info("sampling round %d/%d messages=%d", round_no, MAX_SAMPLING_ROUNDS, len(messages))
        result = await ctx.session.create_message(
            messages=messages,
            max_tokens=MAX_SAMPLING_TOKENS,
            tools=BROKER_TOOLS,
        )

        blocks = result.content if isinstance(result.content, list) else [result.content]
        for block in blocks:
            if isinstance(block, types.TextContent):
                last_text = block.text

        stop_reason = getattr(result, "stopReason", None) or "endTurn"
        logger.info(
            "sampling stop_reason=%s text_len=%d requested_max_tokens=%d",
            stop_reason,
            len(last_text),
            MAX_SAMPLING_TOKENS,
        )
        if stop_reason == "maxTokens":
            max_token_continues += 1
            if max_token_continues > MAX_MAXTOKEN_CONTINUES:
                logger.warning(
                    "sampling maxTokens continue limit exceeded (%d); returning maxTokens",
                    MAX_MAXTOKEN_CONTINUES,
                )
                return last_text, stop_reason

            logger.info(
                "sampling maxTokens in round %d; output hit requested_max_tokens=%d; "
                "text_len=%d chars; missing_tokens=unknown; asking sampler to continue (%d/%d)",
                round_no,
                MAX_SAMPLING_TOKENS,
                len(last_text),
                max_token_continues,
                MAX_MAXTOKEN_CONTINUES,
            )
            messages.append(types.SamplingMessage(role="assistant", content=result.content))
            messages.append(
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            "Your previous response hit the max token limit before producing a usable final JSON result. "
                            "Continue from where you stopped. Do not restart from scratch. "
                            "If you have enough information to conclude, return exactly one valid JSON object matching "
                            "the requested schema. Do not wrap it in Markdown."
                        ),
                    ),
                )
            )
            continue

        if stop_reason != "toolUse":
            return last_text, stop_reason

        tool_uses = [block for block in blocks if isinstance(block, types.ToolUseContent)]
        if not tool_uses:
            return last_text, stop_reason

        tool_results: list[types.ToolResultContent] = []
        for tool_use in tool_uses:
            tool_args = tool_use.input if isinstance(tool_use.input, dict) else {}
            arg_summary = ""
            if tool_use.name == "shell_command":
                command = str(tool_args.get("command", ""))
                arg_summary = f" command={_safe_log_text(command)!r}"
            logger.info("sampling executing tool name=%s%s", tool_use.name, arg_summary)
            output = _execute_broker_tool(tool_use.name, tool_args, repo_path, process_groups, leaked_pids)
            logger.info("sampling tool result name=%s output_len=%d", tool_use.name, len(output))
            tool_results.append(
                types.ToolResultContent(
                    type="tool_result",
                    toolUseId=tool_use.id,
                    content=[types.TextContent(type="text", text=output)],
                )
            )
        messages.append(types.SamplingMessage(role="assistant", content=result.content))
        messages.append(types.SamplingMessage(role="user", content=tool_results))

    return last_text, "maxRoundsExceeded"


# ---------------------------------------------------------------------------
# JSON repair helper
# ---------------------------------------------------------------------------
async def _repair_json_with_sampling(
    ctx: Any,
    operation: str,
    raw_response: str,
    parse_error: str,
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    expected_schema = _expected_json_schema_for_operation(operation)
    repair_prompt = (
        "The broker MCP server could not parse your previous response as the required JSON object.\n\n"
        f"Operation: {operation}\n\n"
        f"Parser error:\n{parse_error}\n\n"
        "Expected JSON schema / allowed shapes:\n"
        f"{expected_schema}\n\n"
        "Previous raw response follows exactly between markers. Convert it to exactly one valid JSON object "
        "matching the expected schema. Do not add Markdown, code fences, commentary, or extra text.\n\n"
        "---RAW_RESPONSE_START---\n"
        f"{raw_response}\n"
        "---RAW_RESPONSE_END---"
    )

    messages: list[types.SamplingMessage] = [
        types.SamplingMessage(
            role="user",
            content=types.TextContent(type="text", text=repair_prompt),
        )
    ]

    for attempt_no in range(1, MAX_JSON_REPAIR_ATTEMPTS + 1):
        result = await ctx.session.create_message(
            messages=messages,
            max_tokens=MAX_SAMPLING_TOKENS,
        )
        blocks = result.content if isinstance(result.content, list) else [result.content]
        repaired_text = ""
        for block in blocks:
            if isinstance(block, types.TextContent):
                repaired_text = block.text

        stop_reason = getattr(result, "stopReason", None) or "endTurn"
        try:
            parsed = _extract_first_json_object(repaired_text)
            attempts.append(
                {
                    "attempt": attempt_no,
                    "stop_reason": stop_reason,
                    "success": True,
                    "response_len": len(repaired_text),
                }
            )
            logger.info(
                "JSON_REPAIR: attempt %d/%d stop_reason=%s success=True response_len=%d",
                attempt_no,
                MAX_JSON_REPAIR_ATTEMPTS,
                stop_reason,
                len(repaired_text),
            )
            return parsed, repaired_text, attempts
        except Exception as exc:
            error_text = str(exc)
            attempts.append(
                {
                    "attempt": attempt_no,
                    "stop_reason": stop_reason,
                    "success": False,
                    "error": error_text,
                    "response_len": len(repaired_text),
                    "response_prefix": repaired_text[:JSON_ERROR_PREFIX_CHARS],
                }
            )
            logger.info(
                "JSON_REPAIR: attempt %d/%d stop_reason=%s success=False error=%s response_prefix=%r",
                attempt_no,
                MAX_JSON_REPAIR_ATTEMPTS,
                stop_reason,
                error_text,
                repaired_text[:JSON_ERROR_PREFIX_CHARS],
            )
            messages.append(types.SamplingMessage(role="assistant", content=result.content))
            messages.append(
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            "That response still did not parse as the required JSON object.\n\n"
                            f"Parser error:\n{error_text}\n\n"
                            "Return exactly one valid JSON object matching the expected schema. "
                            "Do not include Markdown, code fences, commentary, or extra text."
                        ),
                    ),
                )
            )

    raise BrokerError(
        "Could not repair LLM response into valid JSON after "
        f"{MAX_JSON_REPAIR_ATTEMPTS} attempts; last_error="
        f"{attempts[-1].get('error') if attempts else parse_error}"
    )


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name not in {"getNextTask", "reviewTask"}:
        raise ValueError(f"Unknown tool: {name}")

    repo = _resolve_repo_path(arguments["repo_path"])
    repo_path = str(repo)
    request_id = uuid.uuid4().hex
    timestamp_before = datetime.now(timezone.utc).isoformat()
    t_before = time.monotonic()
    log: LogWriter | None = None
    process_groups: list[int] = []
    leaked_pids: list[int] = []

    try:
        git = GitCapturer(repo_path)
        head_before = git.head_sha()
        branch = git.branch()
        dirty = git.is_dirty()
        log = LogWriter(_get_log_path(repo_path))

        started_event = {
            "event": f"{name}_started",
            "request_id": request_id,
            "timestamp_utc": timestamp_before,
            "repo_path": repo_path,
            "branch": branch,
            "head_sha": head_before,
            "working_tree_dirty": dirty,
            "arguments": arguments,
        }
        log.append(started_event)

        prompt = _get_next_prompt(repo_path, git, arguments) if name == "getNextTask" else _review_task_prompt(repo_path, git, arguments)
        response_text, stop_reason = await _sample_with_tools(
            app.request_context,
            prompt,
            repo_path,
            process_groups,
            leaked_pids,
        )
        logger.info(
            "call_tool %s sampling returned stop_reason=%s text_len=%d response_prefix=%r",
            name,
            stop_reason,
            len(response_text),
            response_text[:JSON_ERROR_PREFIX_CHARS],
        )
        json_repair_attempts: list[dict[str, Any]] = []
        try:
            parsed = _extract_first_json_object(response_text)
        except Exception as exc:
            logger.info(
                "call_tool %s JSON parse failed: %s response_len=%d response_prefix=%r",
                name,
                exc,
                len(response_text),
                response_text[:JSON_ERROR_PREFIX_CHARS],
            )
            parsed, response_text, json_repair_attempts = await _repair_json_with_sampling(
                app.request_context,
                name,
                response_text,
                str(exc),
            )

        head_after = git.head_sha()
        stale = head_after != head_before
        status = "STALE" if stale else "COMPLETED"
        duration_ms = int((time.monotonic() - t_before) * 1000)

        if stale:
            result: dict[str, Any] = {
                "request_id": request_id,
                "status": "ERROR",
                "error": "Repository HEAD changed during broker operation; retry against current HEAD.",
                "stale": True,
                "head_sha_before": head_before,
                "head_sha_after": head_after,
            }
        else:
            result = {
                "request_id": request_id,
                "status": status,
                "stale": False,
                "head_sha": head_before,
                "broker_result": parsed,
            }

        completed_event = {
            "event": f"{name}_completed",
            "request_id": request_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "repo_path": repo_path,
            "head_sha_before": head_before,
            "head_sha_after": head_after,
            "status": status,
            "stale": stale,
            "stop_reason": stop_reason,
            "duration_ms": duration_ms,
            "result": result,
            "raw_response": response_text,
            "json_repair_attempts": json_repair_attempts,
        }
        log.append(completed_event)
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as exc:
        logger.error("call_tool %s failed: %s", name, exc, exc_info=True)
        result = {
            "request_id": request_id,
            "status": "ERROR",
            "stale": False,
            "error": str(exc),
        }
        if log is not None:
            log.append(
                {
                    "event": f"{name}_completed",
                    "request_id": request_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "repo_path": repo_path if "repo_path" in locals() else arguments.get("repo_path"),
                    "status": "ERROR",
                    "error": str(exc),
                }
            )
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    finally:
        _cleanup_process_groups(process_groups, leaked_pids)
        if log is not None:
            log.close()


async def main() -> None:
    logger.info("=== %s server started ===", SERVER_NAME)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=types.ServerCapabilities(),
            ),
        )
    logger.info("=== %s server exiting ===", SERVER_NAME)


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("=== %s interrupted ===", SERVER_NAME)
    except BaseException:
        logger.exception("=== %s unhandled exception ===", SERVER_NAME)
