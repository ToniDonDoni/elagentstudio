"""sddtdd-broker-mcp — MCP task broker for Spec-Driven TDD.

The server exposes a two-tool broker contract:

* ``getNextTask`` — returns the next workflow task, or ``complete`` /
  ``blocked``. The first call carries ``user_input`` and creates or
  resumes the delivery. Subsequent calls carry ``previous_task_id``.
* ``reviewTask`` — performs **process-gate verification** without LLM
  sampling. The broker itself reads the committed journal, the broker
  task instruction, and the implementer's claimed evidence, and decides
  whether the issued workflow step has produced all evidence and
  approvals required to permit the next workflow step. The broker does
  not re-review the artifact's correctness — that is the independent
  reviewer's job (``mcp_sddtdd_review_review``).

The broker does not pass role files to a sampled model. The orchestrator
role file (``SKILL-ORCHESTRATOR.md``) is the source of truth for the
decision policy, but the policy is enforced directly by the broker in
Python.
"""

from __future__ import annotations

import json
import os
import re
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

BROKER_TOOLS = {"getNextTask", "reviewTask"}

# Stages that have no independent reviewer and therefore require no
# review verdict in the journal for process-gate verification.
NO_REVIEW_STAGES = {"USER_INPUT_CAPTURE", "PROJECT_INIT", "SPEC_SPEC", "DECOMPOSE"}

# Mapping from a workflow stage to the review_type the implementer must
# have journaled with STATUS: PASS by the time the broker verifies the
# task. The reviewer verdict is what the broker checks; the broker does
# not generate one.
STAGE_REQUIRED_REVIEW: dict[str, str] = {
    "ARCHITECTURE": "ARCHITECTURE_REVIEW",
    "RED": "RED_REVIEW",
    "GREEN": "GREEN_REVIEW",
    "REGRESSION": "REGRESSION_REVIEW",
    "FINAL": "FINAL_REVIEW",
}

# Mapping from a workflow stage to the prior review verdicts that must
# also exist in the journal (in addition to the stage's own review).
STAGE_PREREQUISITE_REVIEWS: dict[str, list[str]] = {
    "GREEN": ["RED_REVIEW"],
    "FINAL": ["REGRESSION_REVIEW"],
}

# Mapping from a workflow stage to the artifacts that must exist at
# ``head_sha_before`` for the broker to consider the stage complete.
# The broker does not re-review the artifact's content — that is the
# reviewer's job — but it does verify that the artifact that the
# reviewer allegedly reviewed actually exists in the committed tree.
STAGE_REQUIRED_ARTIFACTS: dict[str, list[str]] = {
    "USER_INPUT_CAPTURE": ["SPEC-DRAFT.md"],
    "SPEC_SPEC": ["SPEC.md"],
    "ARCHITECTURE": ["ARCHITECTURE.md"],
    "DECOMPOSE": ["TASKS.md"],
}


# ---------------------------------------------------------------------------
# Git and journal helpers
# ---------------------------------------------------------------------------


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


def _read_text(path: Path) -> str:
    if not path.exists():
        return f"MISSING: {path}"
    return path.read_text(errors="replace")


# ---------------------------------------------------------------------------
# Journal parsing
# ---------------------------------------------------------------------------


_ENTRY_HEADER = re.compile(r"^=== (?P<jid>J-\S+) ===\s*$")


def _parse_journal(text: str) -> list[dict[str, str]]:
    """Parse a journal log into a list of dicts with the raw key/value fields.

    Each entry is delimited by ``=== JID ===`` lines. Field lines are
    either ``|KEY: VALUE`` (the canonical form documented in
    JOURNAL.md) or plain ``KEY: VALUE`` for backward compatibility.
    """
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in text.splitlines():
        m = _ENTRY_HEADER.match(raw_line)
        if m:
            if current is not None:
                entries.append(current)
            current = {"_jid": m.group("jid")}
            continue
        if current is None:
            continue
        line = raw_line.lstrip()
        if line.startswith("|"):
            line = line[1:].strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key in current:
            current[key] = f"{current[key]}\n{value}"
        else:
            current[key] = value
    if current is not None:
        entries.append(current)
    return entries


