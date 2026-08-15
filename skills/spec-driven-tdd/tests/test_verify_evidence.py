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


class Fixture:
    def __init__(self) -> None:
        self.entries: list[dict[str, str]] = []
        self.counter = 0
        self.root = ""

    def add(
        self, event_type: str, status: str, parent: str | None = None,
        *, task_id: str | None = None, depends: list[str] | None = None,
    ) -> str:
        self.counter += 1
        jid = f"J-20260726-000000-{self.counter:03d}"
        if event_type == "USER_INPUT":
            parent = "--"
            self.root = jid
        elif parent is None:
            parent = self.entries[-1]["JID"]
        row = {
            "JID": jid,
            "TYPE": event_type,
            "SPEC": "SPEC-1",
            "STATUS": status,
            "PARENT": parent,
            "ROOT": self.root,
            "DETAIL": f"fixture {event_type}",
        }
        if depends:
            row["DEPENDS"] = ", ".join(depends)
        if task_id:
            row["TASK_ID"] = task_id
            row["PARENT_TASK_ID"] = "--"
            row["ROOT_USER_INPUT_ID"] = task_id
        self.entries.append(row)
        return jid

    def text(self) -> str:
        chunks: list[str] = []
        for row in self.entries:
            chunks.append(f"=== {row['JID']} ===")
            for key, value in row.items():
                if key != "JID":
                    chunks.append(f"{key}: {value}")
            chunks.append("")
        return "\n".join(chunks)


def reviewed(
    fx: Fixture, work_type: str, review_type: str, parent: str,
    task: str | None = None,
):
    work = fx.add(work_type, "COMPLETED", parent, task_id=task)
    review = fx.add(review_type, "PASS", work, task_id=task)
    gate = fx.add("ORCHESTRATOR_TASK_REVIEW", "PASS", review, task_id=task)
    return work, review, gate


def valid_journal() -> str:
    fx = Fixture()
    user = fx.add("USER_INPUT", "COMPLETED")
    _, _, spec_gate = reviewed(fx, "SPEC_SPEC", "SPEC_REVIEW", user)
    _, _, arch_gate = reviewed(fx, "ARCHITECTURE", "ARCHITECTURE_REVIEW", spec_gate)
    _, _, task_gate = reviewed(fx, "DECOMPOSE", "TASK_REVIEW", arch_gate)
    _, _, plan_gate = reviewed(
        fx, "IMPLEMENTATION_PLAN", "IMPLEMENTATION_PLAN_REVIEW", task_gate
    )
    _, _, red_gate = reviewed(fx, "RED", "RED_REVIEW", plan_gate, "T1")
    _, _, green_gate = reviewed(fx, "GREEN", "GREEN_REVIEW", red_gate, "T1")
    _, _, merge_gate = reviewed(fx, "MERGE", "MERGE_REVIEW", green_gate, "T1")
    complete = fx.add("TASKS_COMPLETE", "COMPLETED", merge_gate, depends=[merge_gate])
    _, _, regression_gate = reviewed(fx, "REGRESSION", "REGRESSION_REVIEW", complete)
    _, _, final_gate = reviewed(fx, "FINAL", "FINAL_REVIEW", regression_gate)
    fx.add("DONE", "COMPLETED", final_gate)
    return fx.text()


def valid_plan() -> str:
    return "\n".join([
        "# Implementation Plan", "", "## PLAN-T1", "TASK_ID: T1",
        "DEPENDS_ON: --", "DEPENDENCY_GATE: --", "WAVE: 1",
        "PARALLEL_GROUP: WAVE-1", "WRITE_SCOPE: tests/t1/**, src/t1/**",
        "RED_ASSIGNMENT: Agent-1", "RED_COMMAND: npm test -- t1",
        "RED_REVIEW_ASSIGNMENT: Reviewer-1", "RED_REVIEW: REQUIRED",
        "GREEN_ASSIGNMENT: Agent-1", "GREEN_REVIEW_ASSIGNMENT: Reviewer-1",
        "GREEN_REVIEW: REQUIRED", "MERGE_ORDER: 1",
        "POST_INTEGRATION_TESTS: npm test -- t1",
        "STOP_CONDITIONS: FAIL, NEEDS_CLARIFICATION, BLOCKED, INVALID_RED, ADVISOR_BLOCKER, CONFLICT",
        "",
    ])


