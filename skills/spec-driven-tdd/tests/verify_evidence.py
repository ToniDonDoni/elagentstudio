#!/usr/bin/env python3
"""Verify committed Spec-Driven TDD journal and OMP handoff evidence."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ENTRY_HEADER = re.compile(r"^===\s+(.+?)\s+===$")
PLACEHOLDERS = {"", "--", "none", "null", "unknown", "n/a", "pending"}

REQUIRED_LATEST_STATUS = {
    "USER_INPUT": "COMPLETED",
    "SPEC_REVIEW": "PASS",
    "ARCHITECTURE_REVIEW": "PASS",
    "TASK_REVIEW": "PASS",
    "RED_REVIEW": "PASS",
    "GREEN_REVIEW": "PASS",
    "MERGE": "COMPLETED",
    "MERGE_REVIEW": "PASS",
    "REGRESSION_REVIEW": "PASS",
    "FINAL_REVIEW": "PASS",
    "DONE": "COMPLETED",
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


class EvidenceError(ValueError):
    pass


def parse_journal(text: str) -> list[JournalEntry]:
    entries: list[JournalEntry] = []
    current_jid: str | None = None
    current_fields: dict[str, str] = {}

    def finish() -> None:
        nonlocal current_jid, current_fields
        if current_jid is None:
            return
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
        if current_jid is None or not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_fields[key.strip()] = value.strip()
    finish()

    if not entries:
        raise EvidenceError("journal contains no entries")
    return entries


def is_real(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def verify_journal(entries: Iterable[JournalEntry]) -> None:
    ordered = list(entries)
    latest: dict[str, JournalEntry] = {}
    seen_jids: set[str] = set()

    for entry in ordered:
        if entry.jid in seen_jids:
            raise EvidenceError(f"duplicate journal id: {entry.jid}")
        seen_jids.add(entry.jid)
        if not entry.event_type:
            raise EvidenceError(f"entry {entry.jid} has no TYPE")
        if not entry.status:
            raise EvidenceError(f"entry {entry.jid} has no STATUS")
        latest[entry.event_type] = entry

    for event_type, expected_status in REQUIRED_LATEST_STATUS.items():
        entry = latest.get(event_type)
        if entry is None:
            raise EvidenceError(f"missing required journal event: {event_type}")
        if entry.status != expected_status:
            raise EvidenceError(
                f"latest {event_type} status is {entry.status!r}, expected {expected_status!r}"
            )

    gates = [
        entry
        for entry in ordered
        if entry.event_type == "ORCHESTRATOR_TASK_REVIEW" and entry.status == "PASS"
    ]
    if not gates:
        raise EvidenceError("missing passing ORCHESTRATOR_TASK_REVIEW evidence")

    merge_index = max(i for i, entry in enumerate(ordered) if entry.event_type == "MERGE")
    merge_review_index = max(i for i, entry in enumerate(ordered) if entry.event_type == "MERGE_REVIEW")
    done_index = max(i for i, entry in enumerate(ordered) if entry.event_type == "DONE")
    if not merge_index < merge_review_index < done_index:
        raise EvidenceError("MERGE_REVIEW must occur after MERGE and before DONE")


def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise EvidenceError(f"missing or empty runtime evidence log: {path}")
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
        raise EvidenceError(f"runtime evidence log has no records: {path}")
    return records


def verify_runtime(records: Iterable[dict[str, object]]) -> None:
    rows = list(records)
    if not any(is_real(row.get("agent_id")) for row in rows):
        raise EvidenceError("orchestrator log has no real agent_id")
    if not any(is_real(row.get("job_id")) for row in rows):
        raise EvidenceError("orchestrator log has no real job_id")
    commits = [str(row.get("commit", "")) for row in rows]
    if not any(re.fullmatch(r"[0-9a-fA-F]{7,40}", commit) for commit in commits):
        raise EvidenceError("orchestrator log has no real commit SHA")
    if not any(str(row.get("role", "")) == "reviewer" for row in rows):
        raise EvidenceError("orchestrator log has no reviewer handoff/check record")
    if not any(str(row.get("task_kind", "")) == "MERGE" for row in rows):
        raise EvidenceError("orchestrator log has no MERGE handoff/check record")


def verify(journal_path: Path, orchestrator_log_path: Path) -> None:
    if not journal_path.is_file() or journal_path.stat().st_size == 0:
        raise EvidenceError(f"missing or empty journal: {journal_path}")
    verify_journal(parse_journal(journal_path.read_text(encoding="utf-8")))
    verify_runtime(load_jsonl(orchestrator_log_path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("journal", type=Path)
    parser.add_argument("orchestrator_log", type=Path)
    args = parser.parse_args()
    try:
        verify(args.journal, args.orchestrator_log)
    except EvidenceError as exc:
        print(f"evidence verification failed: {exc}")
        return 1
    print("evidence verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