def _committed_journal(repo_path: str, ref: str | None = None) -> str | None:
    """Return the committed journal text at the given ref (or HEAD).

    The broker reads the journal at ``head_sha_before`` (the HEAD the
    broker observed at the start of ``reviewTask``). The implementer
    cannot commit additional journal entries after the broker started
    verification and then re-ask for a PASS.
    """
    if ref is None:
        try:
            ref = _git(repo_path, "rev-parse", "HEAD")
        except Exception:
            return None
    return _git_show(repo_path, ref, "JOURNAL_SDD_TDD_SKILL.log")


def _file_exists_at_ref(repo_path: str, ref: str, file_path: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "cat-file", "-e", f"{ref}:{file_path}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _working_tree_dirty(repo_path: str) -> bool:
    try:
        return bool(_git(repo_path, "status", "--porcelain"))
    except Exception:
        return True  # treat unreadable repo as dirty for safety


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


def _get_next_task_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Absolute path to the Git repository"},
            "user_input": {
                "type": "string",
                "description": "Original user request. Required on the first call to start a new delivery; omit on subsequent calls.",
            },
            "previous_task_id": {
                "type": "string",
                "description": "Task id returned by the previously verified task. Omit on the first call to start a new delivery.",
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
            "task_kind": {
                "type": "string",
                "description": "Workflow stage the broker issued. One of USER_INPUT_CAPTURE, SPEC_SPEC, ARCHITECTURE, DECOMPOSE, RED, GREEN, REGRESSION, FINAL.",
            },
            "review_type": {
                "type": ["string", "null"],
                "description": (
                    "Review type the implementer was required to obtain. Null/absent when the task does not require independent review."
                ),
            },
            "claimed_result": {"type": "string", "description": "Implementer completion summary"},
            "work_journal_id": {
                "type": "string",
                "description": "JID of the work journal entry the implementer just committed (the stage's own journal entry).",
            },
            "evidence": {
                "type": "object",
                "description": "Concrete evidence supporting completion",
                "properties": {
                    "commits": {"type": "array", "items": {"type": "string"}},
                    "journal_ids": {"type": "array", "items": {"type": "string"}},
                    "review_request_id": {"type": "string"},
                    "review_journal_id": {
                        "type": "string",
                        "description": "JID of the journal entry recording the independent reviewer verdict (when one was required).",
                    },
                    "test_commands": {"type": "array", "items": {"type": "string"}},
                    "files": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "required": ["repo_path", "task_id", "task_kind", "claimed_result", "work_journal_id"],
    }


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="getNextTask",
            description=(
                "Ask the orchestrator for the next task, or for 'complete' / 'blocked'. "
                "The first call carries user_input; subsequent calls carry previous_task_id."
            ),
            inputSchema=_get_next_task_schema(),
        ),
        types.Tool(
            name="reviewTask",
            description=(
                "Ask the orchestrator to verify that the current task is process-complete. "
                "The broker checks the committed journal, the issued task_kind, and the "
                "required reviewer verdict; it does not re-review the artifact."
            ),
            inputSchema=_review_task_schema(),
        ),
    ]


# ---------------------------------------------------------------------------
# Process-gate verification (reviewTask)
# ---------------------------------------------------------------------------


def _find_entry(entries: list[dict[str, str]], jid: str) -> dict[str, str] | None:
    for entry in entries:
        if entry.get("_jid") == jid:
            return entry
    return None


def _check_process_gate(
    repo_path: str,
    task_id: str,
    task_kind: str,
    review_type: str | None,
    work_journal_id: str,
    evidence: dict[str, Any],
    head_sha_before: str,
) -> dict[str, Any]:
    """Run the process-gate checks for the issued task.

    The broker reads the committed journal at ``head_sha_before`` (the
    HEAD the broker observed when ``reviewTask`` was called). The
    implementer cannot commit additional journal entries after the
    broker started verification and then re-ask for a PASS.

    Returns a dict with ``status`` in {PASS, FAIL, NEEDS_CLARIFICATION, ERROR}
    and ``findings`` (a list of strings).
    """
    findings: list[str] = []

    if _working_tree_dirty(repo_path):
        return {
            "status": "FAIL",
            "findings": [
                "Working tree is dirty; the broker only verifies committed state. Commit the work and the journal update first."
            ],
        }

    if not head_sha_before:
        return {
            "status": "ERROR",
            "findings": ["HEAD is unknown; cannot pin the broker's verification to a commit."],
        }

    # Required artifacts: the broker verifies the artifact that the
    # reviewer allegedly reviewed actually exists in the committed
    # tree. This catches the "journal is pretty, artifact evaporated"
    # failure.
    for artifact in STAGE_REQUIRED_ARTIFACTS.get(task_kind, []):
        if not _file_exists_at_ref(repo_path, head_sha_before, artifact):
            findings.append(
                f"required artifact {artifact!r} is absent at HEAD {head_sha_before[:12]}; "
                f"the broker cannot accept a process-gate PASS for {task_kind} without it."
            )

    journal_text = _committed_journal(repo_path, head_sha_before)
    if journal_text is None:
        return {
            "status": "ERROR",
            "findings": [
                f"JOURNAL_SDD_TDD_SKILL.log is absent at HEAD {head_sha_before[:12]}; cannot verify process state."
            ],
        }

    entries = _parse_journal(journal_text)
    if not entries:
        return {
            "status": "FAIL",
            "findings": ["Committed journal is empty; the implementer must journal the work before calling reviewTask."],
        }

    work_entry = _find_entry(entries, work_journal_id)
    if work_entry is None:
        return {
            "status": "FAIL",
            "findings": [
                f"work_journal_id {work_journal_id} not found in committed JOURNAL_SDD_TDD_SKILL.log at HEAD {head_sha_before[:12]}; "
                "the implementer must commit the work journal entry before calling reviewTask."
            ],
        }

    if work_entry.get("STATUS") != "COMPLETED":
        findings.append(
            f"work_journal_id {work_journal_id} has STATUS {work_entry.get('STATUS')!r}; expected 'COMPLETED'."
        )

    # Stage prerequisites (prior review verdicts that must already exist).
    for prereq in STAGE_PREREQUISITE_REVIEWS.get(task_kind, []):
        if not any(
            e.get("TYPE") == prereq and e.get("STATUS") == "PASS" for e in entries
        ):
            findings.append(
                f"prerequisite review {prereq}: PASS is required before {task_kind} and is missing from the committed journal."
            )

    # Stage-required reviewer verdict.
    required_review = review_type or STAGE_REQUIRED_REVIEW.get(task_kind)
    if required_review:
        review_journal_id = (evidence or {}).get("review_journal_id")
        if not review_journal_id:
            findings.append(
                f"reviewer verdict for {required_review} is required by {task_kind} but the implementer did not provide a review_journal_id."
            )
        else:
            review_entry = _find_entry(entries, review_journal_id)
            if review_entry is None:
                findings.append(
                    f"review_journal_id {review_journal_id} not found in committed JOURNAL_SDD_TDD_SKILL.log at HEAD {head_sha_before[:12]}."
                )
            else:
                if review_entry.get("TYPE") != required_review:
                    findings.append(
                        f"review_journal_id {review_journal_id} has TYPE {review_entry.get('TYPE')!r}; expected {required_review!r}."
                    )
                if review_entry.get("STATUS") != "PASS":
                    findings.append(
                        f"review_journal_id {review_journal_id} has STATUS {review_entry.get('STATUS')!r}; expected 'PASS'."
                    )
                # Strict binding: the reviewer verdict must descend
                # from the work_journal_id the implementer just
                # committed. A verdict that descends from a different
                # work entry — or has no PARENT — is rejected.
                if review_entry.get("PARENT") != work_journal_id:
                    findings.append(
                        f"review_journal_id {review_journal_id} has PARENT {review_entry.get('PARENT')!r}; "
                        f"expected {work_journal_id!r} (the work entry for this broker task). "
                        "The reviewer verdict must descend from the work entry of the task being verified."
                    )

    if findings:
        return {"status": "FAIL", "findings": findings}
    return {
        "status": "PASS",
        "findings": [
            f"process-gate verification passed for task {task_id} ({task_kind}) at HEAD {head_sha_before[:12]}"
        ],
    }


# ---------------------------------------------------------------------------
# getNextTask — minimal schema-driven decision (no LLM sampling in v3)
# ---------------------------------------------------------------------------


def _read_repo_state(repo_path: str) -> dict[str, Any]:
    try:
        head_sha = _git(repo_path, "rev-parse", "HEAD")
    except Exception:
        return {"exists": False}
    journal_text = _git_show(repo_path, head_sha, "JOURNAL_SDD_TDD_SKILL.log")
    entries = _parse_journal(journal_text or "")
    return {
        "exists": True,
        "head_sha": head_sha,
        "entries": entries,
        "has_user_input": any(e.get("TYPE") == "USER_INPUT" for e in entries),
        "has_spec": any(e.get("TYPE") == "SPEC_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_architecture": any(e.get("TYPE") == "ARCHITECTURE_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_task_review": any(e.get("TYPE") == "TASK_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_regression": any(e.get("TYPE") == "REGRESSION_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_final_review": any(e.get("TYPE") == "FINAL_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_done": any(e.get("TYPE") == "DONE" and e.get("STATUS") == "COMPLETED" for e in entries),
    }


def _select_next_task(repo_state: dict[str, Any], previous_task_id: str | None, user_input: str | None) -> dict[str, Any]:
    """Decide what to return for getNextTask.

    The order of stages is fixed by the orchestrator role file. The
    broker picks the earliest unmet mandatory condition and returns one
    task. This is a deterministic state-machine; no LLM sampling is
    involved in v3.
    """
    if not repo_state.get("exists"):
        if not user_input:
            return {
                "status": "blocked",
                "summary": "Empty repository: user_input is required to start a new delivery.",
                "required_action": "Call getNextTask again with user_input set to the original user request.",
            }
        return {
            "status": "TASK",
            "task_id": "B-000001",
            "task_kind": "USER_INPUT_CAPTURE",
            "instruction": (
                "Preserve the original user request as SPEC-DRAFT.md, create the USER_INPUT journal entry, "
                "and commit both. Do not translate, summarize, or normalize the user request."
            ),
            "allowed_scope": ["SPEC-DRAFT.md", "JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["commit hash", "USER_INPUT journal JID"],
            "independent_review_required": False,
            "review_type": None,
            "rationale": "Empty repository: capture immutable user input first.",
        }

    if not repo_state.get("has_user_input"):
        return {
            "status": "TASK",
            "task_id": "B-000002",
            "task_kind": "USER_INPUT_CAPTURE",
            "instruction": "The committed journal lacks a USER_INPUT entry. Create the USER_INPUT journal entry and commit it.",
            "allowed_scope": ["JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["USER_INPUT journal JID"],
            "independent_review_required": False,
            "review_type": None,
            "rationale": "First committed state without a USER_INPUT entry; create the journal root.",
        }

    if not repo_state.get("has_spec"):
        return {
            "status": "TASK",
            "task_id": "B-000003",
            "task_kind": "SPEC_SPEC",
            "instruction": "Create SPEC.md from committed SPEC-DRAFT.md. Create the SPEC_SPEC and SPEC_REVIEW journal entries.",
            "allowed_scope": ["SPEC.md", "JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["commit hash", "SPEC_SPEC journal JID", "SPEC_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "SPEC_REVIEW",
            "rationale": "Spec review is the earliest unmet mandatory condition.",
        }

    if not repo_state.get("has_architecture"):
        return {
            "status": "TASK",
            "task_id": "B-000004",
            "task_kind": "ARCHITECTURE",
            "instruction": "Create ARCHITECTURE.md from reviewed SPEC.md. Create the ARCHITECTURE and ARCHITECTURE_REVIEW journal entries.",
            "allowed_scope": ["ARCHITECTURE.md", "JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["commit hash", "ARCHITECTURE journal JID", "ARCHITECTURE_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "ARCHITECTURE_REVIEW",
            "rationale": "Architecture review is the earliest unmet mandatory condition.",
        }

    if not repo_state.get("has_task_review"):
        return {
            "status": "TASK",
            "task_id": "B-000005",
            "task_kind": "DECOMPOSE",
            "instruction": "Create TASKS.md from reviewed SPEC.md and reviewed ARCHITECTURE.md. Create the DECOMPOSE and TASK_REVIEW journal entries.",
            "allowed_scope": ["TASKS.md", "JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["commit hash", "DECOMPOSE journal JID", "TASK_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "TASK_REVIEW",
            "rationale": "Task review is the earliest unmet mandatory condition.",
        }

    if not repo_state.get("has_regression"):
        return {
            "status": "TASK",
            "task_id": "B-000006",
            "task_kind": "REGRESSION",
            "instruction": "Run the full required test suite and capture regression evidence. Create the REGRESSION and REGRESSION_REVIEW journal entries.",
            "allowed_scope": ["JOURNAL_SDD_TDD_SKILL.log", "regression evidence files"],
            "required_evidence": ["commit hash", "REGRESSION journal JID", "REGRESSION_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "REGRESSION_REVIEW",
            "rationale": "Regression review is the earliest unmet mandatory condition.",
        }

    if not repo_state.get("has_final_review"):
        return {
            "status": "TASK",
            "task_id": "B-000007",
            "task_kind": "FINAL",
            "instruction": "Final review of the complete committed solution and its artifact chain. Create the FINAL_REVIEW journal entry.",
            "allowed_scope": ["JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["FINAL_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "FINAL_REVIEW",
            "rationale": "Final review is the earliest unmet mandatory condition.",
        }

    if not repo_state.get("has_done"):
        return {
            "status": "TASK",
            "task_id": "B-000008",
            "task_kind": "DONE",
            "instruction": "Record the DONE journal entry with STATUS: COMPLETED.",
            "allowed_scope": ["JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["DONE journal JID"],
            "independent_review_required": False,
            "review_type": None,
            "rationale": "All required review stages have passed; record DONE.",
        }

    return {
        "status": "complete",
        "summary": "All required SDDTDD completion conditions are satisfied.",
        "rationale": "Final review passed and DONE is journaled.",
    }


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def _normalize_evidence(arguments: dict[str, Any]) -> dict[str, Any]:
    raw = arguments.get("evidence")
    if not isinstance(raw, dict):
        return {}
    return raw


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name not in BROKER_TOOLS:
        raise ValueError(f"Unknown tool: {name}")

    request_id = uuid.uuid4().hex
    started_at = time.monotonic()

    repo_path = str(Path(arguments["repo_path"]).resolve())

    head_sha_before = ""
    try:
        head_sha_before = _git(repo_path, "rev-parse", "HEAD")
    except Exception:
        pass

    task_id = arguments.get("task_id") if name == "reviewTask" else None

    if name == "reviewTask":
        _append_broker_event(repo_path, {
            "event": "task_review_started",
            "request_id": request_id,
            "task_id": task_id,
            "head_sha_before": head_sha_before,
            "arguments": arguments,
        })

    try:
        if name == "getNextTask":
            previous_task_id = arguments.get("previous_task_id")
            user_input = arguments.get("user_input")
            repo_state = _read_repo_state(repo_path)
            result = _select_next_task(repo_state, previous_task_id, user_input)
            result["request_id"] = request_id
            result.setdefault("repo_head", repo_state.get("head_sha", ""))
        elif name == "reviewTask":
            evidence = _normalize_evidence(arguments)
            result = _check_process_gate(
                repo_path=repo_path,
                task_id=arguments.get("task_id", ""),
                task_kind=arguments.get("task_kind", ""),
                review_type=arguments.get("review_type"),
                work_journal_id=arguments.get("work_journal_id", ""),
                evidence=evidence,
                head_sha_before=head_sha_before,
            )
            result["request_id"] = request_id
            result["task_id"] = arguments.get("task_id")
            result["repo_head"] = head_sha_before
        else:
            result = {"status": "ERROR", "summary": f"Unknown tool: {name}"}
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
                server_version="3.0.0",
                capabilities=types.ServerCapabilities(),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
