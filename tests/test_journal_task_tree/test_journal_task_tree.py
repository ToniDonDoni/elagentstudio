"""test_journal_task_tree.py — Journal Task Tree Traceability Test.

Validates that a JOURNAL produced by an SDD run satisfies:
  1. Forest of trees (multiple USER_INPUTs allowed)
  2. Every entry traces to USER_INPUT via PARENT chain
  3. ROOT matches the reached USER_INPUT
  4. Branching only at USER_INPUT, DECOMPOSE, TASK_REVIEW
  5. Linearity within each task branch
  6. No cycles, self-refs, orphan-parents
  7. Required fields (PARENT, ROOT, TASK, SPEC) present and valid

The test generates a realistic sample JOURNAL from a simulated Tetris
SDD run (forest: 1 USER_INPUT, 4 tasks branching from TASK_REVIEW).
8 tests total, synthetic error cases for each violation type.

Directory:
  tests/test_journal_task_tree/
    SKILL.md                    — copy of skill under test
    TASK.md                     — Tetris task spec
    test_journal_task_tree.py   — this file
    validate_journal.py         — standalone validator
    good_journal.log            — known-good journal fixture
    bad_*.log                   — known-bad journal fixtures
"""

import re
from typing import Any

# Types allowed to have multiple children (branching points)
BRANCHING_TYPES = {"USER_INPUT", "DECOMPOSE", "TASK_REVIEW"}

# Per-task types that must have a TASK field
TASK_TYPES = {"RED", "RED_REVIEW", "GREEN", "GREEN_REVIEW"}

# Valid TYPE values (from spec-driven-tdd SKILL.md TYPE enum)
VALID_TYPES = {
    "USER_INPUT", "PROJECT_INIT", "SPEC_SPEC", "SPEC_REVIEW",
    "DECOMPOSE", "TASK_REVIEW", "AGENT_DECISION",
    "RED", "RED_REVIEW", "GREEN", "GREEN_REVIEW",
    "REGRESSION", "REGRESSION_REVIEW", "FINAL_REVIEW",
    "ESCALATION", "DONE",
}

# Allowed PARENT sentinel
SENTINEL = "--"


# =============================================================================
# T1: Journal generator
# =============================================================================

def _jid(seq: int) -> str:
    return f"J-TETRIS-{seq:03d}"


