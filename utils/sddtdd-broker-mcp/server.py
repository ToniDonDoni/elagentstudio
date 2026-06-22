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

import datetime
import json
import logging
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

logger = logging.getLogger("sddtdd-broker-mcp")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
    force=True,
)

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
NO_REVIEW_STAGES = {"USER_INPUT_CAPTURE", "PROJECT_INIT", "SPEC_SPEC", "DECOMPOSE", "TASKS_COMPLETE"}

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

# Mapping from a workflow stage to the prior journal entries that must
# already exist in the committed journal for the broker to consider
# this stage's prerequisites satisfied. Each entry is (TYPE, STATUS);
# the broker only checks that any committed entry has that TYPE and
# STATUS. ``*_REVIEW`` prerequisites are review verdicts (STATUS:
# PASS); ``*_COMPLETE`` and work-type prerequisites are convergence
# events or work entries (STATUS: COMPLETED).
STAGE_PREREQUISITES: dict[str, list[tuple[str, str]]] = {
    "GREEN": [("RED_REVIEW", "PASS")],
    "TASKS_COMPLETE": [("GREEN_REVIEW", "PASS")],
    "REGRESSION": [("TASKS_COMPLETE", "COMPLETED")],
    "FINAL": [("REGRESSION_REVIEW", "PASS")],
}