def runtime_row(
    role: str, kind: str, agent: str, commit: str, task: str,
) -> dict[str, str]:
    row = {
        "timestamp": "2026-07-26T00:00:00Z", "event": "CHECK",
        "role": role, "task_kind": kind, "task_id": task,
        "agent_id": agent, "job_id": agent, "commit": commit,
        "head": commit, "summary": f"{kind} fixture", "prompt": f"run {kind}",
    }
    if role == "reviewer":
        row["verdict"] = "PASS"
        row["reviewed_commit"] = commit
    return row


def valid_runtime_rows() -> list[dict[str, str]]:
    return [
        runtime_row("implementer", "IMPLEMENTATION_PLAN", "PlanImpl", "aaa1111", "PLAN"),
        runtime_row("reviewer", "IMPLEMENTATION_PLAN_REVIEW", "PlanReview", "aaa1111", "PLAN"),
        runtime_row("implementer", "RED", "RedImpl", "bbb2222", "T1"),
        runtime_row("reviewer", "RED_REVIEW", "RedReview", "bbb2222", "T1"),
        runtime_row("implementer", "GREEN", "GreenImpl", "ccc3333", "T1"),
        runtime_row("reviewer", "GREEN_REVIEW", "GreenReview", "ccc3333", "T1"),
        runtime_row("implementer", "MERGE", "MergeImpl", "ddd4444", "T1"),
        runtime_row("reviewer", "MERGE_REVIEW", "MergeReview", "ddd4444", "T1"),
    ]


def valid_runtime() -> str:
    return "\n".join(json.dumps(row) for row in valid_runtime_rows()) + "\n"


def valid_events() -> str:
    names = [row["agent_id"] for row in valid_runtime_rows()]
    event = {
        "event": "task_execution",
        "args": {"tasks": [{"name": name} for name in names]},
        "result": {"details": {"progress": [{"id": name} for name in names]}},
    }
    return json.dumps(event) + "\n"



# ---- Plan-skip proving fixtures (RED for T2) ---------------------------------
# These fixtures model the plan-skip verification mode: the journal has NO
# IMPLEMENTATION_PLAN / IMPLEMENTATION_PLAN_REVIEW stage and NO
# IMPLEMENTATION-PLAN.md file, RED starts right after the TASK_REVIEW process
# gate, and implementer/reviewer identities are resolved from the delegation
# events file, a JSONL of delegation records whose id-bearing fields are
# collected (schema-agnostically, without requiring any record type).


def plan_skip_journal() -> str:
    fx = Fixture()
    user = fx.add("USER_INPUT", "COMPLETED")
    _, _, spec_gate = reviewed(fx, "SPEC_SPEC", "SPEC_REVIEW", user)
    _, _, arch_gate = reviewed(fx, "ARCHITECTURE", "ARCHITECTURE_REVIEW", spec_gate)
    _, _, task_gate = reviewed(fx, "DECOMPOSE", "TASK_REVIEW", arch_gate)
    # NO IMPLEMENTATION_PLAN / IMPLEMENTATION_PLAN_REVIEW permitted here.
    _, _, red_gate = reviewed(fx, "RED", "RED_REVIEW", task_gate, "T1")
    _, _, green_gate = reviewed(fx, "GREEN", "GREEN_REVIEW", red_gate, "T1")
    _, _, merge_gate = reviewed(fx, "MERGE", "MERGE_REVIEW", green_gate, "T1")
    complete = fx.add("TASKS_COMPLETE", "COMPLETED", merge_gate, depends=[merge_gate])
    _, _, regression_gate = reviewed(fx, "REGRESSION", "REGRESSION_REVIEW", complete)
    _, _, final_gate = reviewed(fx, "FINAL", "FINAL_REVIEW", regression_gate)
    fx.add("DONE", "COMPLETED", final_gate)
    return fx.text()