def generate_tetris_journal() -> str:
    """Generate a journal from a Tetris SDD run.

    Correct structure (tree, not a chain):
      USER_INPUT
        └─ SPEC_SPEC → SPEC_REVIEW → DECOMPOSE → TASK_REVIEW
             ├─ TASK-001: RED → RED_REVIEW → GREEN → GREEN_REVIEW → REGRESSION
             ├─ TASK-002: RED → RED_REVIEW → GREEN → GREEN_REVIEW → REGRESSION
             ├─ TASK-003: RED → RED_REVIEW → GREEN → GREEN_REVIEW → REGRESSION
             └─ TASK-004: RED → RED_REVIEW → GREEN → GREEN_REVIEW → REGRESSION
                                       └─ FINAL_REVIEW → DONE
    """
    s = 0
    def nxt() -> str:
        nonlocal s; s += 1; return _jid(s)

    def ent(jid, typ, spec, status, parent, detail, root="", task="", tparent=""):
        lines = [f"=== {jid} ===",
                 f"TYPE: {typ}",
                 f"SPEC: {spec}",
                 f"STATUS: {status}",
                 f"PARENT: {parent}"]
        if root:
            lines.append(f"ROOT: {root}")
        if tparent:
            lines.append(f"TASK_PARENT: {tparent}")
        if task:
            lines.append(f"TASK: {task}")
        lines.append(f"DETAIL: {detail}")
        lines.append("")
        return "\n".join(lines)

    root = nxt()  # 001: USER_INPUT
    spec_s = nxt()  # 002
    spec_r = nxt()  # 003
    decomp = nxt()  # 004
    task_r = nxt()  # 005

    tasks = [
        ("T-S-TETRIS-01-001", "Board model (10x20 grid)"),
        ("T-S-TETRIS-01-002", "Piece definitions and rotation (7 tetrominoes)"),
        ("T-S-TETRIS-01-003", "Collision detection and line clearing"),
        ("T-S-TETRIS-01-004", "Game loop (input handling, gravity, scoring)"),
    ]

    parts = [
        ent(root, "USER_INPUT", "S-TETRIS-01", "COMPLETED", SENTINEL,
            "Tetris game via SDD pipeline", root=root),
        ent(spec_s, "SPEC_SPEC", "S-TETRIS-01", "COMPLETED", root,
            "SPEC-DRAFT.md created with 4 entities", root=root),
        ent(spec_r, "SPEC_REVIEW", "S-TETRIS-01", "PASS", spec_s,
            "SPEC REVIEW PASS", root=root),
        ent(decomp, "DECOMPOSE", "S-TETRIS-01", "COMPLETED", spec_r,
            "Decomposed into 4 tasks", root=root),
        ent(task_r, "TASK_REVIEW", "S-TETRIS-01", "PASS", decomp,
            "TASK REVIEW PASS", root=root),
    ]

    # Each task is a child of TASK_REVIEW (branching!), linear inside
    last_regression = None
    for i, (tid, desc) in enumerate(tasks):
        red = nxt()
        rev = nxt()
        grn = nxt()
        grev = nxt()
        reg = nxt()

        parts.append(ent(red, "RED", "S-TETRIS-01", "COMPLETED", task_r,
                         f"T{i+1} RED: {desc}", root=root, task=tid))
        parts.append(ent(rev, "RED_REVIEW", "S-TETRIS-01", "PASS", red,
                         f"T{i+1} RED REVIEW PASS", root=root, task=tid))
        parts.append(ent(grn, "GREEN", "S-TETRIS-01", "COMPLETED", rev,
                         f"T{i+1} GREEN: {desc}", root=root, task=tid))
        parts.append(ent(grev, "GREEN_REVIEW", "S-TETRIS-01", "PASS", grn,
                         f"T{i+1} GREEN REVIEW PASS", root=root, task=tid))
        parts.append(ent(reg, "REGRESSION", "S-TETRIS-01", "PASS", grev,
                         f"T{i+1} REGRESSION: all tests green", root=root))
        last_regression = reg

    final_r = nxt()
    done = nxt()
    parts.append(ent(final_r, "FINAL_REVIEW", "S-TETRIS-01", "PASS", last_regression,
                     "FINAL REVIEW PASS", root=root))
    parts.append(ent(done, "DONE", "S-TETRIS-01", "COMPLETED", final_r,
                     "Tetris implementation complete", root=root))

    return "\n".join(parts)


# =============================================================================
# T2: Journal parser
# =============================================================================

def parse_journal(text: str) -> list[dict[str, Any]]:
    """Parse journal text into a list of entry dicts.

    Keys: jid, type, spec, status, parent, root, task, task_parent, detail.
    """
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    FIELD_MAP = {
        "type": "type", "spec": "spec", "status": "status",
        "parent": "parent", "root": "root", "task": "task",
        "task_parent": "task_parent", "depends": "depends",
        "detail": "detail",
    }

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("===") and stripped.endswith("==="):
            if current is not None:
                entries.append(current)
            jid = stripped[3:-3].strip()
            current = {"jid": jid}
            continue
        if current is None:
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lower()
            value = value.strip()
            mapped = FIELD_MAP.get(key)
            if mapped:
                if mapped == "detail":
                    current.setdefault("detail", "")
                    if current["detail"]:
                        current["detail"] += "\n" + value
                    else:
                        current["detail"] = value
                else:
                    current[mapped] = value

    if current is not None:
        entries.append(current)
    return entries


# =============================================================================
# T3-T7: Validation
# =============================================================================

_VALID_TYPES = VALID_TYPES
_BRANCHING_TYPES = BRANCHING_TYPES
_TASK_TYPES = TASK_TYPES