# Mapping from a workflow stage to the artifacts that must exist at
# ``head_sha_before`` for the broker to consider the stage complete.
# The broker does not re-review the artifact's content — that is the
# reviewer's job — but it does verify that the artifact that the
# reviewer allegedly reviewed actually exists in the committed tree.
STAGE_REQUIRED_ARTIFACTS: dict[str, list[str]] = {
    "USER_INPUT_CAPTURE": [".sddtdd_skill/SPEC-DRAFT.md"],
    "SPEC_SPEC": [".sddtdd_skill/SPEC.md"],
    "ARCHITECTURE": [".sddtdd_skill/ARCHITECTURE.md"],
    "DECOMPOSE": [".sddtdd_skill/TASKS.md"],
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
    # Runtime access log (not committed). Sibling of review-access.jsonl;
    # both are ignored by .gitignore via the `.sddtdd_skill/*.jsonl`
    # pattern shipped with the spec-driven-tdd skill.
    return Path(repo_path) / ".sddtdd_skill" / "broker-access.jsonl"


def _append_broker_event(repo_path: str, event: dict[str, Any]) -> None:
    path = _broker_log_path(repo_path)
    event.setdefault("timestamp_utc", datetime.datetime.now(datetime.timezone.utc).isoformat())
    logger.info("_append_broker_event: path=%s exists=%s", path, path.exists())
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
    return _git_show(repo_path, ref, ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log")


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
                "description": (
                    "Workflow stage the broker issued. One of USER_INPUT_CAPTURE, "
                    "SPEC_SPEC, ARCHITECTURE, DECOMPOSE, RED, GREEN, TASKS_COMPLETE, "
                    "REGRESSION, FINAL."
                ),
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
                f".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log is absent at HEAD {head_sha_before[:12]}; cannot verify process state."
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
                f"work_journal_id {work_journal_id} not found in committed .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log at HEAD {head_sha_before[:12]}; "
                "the implementer must commit the work journal entry before calling reviewTask."
            ],
        }

    if work_entry.get("STATUS") != "COMPLETED":
        findings.append(
            f"work_journal_id {work_journal_id} has STATUS {work_entry.get('STATUS')!r}; expected 'COMPLETED'."
        )

    # Stage prerequisites (prior journal entries that must already exist).
    for prereq_type, prereq_status in STAGE_PREREQUISITES.get(task_kind, []):
        if not any(
            e.get("TYPE") == prereq_type and e.get("STATUS") == prereq_status
            for e in entries
        ):
            findings.append(
                f"prerequisite {prereq_type}: {prereq_status} is required before {task_kind} "
                f"and is missing from the committed journal."
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
                    f"review_journal_id {review_journal_id} not found in committed .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log at HEAD {head_sha_before[:12]}."
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


def _read_broker_log(repo_path: str) -> list[dict[str, Any]]:
    """Read the broker access log (a JSONL file under ``.sddtdd_skill/``).

    The access log records every ``getNextTask`` issuance and every
    ``reviewTask`` verdict. It is **not** committed to the working
    tree — it lives under ``.sddtdd_skill/`` (next to the committed
    artifacts) and is expected to be ignored by ``.gitignore`` via
    the ``.sddtdd_skill/*.jsonl`` pattern shipped with the
    spec-driven-tdd skill. The broker uses it to remember which
    task ids it has issued in this delivery.
    """
    path = _broker_log_path(repo_path)
    logger.info("_read_broker_log: path=%s exists=%s", path, path.exists())
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            events.append(json.loads(raw_line))
        except json.JSONDecodeError:
            continue
    return events


def _read_repo_state(repo_path: str) -> dict[str, Any]:
    try:
        head_sha = _git(repo_path, "rev-parse", "HEAD")
    except Exception:
        return {"exists": False}
    journal_text = _git_show(repo_path, head_sha, ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log")
    journal_path = f"{repo_path}/.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"
    logger.info("_read_repo_state: journal_path=%s head_sha=%s lines=%d",
                 journal_path, head_sha, len((journal_text or "").splitlines()))
    entries = _parse_journal(journal_text or "")

    # Identify broker task ids the broker has issued in this delivery
    # (from the broker access log) and the broker task ids the
    # implementer has verified (from committed journal entries of
    # TYPE=BROKER_TASK_REVIEW with STATUS=PASS, carrying TASK_ID).
    broker_events = _read_broker_log(repo_path)
    issued_task_ids: set[str] = set()
    for event in broker_events:
        if event.get("event") == "task_issued":
            tid = event.get("task_id")
            if isinstance(tid, str) and tid:
                issued_task_ids.add(tid)
    broker_passed_task_ids: set[str] = set()
    for entry in entries:
        if (
            entry.get("TYPE") == "BROKER_TASK_REVIEW"
            and entry.get("STATUS") == "PASS"
        ):
            tid = entry.get("TASK_ID")
            if isinstance(tid, str) and tid:
                broker_passed_task_ids.add(tid)
    unverified_task_ids = issued_task_ids - broker_passed_task_ids
    logger.info("_read_repo_state: issued=%s passed=%s unverified=%s",
                 sorted(issued_task_ids), sorted(broker_passed_task_ids), sorted(unverified_task_ids))

    return {
        "exists": True,
        "head_sha": head_sha,
        "entries": entries,
        "has_user_input": any(e.get("TYPE") == "USER_INPUT" for e in entries),
        "has_spec": any(e.get("TYPE") == "SPEC_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_architecture": any(e.get("TYPE") == "ARCHITECTURE_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_task_review": any(e.get("TYPE") == "TASK_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_red_review": any(e.get("TYPE") == "RED_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_green_review": any(e.get("TYPE") == "GREEN_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_tasks_complete": any(
            e.get("TYPE") == "TASKS_COMPLETE" and e.get("STATUS") == "COMPLETED"
            for e in entries
        ),
        "has_regression": any(e.get("TYPE") == "REGRESSION_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_final_review": any(e.get("TYPE") == "FINAL_REVIEW" and e.get("STATUS") == "PASS" for e in entries),
        "has_done": any(e.get("TYPE") == "DONE" and e.get("STATUS") == "COMPLETED" for e in entries),
        "issued_task_ids": issued_task_ids,
        "broker_passed_task_ids": broker_passed_task_ids,
        "unverified_task_ids": unverified_task_ids,
    }


def _select_next_task(repo_state: dict[str, Any], previous_task_id: str | None, user_input: str | None) -> dict[str, Any]:
    """Decide what to return for getNextTask.

    The order of stages is fixed by the orchestrator role file. The
    broker picks the earliest unmet mandatory condition and returns one
    task. This is a deterministic state-machine; no LLM sampling is
    involved in v3.

    The broker additionally enforces a **process-gate**: it will not
    hand out the next task while a previously issued task id has not
    been verified (``BROKER_TASK_REVIEW: PASS``) and committed. The
    implementer cannot skip ``reviewTask`` and call ``getNextTask``
    for the next step; the broker returns ``blocked`` with a
    ``required_action`` telling the implementer to verify the
    outstanding task first.
    """
    # Broker gate: outstanding issued task ids must have a committed
    # BROKER_TASK_REVIEW: PASS entry whose TASK_ID matches. This
    # catches the implementer that does the work, never calls
    # reviewTask, and asks the broker for the next task anyway.
    unverified = sorted(repo_state.get("unverified_task_ids", set()))
    logger.info("_select_next_task: gate_check unverified=%s", unverified)
    if unverified:
        return {
            "status": "blocked",
            "summary": (
                f"Outstanding broker task id(s) {unverified} have not been verified "
                f"with reviewTask and a committed BROKER_TASK_REVIEW: PASS journal entry. "
                f"The broker will not issue the next task until the previous one is verified."
            ),
            "required_action": (
                "Call reviewTask for the outstanding task id(s) first, append a "
                "BROKER_TASK_REVIEW: PASS journal entry carrying TASK_ID=<task_id>, "
                "commit, then call getNextTask again."
            ),
            "unverified_task_ids": unverified,
        }

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
                "Preserve the original user request as .sddtdd_skill/SPEC-DRAFT.md, create the USER_INPUT journal entry, "
                "and commit both. Do not translate, summarize, or normalize the user request."
            ),
            "allowed_scope": [".sddtdd_skill/SPEC-DRAFT.md", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
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
            "allowed_scope": [".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
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
            "instruction": "Create .sddtdd_skill/SPEC.md from committed .sddtdd_skill/SPEC-DRAFT.md. Create the SPEC_SPEC and SPEC_REVIEW journal entries.",
            "allowed_scope": [".sddtdd_skill/SPEC.md", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
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
            "instruction": "Create or update .sddtdd_skill/ARCHITECTURE.md from reviewed .sddtdd_skill/SPEC.md. Create the ARCHITECTURE and ARCHITECTURE_REVIEW journal entries.",
            "allowed_scope": [".sddtdd_skill/ARCHITECTURE.md", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
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
            "instruction": "Create .sddtdd_skill/TASKS.md from reviewed .sddtdd_skill/SPEC.md and reviewed .sddtdd_skill/ARCHITECTURE.md. Create the DECOMPOSE and TASK_REVIEW journal entries.",
            "allowed_scope": [".sddtdd_skill/TASKS.md", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["commit hash", "DECOMPOSE journal JID", "TASK_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "TASK_REVIEW",
            "rationale": "Task review is the earliest unmet mandatory condition.",
        }

    # Per-task work stages: in this delivery the broker keeps a flat
    # single-task model and treats the RED → RED_REVIEW → GREEN →
    # GREEN_REVIEW chain as one convergence sequence. A real
    # multi-task model would iterate this block per task in TASKS.md.
    if not repo_state.get("has_red_review"):
        return {
            "status": "TASK",
            "task_id": "B-000006",
            "task_kind": "RED",
            "instruction": "Create the failing test that defines the work. Journal the RED entry and request the RED_REVIEW verdict.",
            "allowed_scope": ["tests/", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["commit hash", "RED journal JID", "RED_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "RED_REVIEW",
            "rationale": "RED is the earliest unmet per-task stage.",
        }

    if not repo_state.get("has_green_review"):
        return {
            "status": "TASK",
            "task_id": "B-000007",
            "task_kind": "GREEN",
            "instruction": "Implement the production code that makes the failing test pass, run the test and confirm it passes. Journal the GREEN entry and request the GREEN_REVIEW verdict.",
            "allowed_scope": ["src/", "tests/", ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["commit hash", "GREEN journal JID", "GREEN_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "GREEN_REVIEW",
            "rationale": "GREEN is the earliest unmet per-task stage.",
        }

    if not repo_state.get("has_tasks_complete"):
        return {
            "status": "TASK",
            "task_id": "B-000008",
            "task_kind": "TASKS_COMPLETE",
            "instruction": (
                "All per-task chains are closed (GREEN_REVIEW: PASS in the committed journal). "
                "Record the TASKS_COMPLETE convergence event in the journal with STATUS: COMPLETED, "
                "and commit. There is no independent reviewer verdict for this stage."
            ),
            "allowed_scope": [".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["commit hash", "TASKS_COMPLETE journal JID with STATUS: COMPLETED"],
            "independent_review_required": False,
            "review_type": None,
            "rationale": "Convergence event: all per-task branches reached GREEN_REVIEW: PASS.",
        }

    if not repo_state.get("has_regression"):
        return {
            "status": "TASK",
            "task_id": "B-000009",
            "task_kind": "REGRESSION",
            "instruction": "Run the full required test suite and capture regression evidence. Create the REGRESSION and REGRESSION_REVIEW journal entries.",
            "allowed_scope": [".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log", "regression evidence files"],
            "required_evidence": ["commit hash", "REGRESSION journal JID", "REGRESSION_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "REGRESSION_REVIEW",
            "rationale": "Regression review is the earliest unmet mandatory condition.",
        }

    if not repo_state.get("has_final_review"):
        return {
            "status": "TASK",
            "task_id": "B-000010",
            "task_kind": "FINAL",
            "instruction": "Final review of the complete committed solution and its artifact chain. Create the FINAL_REVIEW journal entry.",
            "allowed_scope": [".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
            "required_evidence": ["FINAL_REVIEW journal JID with STATUS: PASS"],
            "independent_review_required": True,
            "review_type": "FINAL_REVIEW",
            "rationale": "Final review is the earliest unmet mandatory condition.",
        }

    if not repo_state.get("has_done"):
        return {
            "status": "TASK",
            "task_id": "B-000011",
            "task_kind": "DONE",
            "instruction": "Record the DONE journal entry with STATUS: COMPLETED.",
            "allowed_scope": [".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log"],
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

    if name == "getNextTask":
        _append_broker_event(repo_path, {
            "event": "get_next_task_started",
            "request_id": request_id,
            "head_sha_before": head_sha_before,
            "arguments": arguments,
        })
    elif name == "reviewTask":
        _append_broker_event(repo_path, {
            "event": "task_review_started",
            "request_id": request_id,
            "task_id": task_id,
            "head_sha_before": head_sha_before,
            "arguments": arguments,
        })
    else:
        _append_broker_event(repo_path, {
            "event": "unknown_tool",
            "request_id": request_id,
            "tool_name": name,
            "head_sha_before": head_sha_before,
        })

    try:
        if name == "getNextTask":
            previous_task_id = arguments.get("previous_task_id")
            user_input = arguments.get("user_input")
            repo_state = _read_repo_state(repo_path)
            result = _select_next_task(repo_state, previous_task_id, user_input)
            result["request_id"] = request_id
            result.setdefault("repo_head", repo_state.get("head_sha", ""))
            _append_broker_event(repo_path, {
                "event": "get_next_task_completed",
                "request_id": request_id,
                "status": result.get("status"),
                "task_id": result.get("task_id"),
                "task_kind": result.get("task_kind"),
                "instruction": result.get("instruction"),
                "allowed_scope": result.get("allowed_scope"),
                "required_evidence": result.get("required_evidence"),
                "independent_review_required": result.get("independent_review_required"),
                "review_type": result.get("review_type"),
                "rationale": result.get("rationale"),
                "summary": result.get("summary"),
                "head_sha_before": head_sha_before,
                "previous_task_id": previous_task_id,
            })
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