def delegation_runtime_row(
    role: str, kind: str, agent: str, commit: str, task: str,
) -> dict[str, str]:
    row = {
        "timestamp": "2026-07-26T00:00:00Z", "event": "CHECK",
        "role": role, "task_kind": kind, "task_id": task,
        "agent_id": agent, "job_id": agent, "commit": commit,
        "head": commit, "summary": f"{kind} fixture", "prompt": f"run {kind}",
    }
    if role == "reviewer":
        row["verdict"] = "PASS"
        row["reviewed_commit"] = commit
    return row


def plan_skip_runtime_rows() -> list[dict[str, str]]:
    return [
        delegation_runtime_row("implementer", "RED", "11111111-aaaa-4bbb-8ccc-000000000001", "bbb2222", "T1"),
        delegation_runtime_row("reviewer", "RED_REVIEW", "22222222-bbbb-4ccc-8ddd-000000000002", "bbb2222", "T1"),
        delegation_runtime_row("implementer", "GREEN", "33333333-cccc-4ddd-8eee-000000000003", "ccc3333", "T1"),
        delegation_runtime_row("reviewer", "GREEN_REVIEW", "44444444-dddd-4eee-8fff-000000000004", "ccc3333", "T1"),
        delegation_runtime_row("implementer", "MERGE", "55555555-eeee-4fff-8000-000000000005", "ddd4444", "T1"),
        delegation_runtime_row("reviewer", "MERGE_REVIEW", "66666666-ffff-4000-8111-000000000006", "ddd4444", "T1"),
    ]


def plan_skip_runtime() -> str:
    return "\n".join(json.dumps(row) for row in plan_skip_runtime_rows()) + "\n"


def delegation_record(agent: str, kind: str, task_kind: str) -> dict[str, str]:
    return {
        "type": "delegation",
        "agent_id": agent,
        "label": f"{task_kind} delegation",
        "kind": kind,
        "task_kind": task_kind,
    }


def plan_skip_delegation_events() -> str:
    records = []
    for row in plan_skip_runtime_rows():
        kind = "implementer" if row["role"] == "implementer" else "reviewer"
        records.append(delegation_record(row["agent_id"], kind, row["task_kind"]))
    return "\n".join(json.dumps(record) for record in records) + "\n"


def run_plan_skip(
    journal: str | None = None, runtime: str | None = None,
    events: str | None = None,
) -> None:
    # Plan-skip mode: the IMPLEMENTATION-PLAN.md file is intentionally ABSENT.
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        journal_path = root / "JOURNAL_SDD_TDD_SKILL.log"
        runtime_path = root / "orchestrator.log"
        events_path = root / "delegation-events.jsonl"
        journal_path.write_text(journal or plan_skip_journal(), encoding="utf-8")
        runtime_path.write_text(runtime or plan_skip_runtime(), encoding="utf-8")
        events_path.write_text(events or plan_skip_delegation_events(), encoding="utf-8")
        assert not (root / "IMPLEMENTATION-PLAN.md").exists()
        verify_evidence.verify(journal_path, runtime_path, events_path)