def validate_journal(journal_text: str) -> list[str]:
    """Validate journal task-tree properties.

    Returns list of error strings (empty = all pass).
    Error format: JID=<jid> DETAIL=<description>
    """
    errors = []
    entries = parse_journal(journal_text)

    if not entries:
        return ["JID=-- DETAIL=No entries could be parsed from journal"]

    entry_map: dict[str, dict] = {e["jid"]: e for e in entries}
    user_inputs = [e for e in entries if e.get("type") == "USER_INPUT"]

    # --- A1: All USER_INPUTs have PARENT: -- and ROOT = self ---
    for ui in user_inputs:
        if ui.get("parent", "") != SENTINEL:
            errors.append(f"JID={ui['jid']} DETAIL=USER_INPUT has PARENT={ui.get('parent')!r}, expected '{SENTINEL}'")
        root = ui.get("root", "")
        if root and root != ui["jid"]:
            errors.append(f"JID={ui['jid']} DETAIL=USER_INPUT ROOT={root!r} != own JID {ui['jid']!r}")

    # --- A2: Every entry has required fields ---
    for e in entries:
        if "type" not in e or not e["type"]:
            errors.append(f"JID={e['jid']} DETAIL=Entry has no TYPE field")
        elif e["type"] not in _VALID_TYPES:
            errors.append(f"JID={e['jid']} DETAIL=Invalid TYPE={e['type']!r}")
        if "spec" not in e or not e["spec"]:
            errors.append(f"JID={e['jid']} DETAIL=Missing SPEC field")

    # --- A3: Unique JIDs ---
    seen_jids: dict[str, int] = {}
    for e in entries:
        jid = e["jid"]
        if jid in seen_jids:
            errors.append(f"JID={jid} DETAIL=Duplicate JID (also at index {seen_jids[jid]})")
        seen_jids[jid] = len(seen_jids)

    # --- A4: DONE exists ---
    done_entries = [e for e in entries if e.get("type") == "DONE"]
    if not done_entries:
        errors.append("JID=-- DETAIL=No DONE entry found (required for completed pipeline)")

    # --- A5: Every non-USER_INPUT has PARENT that exists or is sentinel ---
    for e in entries:
        if e.get("type") == "USER_INPUT":
            continue
        if "parent" not in e:
            errors.append(f"JID={e['jid']} DETAIL=Entry type {e['type']!r} has no PARENT field")
            continue
        p = e["parent"]
        if p == e["jid"]:
            errors.append(f"JID={e['jid']} DETAIL=Self-reference: PARENT points to own JID")
        if p not in entry_map and p != SENTINEL:
            errors.append(f"JID={e['jid']} DETAIL=PARENT={p!r} does not match any existing entry")

    # --- A6: TASK field on per-task entries ---
    for e in entries:
        if e.get("type") in _TASK_TYPES:
            task = e.get("task", "")
            if not task:
                errors.append(f"JID={e['jid']} DETAIL=Entry type {e['type']!r} missing TASK field")
            elif not re.match(r"^T-[\w.-]+-\d{3}$", task):
                errors.append(f"JID={e['jid']} DETAIL=TASK={task!r} does not match pattern T-<SPEC_ID>-NNN")

    # --- A7: PARENT chain finite + reaches USER_INPUT + ROOT matches ---
    for e in entries:
        visited: set[str] = set()
        current_jid = e["jid"]
        reached_user = None  # JID of reached USER_INPUT

        while True:
            if current_jid in visited:
                errors.append(f"JID={e['jid']} DETAIL=Cycle in PARENT chain: revisiting {current_jid}")
                break
            visited.add(current_jid)

            cur = entry_map.get(current_jid)
            if cur is None:
                errors.append(f"JID={e['jid']} DETAIL=PARENT chain broken at {current_jid!r}: entry not found")
                break

            if cur.get("type") == "USER_INPUT":
                if cur.get("parent", "") == SENTINEL:
                    reached_user = cur["jid"]
                else:
                    errors.append(f"JID={e['jid']} DETAIL=USER_INPUT {current_jid} has PARENT={cur.get('parent')!r}, expected '{SENTINEL}'")
                break

            parent = cur.get("parent", "")
            if parent == SENTINEL or parent == "":
                errors.append(f"JID={e['jid']} DETAIL=Chain terminates at {current_jid} (type={cur.get('type')!r}) without reaching USER_INPUT")
                break

            current_jid = parent

        # Check ROOT matches reached USER_INPUT
        if reached_user:
            entry_root = e.get("root", "")
            if not entry_root:
                errors.append(f"JID={e['jid']} DETAIL=Missing ROOT field")
            elif entry_root != reached_user:
                errors.append(
                    f"JID={e['jid']} DETAIL=ROOT mismatch: entry ROOT={entry_root!r}, "
                    f"but PARENT chain reaches USER_INPUT {reached_user!r}"
                )

    # --- A8: Branching allowed only at specific types ---
    # Count children per parent JID
    child_counts: dict[str, list[str]] = {}
    for e in entries:
        p = e.get("parent", "")
        if p == SENTINEL or p == "":
            continue
        if p not in child_counts:
            child_counts[p] = []
        child_counts[p].append(e["jid"])

    for parent_jid, children in child_counts.items():
        if len(children) <= 1:
            continue  # fine
        parent_entry = entry_map.get(parent_jid)
        parent_type = parent_entry.get("type", "") if parent_entry else ""
        if parent_type not in _BRANCHING_TYPES:
            errors.append(
                f"JID={parent_jid} DETAIL=Branching not allowed: {len(children)} children "
                f"({children}) but type={parent_type!r} "
                f"(allowed branching: {sorted(_BRANCHING_TYPES)})"
            )

    return errors


