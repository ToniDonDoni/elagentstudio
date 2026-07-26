#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("verify_evidence.py")
SPEC = importlib.util.spec_from_file_location("verify_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
verify_evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verify_evidence
SPEC.loader.exec_module(verify_evidence)


def entry(index: int, event_type: str, status: str) -> str:
    return "\n".join(
        [
            f"=== J-20260726-000000-{index:03d} ===",
            f"TYPE: {event_type}",
            "SPEC: SPEC-1",
            f"STATUS: {status}",
            "PARENT: --",
            f"ROOT: J-20260726-000000-{index:03d}",
            "DETAIL: test fixture",
            "",
        ]
    )


def valid_journal() -> str:
    events = [
        ("USER_INPUT", "COMPLETED"),
        ("SPEC_REVIEW", "PASS"),
        ("ARCHITECTURE_REVIEW", "PASS"),
        ("TASK_REVIEW", "PASS"),
        ("IMPLEMENTATION_PLAN", "COMPLETED"),
        ("IMPLEMENTATION_PLAN_REVIEW", "PASS"),
        ("RED_REVIEW", "PASS"),
        ("GREEN_REVIEW", "PASS"),
        ("ORCHESTRATOR_TASK_REVIEW", "PASS"),
        ("MERGE", "COMPLETED"),
        ("MERGE_REVIEW", "PASS"),
        ("REGRESSION_REVIEW", "PASS"),
        ("FINAL_REVIEW", "PASS"),
        ("DONE", "COMPLETED"),
    ]
    return "".join(entry(i + 1, kind, status) for i, (kind, status) in enumerate(events))


def valid_plan() -> str:
    return "\n".join(
        [
            "# Implementation Plan",
            "",
            "TASK_ID: T010",
            "WAVE: 1",
            "RED_ASSIGNMENT: implementer-red-T010",
            "RED: required",
            "RED_REVIEW: required",
            "GREEN_ASSIGNMENT: implementer-green-T010",
            "GREEN: required",
            "GREEN_REVIEW: required",
            "MERGE_ORDER: 1",
            "",
        ]
    )


def valid_runtime() -> str:
    rows = [
        {
            "event": "HANDOFF",
            "role": "implementer",
            "task_kind": "IMPLEMENTATION_PLAN",
            "agent_id": "agent-plan-1",
            "job_id": "job-plan-1",
            "commit": "abcdeff1234567",
        },
        {
            "event": "HANDOFF",
            "role": "reviewer",
            "task_kind": "IMPLEMENTATION_PLAN_REVIEW",
            "agent_id": "agent-plan-review-1",
            "job_id": "job-plan-review-1",
            "commit": "abcdeff1234567",
        },
        {
            "event": "HANDOFF",
            "role": "implementer",
            "task_kind": "MERGE",
            "agent_id": "agent-merge-1",
            "job_id": "job-merge-1",
            "commit": "abcdef1234567",
        },
        {
            "event": "CHECK",
            "role": "reviewer",
            "task_kind": "MERGE_REVIEW",
            "agent_id": "agent-review-1",
            "job_id": "job-review-1",
            "commit": "abcdef1234567",
        },
    ]
    return "\n".join(json.dumps(row) for row in rows) + "\n"


class EvidenceVerifierTests(unittest.TestCase):
    def run_verify(self, journal: str, runtime: str, plan: str | None = None) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            journal_path = root / "JOURNAL_SDD_TDD_SKILL.log"
            runtime_path = root / "orchestrator.log"
            plan_path = root / "IMPLEMENTATION-PLAN.md"
            journal_path.write_text(journal, encoding="utf-8")
            runtime_path.write_text(runtime, encoding="utf-8")
            if plan is not None:
                plan_path.write_text(plan, encoding="utf-8")
            verify_evidence.verify(journal_path, runtime_path)

    def test_accepts_complete_evidence(self) -> None:
        self.run_verify(valid_journal(), valid_runtime(), valid_plan())

    def test_fails_when_implementation_plan_is_missing(self) -> None:
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "implementation plan"):
            self.run_verify(valid_journal(), valid_runtime())

    def test_fails_when_plan_review_evidence_is_missing(self) -> None:
        journal = valid_journal().replace(
            entry(6, "IMPLEMENTATION_PLAN_REVIEW", "PASS"), ""
        )
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "IMPLEMENTATION_PLAN_REVIEW"):
            self.run_verify(journal, valid_runtime(), valid_plan())

    def test_fails_when_plan_coalesces_task_ids(self) -> None:
        plan = valid_plan().replace("TASK_ID: T010", "TASK_ID: T010,T020")
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "exactly one task node"):
            self.run_verify(valid_journal(), valid_runtime(), plan)

    def test_fails_when_merge_evidence_is_missing(self) -> None:
        journal = valid_journal().replace(entry(10, "MERGE", "COMPLETED"), "")
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "MERGE"):
            self.run_verify(journal, valid_runtime(), valid_plan())

    def test_fails_when_required_review_is_fail(self) -> None:
        journal = valid_journal().replace(
            entry(13, "FINAL_REVIEW", "PASS"), entry(13, "FINAL_REVIEW", "FAIL")
        )
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "FINAL_REVIEW"):
            self.run_verify(journal, valid_runtime(), valid_plan())

    def test_fails_when_runtime_plan_review_is_missing(self) -> None:
        runtime_rows = [
            json.loads(line) for line in valid_runtime().splitlines() if line.strip()
        ]
        runtime = "\n".join(
            json.dumps(row)
            for row in runtime_rows
            if row["task_kind"] != "IMPLEMENTATION_PLAN_REVIEW"
        )
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError, "IMPLEMENTATION_PLAN_REVIEW"
        ):
            self.run_verify(valid_journal(), runtime, valid_plan())

    def test_fails_when_runtime_ids_are_missing(self) -> None:
        runtime = json.dumps(
            {
                "event": "HANDOFF",
                "role": "reviewer",
                "task_kind": "MERGE",
                "agent_id": "--",
                "job_id": "--",
                "commit": "--",
            }
        )
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "agent_id"):
            self.run_verify(valid_journal(), runtime, valid_plan())


if __name__ == "__main__":
    unittest.main()