class EvidenceVerifierTests(unittest.TestCase):
    def run_verify(
        self, journal: str | None = None, runtime: str | None = None,
        plan: str | None = None, events: str | None = None,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            journal_path = root / "JOURNAL_SDD_TDD_SKILL.log"
            runtime_path = root / "orchestrator.log"
            plan_path = root / "IMPLEMENTATION-PLAN.md"
            events_path = root / "tool-events.jsonl"
            journal_path.write_text(journal or valid_journal(), encoding="utf-8")
            runtime_path.write_text(runtime or valid_runtime(), encoding="utf-8")
            plan_path.write_text(plan or valid_plan(), encoding="utf-8")
            events_path.write_text(events or valid_events(), encoding="utf-8")
            verify_evidence.verify(journal_path, runtime_path, events_path)

    def test_accepts_complete_evidence(self) -> None:
        self.run_verify()

    def test_rejects_missing_plan_row_field(self) -> None:
        plan = valid_plan().replace("RED_COMMAND: npm test -- t1\n", "")
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "missing fields: RED_COMMAND"):
            self.run_verify(plan=plan)

    def test_rejects_coalesced_task_ids(self) -> None:
        plan = valid_plan().replace("TASK_ID: T1", "TASK_ID: T1,T2")
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "exactly one task node"):
            self.run_verify(plan=plan)

    def test_rejects_red_before_plan_gate(self) -> None:
        journal = valid_journal()
        blocks = journal.split("\n\n")
        red = next(block for block in blocks if "TYPE: RED\n" in block)
        blocks.remove(red)
        red = red.replace(
            "PARENT: J-20260726-000000-013",
            "PARENT: J-20260726-000000-011",
        )
        plan_review_index = next(
            i for i, block in enumerate(blocks)
            if "TYPE: IMPLEMENTATION_PLAN_REVIEW" in block
        )
        blocks.insert(plan_review_index, red)
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "RED began before"):
            self.run_verify(journal="\n\n".join(blocks))

    def test_rejects_unresolved_failure_for_one_task(self) -> None:
        journal = valid_journal().replace(
            "TYPE: GREEN_REVIEW\nSPEC: SPEC-1\nSTATUS: PASS",
            "TYPE: GREEN_REVIEW\nSPEC: SPEC-1\nSTATUS: FAIL",
        )
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "latest GREEN_REVIEW"):
            self.run_verify(journal=journal)

    def test_rejects_missing_merge_process_gate(self) -> None:
        journal = valid_journal()
        blocks = journal.split("\n\n")
        blocks = [block for block in blocks if not (
            "TYPE: ORCHESTRATOR_TASK_REVIEW" in block
            and "PARENT: J-20260726-000000-021" in block
        )]
        blocks = [
            block.replace(
                "PARENT: J-20260726-000000-022",
                "PARENT: J-20260726-000000-021",
            ).replace(
                "DEPENDS: J-20260726-000000-022",
                "DEPENDS: J-20260726-000000-021",
            )
            for block in blocks
        ]
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "missing process gate after MERGE_REVIEW",
        ):
            self.run_verify(journal="\n\n".join(blocks))

    def test_rejects_done_before_final_review(self) -> None:
        journal = valid_journal()
        blocks = journal.split("\n\n")
        done = next(block for block in blocks if "TYPE: DONE" in block)
        blocks.remove(done)
        final_review_index = next(
            i for i, block in enumerate(blocks) if "TYPE: FINAL_REVIEW" in block
        )
        blocks.insert(final_review_index, done)
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "out of order|final journal entry|missing or future parent",
        ):
            self.run_verify(journal="\n\n".join(blocks))

    def test_rejects_malformed_journal_lineage(self) -> None:
        journal = valid_journal().replace(
            "TYPE: SPEC_REVIEW\nSPEC: SPEC-1\nSTATUS: PASS\nPARENT: J-20260726-000000-002",
            "TYPE: SPEC_REVIEW\nSPEC: SPEC-1\nSTATUS: PASS\nPARENT: --",
        )
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "missing or future parent"):
            self.run_verify(journal=journal)

    def test_rejects_invented_runtime_id(self) -> None:
        runtime = valid_runtime().replace(
            '"agent_id": "MergeReview"',
            '"agent_id": "made-up"',
        )
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "not found in raw delegation events",
        ):
            self.run_verify(runtime=runtime)

    def test_rejects_merge_review_without_pass_verdict(self) -> None:
        rows = valid_runtime_rows()
        for row in rows:
            if row["task_kind"] == "MERGE_REVIEW":
                row["verdict"] = "FAIL"
        runtime = "\n".join(json.dumps(row) for row in rows) + "\n"
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "missing passing MERGE_REVIEW",
        ):
            self.run_verify(runtime=runtime)

    def test_rejects_merge_review_for_wrong_commit(self) -> None:
        rows = valid_runtime_rows()
        for row in rows:
            if row["task_kind"] == "MERGE_REVIEW":
                row["reviewed_commit"] = "eee5555"
        runtime = "\n".join(json.dumps(row) for row in rows) + "\n"
        with self.assertRaisesRegex(verify_evidence.EvidenceError, "exact commit"):
            self.run_verify(runtime=runtime)

    def test_rejects_plan_review_with_incomplete_record(self) -> None:
        rows = valid_runtime_rows()
        for row in rows:
            if row["task_kind"] == "IMPLEMENTATION_PLAN_REVIEW":
                row.pop("job_id")
        runtime = "\n".join(json.dumps(row) for row in rows) + "\n"
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "missing passing IMPLEMENTATION_PLAN_REVIEW",
        ):
            self.run_verify(runtime=runtime)


    # ---- Plan-skip mode: delegation-based evidence tooling ----------------

    def test_plan_skip_accepts_valid_evidence_without_plan(self) -> None:
        # The verifier must ACCEPT a journal with NO IMPLEMENTATION_PLAN /
        # IMPLEMENTATION_PLAN_REVIEW entries and NO IMPLEMENTATION-PLAN.md file,
        # with RED starting right after the TASK_REVIEW gate.
        run_plan_skip()

    def test_plan_skip_rejects_invented_agent_id(self) -> None:
        # The plan-skip verifier must REJECT an implementer/reviewer agent_id
        # that is invented / absent from the delegation events file.
        runtime = plan_skip_runtime().replace(
            '"agent_id": "11111111-aaaa-4bbb-8ccc-000000000001"',
            '"agent_id": "made-up-or-absent-000000000000"',
            1,
        )
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "invented|absent|not found",
        ):
            run_plan_skip(runtime=runtime)

    def test_plan_skip_rejects_absent_reviewer_delegation(self) -> None:
        # A reviewer agent_id with no matching delegation record must be
        # rejected even when the implementer is real.
        events = plan_skip_delegation_events()
        # Drop the RED_REVIEW reviewer delegation from the event stream.
        lines = [line for line in events.splitlines() if line]
        kept = [
            line for line in lines
            if '"task_kind": "RED_REVIEW"' not in line
        ]
        events = "\n".join(kept) + "\n"
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "invented|absent|not found|RED_REVIEW",
        ):
            run_plan_skip(events=events)

    def test_plan_skip_still_rejects_broken_lineage(self) -> None:
        # The plan-skip mode must preserve the existing journal invariants: a
        # derived entry with a missing/future parent is still rejected.
        journal = plan_skip_journal().replace(
            "TYPE: SPEC_REVIEW\nSPEC: SPEC-1\nSTATUS: PASS\nPARENT: J-20260726-000000-002",
            "TYPE: SPEC_REVIEW\nSPEC: SPEC-1\nSTATUS: PASS\nPARENT: --",
        )
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "missing or future parent",
        ):
            run_plan_skip(journal=journal)

    def test_plan_skip_still_rejects_red_before_task_review_gate(self) -> None:
        # In plan-skip mode RED must begin only after the TASK_REVIEW process
        # gate; starting before it remains an invariant violation.
        journal = plan_skip_journal()
        blocks = journal.split("\n\n")
        red = next(block for block in blocks if "TYPE: RED\n" in block)
        blocks.remove(red)
        blocks.insert(0, red)
        with self.assertRaisesRegex(
            verify_evidence.EvidenceError,
            "RED began before|missing or future parent|top-level|must exist|review|out of order",
        ):
            run_plan_skip(journal="\n\n".join(blocks))

    def test_plan_skip_collector_indexes_delegation_ids(self) -> None:
        # The event collector is schema-agnostic: it must extract id-bearing
        # identifiers from delegation records so invented/absent agent ids
        # can be rejected in plan-skip mode.
        records = [
            json.loads(line)
            for line in plan_skip_delegation_events().splitlines()
            if line
        ]
        agents, jobs = verify_evidence.collect_event_ids(records)
        for row in plan_skip_runtime_rows():
            self.assertIn(str(row["agent_id"]), agents)
            self.assertIn(str(row["job_id"]), jobs)


if __name__ == "__main__":
    unittest.main()