# =============================================================================
# T8: Tests
# =============================================================================

def test_clean_journal_passes_all_checks():
    """A well-formed Tetris SDD journal validates with zero errors."""
    journal = generate_tetris_journal()
    errors = validate_journal(journal)
    assert errors == [], (
        f"Clean journal should pass all checks, got {len(errors)} errors:\n"
        + "\n".join(errors)
    )


def _make_minimal_journal(entries_text: str) -> str:
    return entries_text.strip() + "\n"


def test_detects_missing_parent():
    """Entry without PARENT field is detected."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root

=== J-ORPHAN-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
ROOT: J-UID-001
DETAIL: Missing PARENT
""")
    errors = validate_journal(journal)
    assert any("J-ORPHAN-001" in e and "PARENT" in e for e in errors), (
        f"Should detect missing PARENT, errors: {errors}"
    )


def test_detects_orphan_parent():
    """PARENT pointing to non-existent JID is detected."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root

=== J-CHILD-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-NONEXISTENT
ROOT: J-UID-001
TASK: T-S-TEST-001
DETAIL: Orphan parent
""")
    errors = validate_journal(journal)
    assert any("J-NONEXISTENT" in e for e in errors), (
        f"Should detect orphan PARENT, errors: {errors}"
    )


def test_detects_self_reference():
    """PARENT == own JID is detected."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root

=== J-SELF-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-SELF-001
ROOT: J-UID-001
TASK: T-S-TEST-001
DETAIL: Self-ref
""")
    errors = validate_journal(journal)
    assert any("self" in e.lower() and "J-SELF-001" in e for e in errors), (
        f"Should detect self-reference, errors: {errors}"
    )


def test_detects_cycle():
    """Circular PARENT chain is detected."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root

=== J-A-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-B-001
ROOT: J-UID-001
TASK: T-S-TEST-001
DETAIL: A

=== J-B-001 ===
TYPE: GREEN
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-A-001
ROOT: J-UID-001
TASK: T-S-TEST-001
DETAIL: B
""")
    errors = validate_journal(journal)
    assert any("cycle" in e.lower() for e in errors), (
        f"Should detect cycle, errors: {errors}"
    )


def test_detects_broken_chain():
    """Chain terminating before USER_INPUT is detected."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root

=== J-MID-001 ===
TYPE: SPEC_SPEC
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Disconnected from USER_INPUT

=== J-DONE-001 ===
TYPE: DONE
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-MID-001
ROOT: J-UID-001
DETAIL: Done pointing to disconnected mid
""")
    errors = validate_journal(journal)
    assert any("J-DONE-001" in e and "USER_INPUT" in e for e in errors), (
        f"Should detect broken chain from DONE, errors: {errors}"
    )


