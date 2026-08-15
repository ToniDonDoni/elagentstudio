#!/usr/bin/env python3
"""Verify committed Spec-Driven TDD journal, plan, and delegation evidence.

Primary mode is plan-skip evidence: no IMPLEMENTATION-PLAN.md file or plan
stages are required, task ids come from the journal/TASKS.md, and
implementer/reviewer identities are resolved from the delegation events file's
id-bearing fields. A backward-compatible plan mode is kept for the unit-test
fixtures and fails identically when plan evidence is present."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

JID_RE = re.compile(r"^J-\d{8}-\d{6}-\d{3}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ENTRY_HEADER = re.compile(r"^===\s+(.+?)\s+===$")
PLACEHOLDERS = {"", "--", "none", "null", "unknown", "n/a", "pending"}
ID_KEYS = ("subagent_id", "agent_id", "job_id", "agentId", "jobId", "id")

REQUIRED_ENTRY_FIELDS = {"TYPE", "SPEC", "STATUS", "PARENT", "ROOT", "DETAIL"}
ALLOWED_TYPES = {
    "USER_INPUT", "SPEC_SPEC", "SPEC_REVIEW", "ARCHITECTURE",
    "ARCHITECTURE_REVIEW", "DECOMPOSE", "TASK_REVIEW",
    "IMPLEMENTATION_PLAN", "IMPLEMENTATION_PLAN_REVIEW", "RED",
    "RED_REVIEW", "GREEN", "GREEN_REVIEW", "MERGE", "MERGE_REVIEW",
    "TASKS_COMPLETE", "REGRESSION", "REGRESSION_REVIEW", "FINAL",
    "FINAL_REVIEW", "ORCHESTRATOR_TASK_REVIEW", "ESCALATION", "DONE",
}
ALLOWED_STATUSES = {
    "COMPLETED", "PASS", "FAIL", "NEEDS_CLARIFICATION", "BLOCKED",
    "ERROR", "ESCALATED", "CANCELLED",
}
WORK_TYPES = {
    "USER_INPUT", "SPEC_SPEC", "ARCHITECTURE", "DECOMPOSE",
    "IMPLEMENTATION_PLAN", "RED", "GREEN", "MERGE", "TASKS_COMPLETE",
    "REGRESSION", "FINAL", "DONE",
}
REVIEW_TO_WORK = {
    "SPEC_REVIEW": "SPEC_SPEC",
    "ARCHITECTURE_REVIEW": "ARCHITECTURE",
    "TASK_REVIEW": "DECOMPOSE",
    "IMPLEMENTATION_PLAN_REVIEW": "IMPLEMENTATION_PLAN",
    "RED_REVIEW": "RED",
    "GREEN_REVIEW": "GREEN",
    "MERGE_REVIEW": "MERGE",
    "REGRESSION_REVIEW": "REGRESSION",
    "FINAL_REVIEW": "FINAL",
}
PLAN_REQUIRED_FIELDS = (
    "TASK_ID", "DEPENDS_ON", "DEPENDENCY_GATE", "WAVE", "PARALLEL_GROUP",
    "WRITE_SCOPE", "RED_ASSIGNMENT", "RED_COMMAND", "RED_REVIEW_ASSIGNMENT",
    "RED_REVIEW", "GREEN_ASSIGNMENT", "GREEN_REVIEW_ASSIGNMENT",
    "GREEN_REVIEW", "MERGE_ORDER", "POST_INTEGRATION_TESTS", "STOP_CONDITIONS",
)
PLAN_DASH_ALLOWED = {"DEPENDS_ON", "DEPENDENCY_GATE"}
REQUIRED_STOP_CONDITIONS = {
    "FAIL", "NEEDS_CLARIFICATION", "BLOCKED", "INVALID_RED",
    "ADVISOR_BLOCKER", "CONFLICT",
}


@dataclass(frozen=True)
class JournalEntry:
    jid: str
    fields: dict[str, str]

    @property
    def event_type(self) -> str:
        return self.fields.get("TYPE", "")

    @property
    def status(self) -> str:
        return self.fields.get("STATUS", "")

    @property
    def parent(self) -> str:
        return self.fields.get("PARENT", "")

    @property
    def root(self) -> str:
        return self.fields.get("ROOT", "")

    @property
    def task_id(self) -> str | None:
        value = self.fields.get("TASK_ID")
        return value if value and value != "--" else None


@dataclass(frozen=True)
class PlanRow:
    heading: str
    fields: dict[str, str]

    @property
    def task_id(self) -> str:
        return self.fields["TASK_ID"]

    @property
    def wave(self) -> int:
        return int(self.fields["WAVE"])

    @property
    def merge_order(self) -> int:
        return int(self.fields["MERGE_ORDER"])


class EvidenceError(ValueError):
    pass


def parse_journal(text: str) -> list[JournalEntry]:
    entries: list[JournalEntry] = []
    current_jid: str | None = None
    current_fields: dict[str, str] = {}

    def finish() -> None:
        nonlocal current_jid, current_fields
        if current_jid is not None:
            entries.append(JournalEntry(current_jid, dict(current_fields)))
        current_jid = None
        current_fields = {}

    for raw in text.splitlines():
        line = raw.strip()
        header = ENTRY_HEADER.match(line)
        if header:
            finish()
            current_jid = header.group(1)
            continue
        if current_jid is None or not line:
            continue
        if ":" not in line:
            raise EvidenceError(f"malformed journal line in {current_jid}: {raw!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key in current_fields:
            raise EvidenceError(f"duplicate field {key} in {current_jid}")
        current_fields[key] = value.strip()
    finish()
    if not entries:
        raise EvidenceError("journal contains no entries")
    return entries


def parse_plan(text: str) -> list[PlanRow]:
    rows: list[PlanRow] = []
    heading: str | None = None
    fields: dict[str, str] = {}

    def finish() -> None:
        nonlocal heading, fields
        if heading is not None:
            rows.append(PlanRow(heading, dict(fields)))
        heading = None
        fields = {}

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## PLAN-"):
            finish()
            heading = line[3:].strip()
            continue
        if heading is None or not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in fields:
            raise EvidenceError(f"duplicate plan field {key} in {heading}")
        fields[key] = value.strip()
    finish()
    if not rows:
        raise EvidenceError("implementation plan has no PLAN task blocks")
    return rows


def is_real(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def scope_roots(value: str) -> list[str]:
    roots: list[str] = []
    for item in split_csv(value):
        root = re.split(r"[*?[]", item, maxsplit=1)[0].rstrip("/")
        roots.append(root or item)
    return roots


def scopes_overlap(left: str, right: str) -> bool:
    for a in scope_roots(left):
        for b in scope_roots(right):
            if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                return True
    return False


def verify_implementation_plan(path: Path) -> list[PlanRow]:
    if not path.is_file() or path.stat().st_size == 0:
        raise EvidenceError(f"missing or empty implementation plan: {path}")
    rows = parse_plan(path.read_text(encoding="utf-8"))
    by_task: dict[str, PlanRow] = {}
    merge_orders: set[int] = set()

    for row in rows:
        missing = [
            field for field in PLAN_REQUIRED_FIELDS
            if field not in row.fields
            or (field not in PLAN_DASH_ALLOWED and not is_real(row.fields.get(field)))
        ]
        if missing:
            raise EvidenceError(
                f"implementation plan row {row.heading} is missing fields: {', '.join(missing)}"
            )
        task_id = row.task_id
        if not TASK_ID_RE.fullmatch(task_id):
            raise EvidenceError(
                f"implementation plan TASK_ID must name exactly one task node: {task_id!r}"
            )
        if task_id in by_task:
            raise EvidenceError(f"implementation plan contains duplicate TASK_ID: {task_id}")
        by_task[task_id] = row
        if row.fields["RED_REVIEW"] != "REQUIRED" or row.fields["GREEN_REVIEW"] != "REQUIRED":
            raise EvidenceError(f"plan row {task_id} must require RED_REVIEW and GREEN_REVIEW")
        try:
            wave = row.wave
            merge_order = row.merge_order
        except ValueError as exc:
            raise EvidenceError(f"plan row {task_id} has a non-integer wave or merge order") from exc
        if wave < 1 or merge_order < 1:
            raise EvidenceError(f"plan row {task_id} wave and merge order must be positive")
        if merge_order in merge_orders:
            raise EvidenceError(f"duplicate MERGE_ORDER: {merge_order}")
        merge_orders.add(merge_order)
        stops = set(split_csv(row.fields["STOP_CONDITIONS"]))
        missing_stops = REQUIRED_STOP_CONDITIONS - stops
        if missing_stops:
            raise EvidenceError(
                f"plan row {task_id} is missing stop conditions: {', '.join(sorted(missing_stops))}"
            )

    for row in rows:
        dependencies = split_csv(row.fields["DEPENDS_ON"])
        if dependencies == ["--"]:
            dependencies = []
        if not dependencies:
            if row.fields["DEPENDENCY_GATE"] != "--":
                raise EvidenceError(f"plan row {row.task_id} has a gate without dependencies")
        else:
            if row.fields["DEPENDENCY_GATE"] not in {"GREEN_REVIEW", "MERGE_REVIEW"}:
                raise EvidenceError(f"plan row {row.task_id} has an invalid dependency gate")
            for dependency in dependencies:
                if dependency not in by_task:
                    raise EvidenceError(
                        f"plan row {row.task_id} depends on unknown task {dependency}"
                    )
                if row.wave <= by_task[dependency].wave:
                    raise EvidenceError(
                        f"plan row {row.task_id} must be in a later wave than {dependency}"
                    )

    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            same_parallel_group = (
                left.wave == right.wave
                and left.fields["PARALLEL_GROUP"] == right.fields["PARALLEL_GROUP"]
                and left.fields["PARALLEL_GROUP"] != "SERIAL"
            )
            if same_parallel_group and scopes_overlap(
                left.fields["WRITE_SCOPE"], right.fields["WRITE_SCOPE"]
            ):
                raise EvidenceError(
                    f"parallel plan rows {left.task_id} and {right.task_id} have overlapping write scopes"
                )
    return rows


def find_gate(
    ordered: list[JournalEntry], index_by_jid: dict[str, int], review: JournalEntry
) -> JournalEntry:
    gates = [
        entry for entry in ordered
        if entry.event_type == "ORCHESTRATOR_TASK_REVIEW" and entry.parent == review.jid
    ]
    if not gates:
        raise EvidenceError(f"missing process gate after {review.event_type} {review.jid}")
    gate = gates[-1]
    if gate.status != "PASS":
        raise EvidenceError(f"process gate after {review.jid} is {gate.status}, expected PASS")
    if index_by_jid[gate.jid] <= index_by_jid[review.jid]:
        raise EvidenceError(f"process gate {gate.jid} does not follow review {review.jid}")
    if review.task_id and gate.task_id != review.task_id:
        raise EvidenceError(f"process gate {gate.jid} has the wrong TASK_ID")
    return gate


def latest_review(
    ordered: list[JournalEntry], event_type: str, task_id: str | None = None
) -> JournalEntry:
    matches = [
        entry for entry in ordered
        if entry.event_type == event_type and (task_id is None or entry.task_id == task_id)
    ]
    if not matches:
        suffix = f" for task {task_id}" if task_id else ""
        raise EvidenceError(f"missing required journal event: {event_type}{suffix}")
    review = matches[-1]
    if review.status != "PASS":
        suffix = f" for task {task_id}" if task_id else ""
        raise EvidenceError(f"latest {event_type}{suffix} is {review.status}, expected PASS")
    return review


def reviewed_stage(
    ordered: list[JournalEntry], by_jid: dict[str, JournalEntry], index_by_jid: dict[str, int],
    review_type: str, task_id: str | None = None,
) -> tuple[JournalEntry, JournalEntry, JournalEntry]:
    review = latest_review(ordered, review_type, task_id)
    work = by_jid.get(review.parent)
    expected_work = REVIEW_TO_WORK[review_type]
    if work is None or work.event_type != expected_work:
        raise EvidenceError(f"{review_type} {review.jid} does not directly review {expected_work}")
    if work.status != "COMPLETED":
        raise EvidenceError(f"reviewed work {work.jid} is {work.status}, expected COMPLETED")
    if task_id and work.task_id != task_id:
        raise EvidenceError(f"{review_type} {review.jid} reviews the wrong task")
    if index_by_jid[work.jid] >= index_by_jid[review.jid]:
        raise EvidenceError(f"review {review.jid} precedes its work {work.jid}")
    gate = find_gate(ordered, index_by_jid, review)
    return work, review, gate


def _validate_common_entries(
    ordered: list[JournalEntry],
) -> tuple[dict[str, JournalEntry], dict[str, int], JournalEntry]:
    by_jid: dict[str, JournalEntry] = {}
    index_by_jid: dict[str, int] = {}
    task_tree: dict[str, tuple[str, str]] = {}

    for index, entry in enumerate(ordered):
        if not JID_RE.fullmatch(entry.jid):
            raise EvidenceError(f"invalid journal id: {entry.jid}")
        if entry.jid in by_jid:
            raise EvidenceError(f"duplicate journal id: {entry.jid}")
        missing = REQUIRED_ENTRY_FIELDS - entry.fields.keys()
        if missing:
            raise EvidenceError(f"entry {entry.jid} is missing fields: {', '.join(sorted(missing))}")
        if entry.event_type not in ALLOWED_TYPES:
            raise EvidenceError(f"entry {entry.jid} has invalid TYPE: {entry.event_type}")
        if entry.status not in ALLOWED_STATUSES:
            raise EvidenceError(f"entry {entry.jid} has invalid STATUS: {entry.status}")
        if entry.event_type in WORK_TYPES and entry.status != "COMPLETED":
            raise EvidenceError(f"work entry {entry.jid} must use STATUS: COMPLETED")
        if not is_real(entry.fields["SPEC"]) or not is_real(entry.fields["DETAIL"]):
            raise EvidenceError(f"entry {entry.jid} has an empty SPEC or DETAIL")

        if entry.event_type == "USER_INPUT":
            if entry.parent != "--" or entry.root != entry.jid:
                raise EvidenceError(f"USER_INPUT {entry.jid} must be its own root with no parent")
        else:
            parent = by_jid.get(entry.parent)
            if parent is None:
                raise EvidenceError(f"entry {entry.jid} references a missing or future parent")
            if entry.root != parent.root:
                raise EvidenceError(f"entry {entry.jid} does not preserve its parent root")

        for dependency in split_csv(entry.fields.get("DEPENDS", "")):
            if dependency == "--":
                continue
            if dependency not in by_jid:
                raise EvidenceError(f"entry {entry.jid} has a missing or future DEPENDS jid")

        task_fields = [
            entry.fields.get("TASK_ID"), entry.fields.get("PARENT_TASK_ID"),
            entry.fields.get("ROOT_USER_INPUT_ID"),
        ]
        if any(value is not None for value in task_fields):
            if not all(value is not None and value != "" for value in task_fields):
                raise EvidenceError(f"entry {entry.jid} has incomplete task-tree fields")
            assert entry.task_id is not None
            parent_task = entry.fields["PARENT_TASK_ID"]
            root_task = entry.fields["ROOT_USER_INPUT_ID"]
            if parent_task == "--" and root_task != entry.task_id:
                raise EvidenceError(f"root task {entry.task_id} must identify itself as root")
            shape = (parent_task, root_task)
            previous = task_tree.setdefault(entry.task_id, shape)
            if previous != shape:
                raise EvidenceError(f"task-tree fields changed for task {entry.task_id}")

        by_jid[entry.jid] = entry
        index_by_jid[entry.jid] = index

    user_inputs = [entry for entry in ordered if entry.event_type == "USER_INPUT"]
    if not user_inputs:
        raise EvidenceError("missing required journal event: USER_INPUT")
    root = user_inputs[0]

    latest_by_stream: dict[tuple[str, str], JournalEntry] = {}
    for entry in ordered:
        if entry.event_type in REVIEW_TO_WORK:
            key = entry.task_id or entry.root
            latest_by_stream[(entry.event_type, key)] = entry
    for (event_type, key), entry in latest_by_stream.items():
        if entry.status != "PASS":
            raise EvidenceError(f"latest {event_type} for {key} is {entry.status}, expected PASS")

    return by_jid, index_by_jid, root


def verify_journal(entries: Iterable[JournalEntry], plan_rows: list[PlanRow]) -> None:
    ordered = list(entries)
    by_jid, index_by_jid, root = _validate_common_entries(ordered)

    spec = reviewed_stage(ordered, by_jid, index_by_jid, "SPEC_REVIEW")
    architecture = reviewed_stage(ordered, by_jid, index_by_jid, "ARCHITECTURE_REVIEW")
    tasks = reviewed_stage(ordered, by_jid, index_by_jid, "TASK_REVIEW")
    plan = reviewed_stage(ordered, by_jid, index_by_jid, "IMPLEMENTATION_PLAN_REVIEW")

    top_indices = [
        index_by_jid[root.jid],
        *(index_by_jid[item.jid] for stage in (spec, architecture, tasks, plan) for item in stage),
    ]
    if top_indices != sorted(top_indices) or len(set(top_indices)) != len(top_indices):
        raise EvidenceError("top-level workflow stages are out of order")
    plan_gate_index = index_by_jid[plan[2].jid]

    first_red = min(
        (index for index, entry in enumerate(ordered) if entry.event_type == "RED"),
        default=None,
    )
    if first_red is None:
        raise EvidenceError("missing required journal event: RED")
    if first_red <= plan_gate_index:
        raise EvidenceError("RED began before the implementation-plan review and process gate")

    merge_gates: list[tuple[int, int, str]] = []
    for row in plan_rows:
        red = reviewed_stage(ordered, by_jid, index_by_jid, "RED_REVIEW", row.task_id)
        green = reviewed_stage(ordered, by_jid, index_by_jid, "GREEN_REVIEW", row.task_id)
        merge = reviewed_stage(ordered, by_jid, index_by_jid, "MERGE_REVIEW", row.task_id)
        indices = [
            plan_gate_index,
            *(index_by_jid[item.jid] for stage in (red, green, merge) for item in stage),
        ]
        if indices != sorted(indices) or len(set(indices)) != len(indices):
            raise EvidenceError(f"task {row.task_id} has an invalid RED/GREEN/MERGE transition order")
        merge_gates.append((row.merge_order, index_by_jid[merge[2].jid], merge[2].jid))

    merge_gates.sort()
    merge_gate_indices = [item[1] for item in merge_gates]
    if merge_gate_indices != sorted(merge_gate_indices):
        raise EvidenceError("task merges do not follow IMPLEMENTATION-PLAN MERGE_ORDER")

    tasks_complete_entries = [entry for entry in ordered if entry.event_type == "TASKS_COMPLETE"]
    if not tasks_complete_entries:
        raise EvidenceError("missing required journal event: TASKS_COMPLETE")
    tasks_complete = tasks_complete_entries[-1]
    tasks_complete_index = index_by_jid[tasks_complete.jid]
    if tasks_complete_index <= max(merge_gate_indices):
        raise EvidenceError("TASKS_COMPLETE occurs before all merge review process gates")
    required_merge_gate_jids = {item[2] for item in merge_gates}
    convergence_refs = {tasks_complete.parent, *split_csv(tasks_complete.fields.get("DEPENDS", ""))}
    if not required_merge_gate_jids.issubset(convergence_refs):
        raise EvidenceError("TASKS_COMPLETE does not depend on every merge process gate")

    regression = reviewed_stage(ordered, by_jid, index_by_jid, "REGRESSION_REVIEW")
    final = reviewed_stage(ordered, by_jid, index_by_jid, "FINAL_REVIEW")
    done_entries = [entry for entry in ordered if entry.event_type == "DONE"]
    if not done_entries:
        raise EvidenceError("missing required journal event: DONE")
    done = done_entries[-1]
    final_indices = [
        tasks_complete_index,
        *(index_by_jid[item.jid] for stage in (regression, final) for item in stage),
        index_by_jid[done.jid],
    ]
    if final_indices != sorted(final_indices) or len(set(final_indices)) != len(final_indices):
        raise EvidenceError("regression, final review, and DONE are out of order")
    if ordered[-1].jid != done.jid:
        raise EvidenceError("DONE must be the final journal entry")
    if done.parent != final[2].jid:
        raise EvidenceError("DONE must directly follow the final process gate")


def verify_journal_plan_skip(entries: Iterable[JournalEntry]) -> list[str]:
    """Validate a plan-skip journal and return its task ids (sourced from the
    journal task-tree fields, corresponding to TASKS.md). No IMPLEMENTATION-PLAN.md
    file, IMPLEMENTATION_PLAN, or IMPLEMENTATION_PLAN_REVIEW entries are required;
    RED must begin only after the TASK_REVIEW process gate."""
    ordered = list(entries)
    by_jid, index_by_jid, root = _validate_common_entries(ordered)

    spec = reviewed_stage(ordered, by_jid, index_by_jid, "SPEC_REVIEW")
    architecture = reviewed_stage(ordered, by_jid, index_by_jid, "ARCHITECTURE_REVIEW")
    tasks = reviewed_stage(ordered, by_jid, index_by_jid, "TASK_REVIEW")

    top_indices = [
        index_by_jid[root.jid],
        *(index_by_jid[item.jid] for stage in (spec, architecture, tasks) for item in stage),
    ]
    if top_indices != sorted(top_indices) or len(set(top_indices)) != len(top_indices):
        raise EvidenceError("top-level workflow stages are out of order")
    task_gate_index = index_by_jid[tasks[2].jid]

    first_red = min(
        (index for index, entry in enumerate(ordered) if entry.event_type == "RED"),
        default=None,
    )
    if first_red is None:
        raise EvidenceError("missing required journal event: RED")
    if first_red <= task_gate_index:
        raise EvidenceError("RED began before the task review and process gate")

    task_ids = sorted({
        entry.task_id for entry in ordered
        if entry.event_type in {"RED", "GREEN", "MERGE"} and entry.task_id is not None
    })
    if not task_ids:
        raise EvidenceError("missing required journal event: no task branch has a task id")

    merge_gates: list[tuple[int, str]] = []
    for task_id in task_ids:
        red = reviewed_stage(ordered, by_jid, index_by_jid, "RED_REVIEW", task_id)
        green = reviewed_stage(ordered, by_jid, index_by_jid, "GREEN_REVIEW", task_id)
        merge = reviewed_stage(ordered, by_jid, index_by_jid, "MERGE_REVIEW", task_id)
        indices = [
            task_gate_index,
            *(index_by_jid[item.jid] for stage in (red, green, merge) for item in stage),
        ]
        if indices != sorted(indices) or len(set(indices)) != len(indices):
            raise EvidenceError(f"task {task_id} has an invalid RED/GREEN/MERGE transition order")
        merge_gates.append((index_by_jid[merge[2].jid], merge[2].jid))

    merge_gate_indices = [item[0] for item in merge_gates]
    tasks_complete_entries = [entry for entry in ordered if entry.event_type == "TASKS_COMPLETE"]
    if not tasks_complete_entries:
        raise EvidenceError("missing required journal event: TASKS_COMPLETE")
    tasks_complete = tasks_complete_entries[-1]
    tasks_complete_index = index_by_jid[tasks_complete.jid]
    if tasks_complete_index <= max(merge_gate_indices):
        raise EvidenceError("TASKS_COMPLETE occurs before all merge review process gates")
    required_merge_gate_jids = {item[1] for item in merge_gates}
    convergence_refs = {tasks_complete.parent, *split_csv(tasks_complete.fields.get("DEPENDS", ""))}
    if not required_merge_gate_jids.issubset(convergence_refs):
        raise EvidenceError("TASKS_COMPLETE does not depend on every merge process gate")

    regression = reviewed_stage(ordered, by_jid, index_by_jid, "REGRESSION_REVIEW")
    final = reviewed_stage(ordered, by_jid, index_by_jid, "FINAL_REVIEW")
    done_entries = [entry for entry in ordered if entry.event_type == "DONE"]
    if not done_entries:
        raise EvidenceError("missing required journal event: DONE")
    done = done_entries[-1]
    final_indices = [
        tasks_complete_index,
        *(index_by_jid[item.jid] for stage in (regression, final) for item in stage),
        index_by_jid[done.jid],
    ]
    if final_indices != sorted(final_indices) or len(set(final_indices)) != len(final_indices):
        raise EvidenceError("regression, final review, and DONE are out of order")
    if ordered[-1].jid != done.jid:
        raise EvidenceError("DONE must be the final journal entry")
    if done.parent != final[2].jid:
        raise EvidenceError("DONE must directly follow the final process gate")
    return task_ids


def load_jsonl(path: Path, label: str) -> list[dict[str, object]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise EvidenceError(f"missing or empty {label}: {path}")
    records: list[dict[str, object]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EvidenceError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise EvidenceError(f"non-object JSONL record at {path}:{line_number}")
        records.append(value)
    if not records:
        raise EvidenceError(f"{label} has no records: {path}")
    return records


def nested_dicts(value: object) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nested_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_dicts(child)


def _collect_identifiers(events: Iterable[dict[str, object]]) -> tuple[set[str], set[str]]:
    agents: set[str] = set()
    jobs: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        for obj in nested_dicts(event):
            tasks = obj.get("tasks")
            if isinstance(tasks, list):
                for task in tasks:
                    if isinstance(task, dict) and is_real(task.get("name")):
                        name = str(task["name"])
                        agents.add(name)
                        jobs.add(name)
            progress = obj.get("progress")
            if isinstance(progress, list):
                for item in progress:
                    if isinstance(item, dict) and is_real(item.get("id")):
                        identifier = str(item["id"])
                        agents.add(identifier)
                        jobs.add(identifier)
            for key in ID_KEYS:
                if is_real(obj.get(key)):
                    identifier = str(obj[key])
                    agents.add(identifier)
                    jobs.add(identifier)
    if not agents or not jobs:
        raise EvidenceError("raw delegation events contain no task agent/job identifiers")
    return agents, jobs


def collect_event_ids(events: Iterable[dict[str, object]]) -> tuple[set[str], set[str]]:
    """Collect agent and job identifiers referenced by a delegation/tool-event stream.

    The events file is a generic JSONL of delegation/tool-event records; no
    record type or event/tool name is required. Identifiers are collected from
    any id-bearing field (subagent_id, agent_id, job_id, agentId, jobId, id)
    and from nested task lists (tasks[].name, progress[].id) when present."""
    return _collect_identifiers(events)


def collect_delegation_ids(events: Iterable[dict[str, object]]) -> tuple[set[str], set[str]]:
    """Collect implementer/reviewer identifiers from a delegation record stream.

    Schema-agnostic: no literal record type is assumed; every id-bearing field
    of each record is collected. An empty stream or a stream with no real
    identifiers is an error so that invented/absent identities cannot silently
    pass."""
    return _collect_identifiers(events)


def complete_runtime_row(row: dict[str, object], kind: str, role: str) -> bool:
    return (
        row.get("task_kind") == kind
        and row.get("role") == role
        and is_real(row.get("task_id"))
        and is_real(row.get("agent_id"))
        and is_real(row.get("job_id"))
        and is_real(row.get("prompt"))
        and is_real(row.get("summary"))
    )


def require_sha(value: object, label: str) -> str:
    text = str(value or "")
    if not SHA_RE.fullmatch(text):
        raise EvidenceError(f"{label} is missing a real commit SHA")
    return text.lower()


def find_runtime_pair(
    rows: list[dict[str, object]], implementer_kind: str, review_kind: str,
    task_id: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    implementers = [
        row for row in rows
        if complete_runtime_row(row, implementer_kind, "implementer")
        and (task_id is None or row.get("task_id") == task_id)
    ]
    if not implementers:
        suffix = f" for task {task_id}" if task_id else ""
        raise EvidenceError(f"missing complete {implementer_kind} runtime record{suffix}")
    implementer = implementers[-1]
    commit = require_sha(implementer.get("commit"), f"{implementer_kind} runtime record")

    reviewers = [
        row for row in rows
        if complete_runtime_row(row, review_kind, "reviewer")
        and (task_id is None or row.get("task_id") == task_id)
        and row.get("verdict") == "PASS"
        and str(row.get("reviewed_commit", "")).lower() == commit
    ]
    if not reviewers:
        suffix = f" for task {task_id}" if task_id else ""
        raise EvidenceError(
            f"missing passing {review_kind} runtime record for exact commit {commit}{suffix}"
        )
    reviewer = reviewers[-1]
    if reviewer.get("agent_id") == implementer.get("agent_id"):
        raise EvidenceError(f"{review_kind} reused the implementer agent identity")
    if reviewer.get("job_id") == implementer.get("job_id"):
        raise EvidenceError(f"{review_kind} reused the implementer job identity")
    return implementer, reviewer


def verify_runtime(
    rows: Iterable[dict[str, object]], events: Iterable[dict[str, object]],
    plan_rows: list[PlanRow],
) -> None:
    records = list(rows)
    raw_agents, raw_jobs = collect_event_ids(events)
    for row in records:
        if is_real(row.get("agent_id")) and str(row["agent_id"]) not in raw_agents:
            raise EvidenceError(f"runtime agent_id not found in raw delegation events: {row['agent_id']}")
        if is_real(row.get("job_id")) and str(row["job_id"]) not in raw_jobs:
            raise EvidenceError(f"runtime job_id not found in raw delegation events: {row['job_id']}")

    find_runtime_pair(records, "IMPLEMENTATION_PLAN", "IMPLEMENTATION_PLAN_REVIEW")
    for plan_row in plan_rows:
        find_runtime_pair(records, "RED", "RED_REVIEW", plan_row.task_id)
        find_runtime_pair(records, "GREEN", "GREEN_REVIEW", plan_row.task_id)
        find_runtime_pair(records, "MERGE", "MERGE_REVIEW", plan_row.task_id)


def verify_runtime_delegations(
    rows: Iterable[dict[str, object]], events: Iterable[dict[str, object]],
    task_ids: list[str],
) -> None:
    """Verify runtime evidence against the delegation event stream: every real
    agent/job id in the orchestrator log must resolve to a collected identifier
    from the events file, and each reviewed task branch must have a passing
    implementer/reviewer pair with distinct identities. Task ids come from the
    journal/TASKS.md."""
    records = list(rows)
    known_agents, known_jobs = collect_delegation_ids(events)
    for row in records:
        if is_real(row.get("agent_id")) and str(row["agent_id"]) not in known_agents:
            raise EvidenceError(f"runtime agent_id not found in delegation events: {row['agent_id']}")
        if is_real(row.get("job_id")) and str(row["job_id"]) not in known_jobs:
            raise EvidenceError(f"runtime job_id not found in delegation events: {row['job_id']}")

    for task_id in task_ids:
        find_runtime_pair(records, "RED", "RED_REVIEW", task_id)
        find_runtime_pair(records, "GREEN", "GREEN_REVIEW", task_id)
        find_runtime_pair(records, "MERGE", "MERGE_REVIEW", task_id)


def verify(journal_path: Path, orchestrator_log_path: Path, events_path: Path) -> None:
    if not journal_path.is_file() or journal_path.stat().st_size == 0:
        raise EvidenceError(f"missing or empty journal: {journal_path}")
    plan_path = journal_path.with_name("IMPLEMENTATION-PLAN.md")
    plan_mode = plan_path.is_file() and plan_path.stat().st_size > 0
    entries = parse_journal(journal_path.read_text(encoding="utf-8"))
    if plan_mode:
        # Plan mode: backward-compatible validation when a plan file is present.
        plan_rows = verify_implementation_plan(plan_path)
        verify_journal(entries, plan_rows)
        verify_runtime(
            load_jsonl(orchestrator_log_path, "orchestrator log"),
            load_jsonl(events_path, "raw delegation event stream"),
            plan_rows,
        )
    else:
        # Plan-skip mode: no plan file/stage or gate required; task ids sourced
        # from the journal task-tree (TASKS.md); identities resolved from the
        # delegation events file (the id-bearing fields of each record).
        task_ids = verify_journal_plan_skip(entries)
        verify_runtime_delegations(
            load_jsonl(orchestrator_log_path, "orchestrator log"),
            load_jsonl(events_path, "delegation events"),
            task_ids,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("journal", type=Path)
    parser.add_argument("orchestrator_log", type=Path)
    parser.add_argument("events", type=Path)
    args = parser.parse_args()
    try:
        verify(args.journal, args.orchestrator_log, args.events)
    except EvidenceError as exc:
        print(f"evidence verification failed: {exc}")
        return 1
    print("evidence verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