def test_detects_multiple_roots():
    """Multiple USER_INPUTs are allowed (forest), each must be valid."""
    journal = _make_minimal_journal("""
=== J-ROOT1-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-ROOT1-001
DETAIL: Root 1

=== J-ROOT2-001 ===
TYPE: USER_INPUT
SPEC: S-TEST-2
STATUS: COMPLETED
PARENT: --
ROOT: J-ROOT2-001
DETAIL: Root 2

=== J-SPEC1-001 ===
TYPE: SPEC_SPEC
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-ROOT1-001
ROOT: J-ROOT1-001
DETAIL: Spec in tree 1
""")
    errors = validate_journal(journal)
    # Multiple USER_INPUTs are allowed — should not error about that
    multi_root_errors = [e for e in errors if "USER_INPUT" in e and "Multiple" in e]
    assert len(multi_root_errors) == 0, (
        f"Multiple USER_INPUTs should be allowed, errors: {errors}"
    )


def test_detects_wrong_root():
    """ROOT mismatch (entry ROOT != reached USER_INPUT) is detected."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root

=== J-UID-002 ===
TYPE: SPEC_SPEC
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-UID-001
ROOT: J-UID-002
DETAIL: ROOT points to itself, not to the USER_INPUT
""")
    errors = validate_journal(journal)
    assert any("ROOT mismatch" in e for e in errors), (
        f"Should detect ROOT mismatch, errors: {errors}"
    )


def test_detects_branching_in_task():
    """Branching inside a task branch (not at allowed node) is detected."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root

=== J-SPEC-001 ===
TYPE: SPEC_SPEC
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-UID-001
ROOT: J-UID-001
DETAIL: Spec

=== J-SREV-001 ===
TYPE: SPEC_REVIEW
SPEC: S-TEST
STATUS: PASS
PARENT: J-SPEC-001
ROOT: J-UID-001
DETAIL: Spec review

=== J-DECOMP-001 ===
TYPE: DECOMPOSE
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-SREV-001
ROOT: J-UID-001
DETAIL: Decomp

=== J-TREV-001 ===
TYPE: TASK_REVIEW
SPEC: S-TEST
STATUS: PASS
PARENT: J-DECOMP-001
ROOT: J-UID-001
DETAIL: Task review

=== J-RED-A-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-TREV-001
ROOT: J-UID-001
TASK: T-S-TETRIS-01-001
DETAIL: Task 1 RED

=== J-RED-B-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-TREV-001
ROOT: J-UID-001
TASK: T-S-TETRIS-01-002
DETAIL: Task 2 RED (branching at TASK_REVIEW = allowed)

=== J-RED-C-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-RED-A-001
ROOT: J-UID-001
TASK: T-S-TETRIS-01-001
DETAIL: Second child of RED-A-001 (branching NOT allowed inside task)

=== J-RED-D-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-RED-A-001
ROOT: J-UID-001
TASK: T-S-TETRIS-01-001
DETAIL: Third child of RED-A-001 (also illegal branching)
""")
    errors = validate_journal(journal)
    assert any("Branching not allowed" in e for e in errors), (
        f"Should detect illegal branching inside task, errors: {errors}"
    )
    # But branching at TASK_REVIEW should NOT be flagged
    branching_errors = [e for e in errors if "Branching" in e]
    assert not any("J-TREV-001" in e for e in branching_errors), (
        f"Branching at TASK_REVIEW should be allowed, errors: {branching_errors}"
    )


def test_detects_duplicate_jid():
    """Duplicate JIDs are detected."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root

=== J-UID-001 ===
TYPE: DONE
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-UID-001
ROOT: J-UID-001
DETAIL: Duplicate JID
""")
    errors = validate_journal(journal)
    assert any("Duplicate JID" in e for e in errors), (
        f"Should detect duplicate JIDs, errors: {errors}"
    )


def test_detects_missing_done():
    """Journal without DONE entry is flagged (advisory)."""
    journal = _make_minimal_journal("""
=== J-UID-001 ===
TYPE: USER_INPUT
SPEC: S-TEST
STATUS: COMPLETED
PARENT: --
ROOT: J-UID-001
DETAIL: Root
""")
    errors = validate_journal(journal)
    assert any("DONE" in e for e in errors), (
        f"Should warn about missing DONE, errors: {errors}"
    )
