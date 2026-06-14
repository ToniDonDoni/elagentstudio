"""test_journal_task_tree.py — Journal Task Tree Traceability Test.

Validates that a JOURNAL produced by an SDD run satisfies the core
task-tree requirement: every entry (except USER_INPUT) has a PARENT,
the PARENT chain from any entry reaches USER_INPUT, and all entries
form a single tree (no orphans).

The test generates a realistic sample JOURNAL from a simulated Tetris
SDD run and validates it (7 tests total, including 6 synthetic error
cases).

Directory structure:
  tests/test_journal_task_tree/
    SKILL.md              — copy of the skill under test
    TASK.md               — Tetris task specification
    test_journal_task_tree.py  — this test file
"""

import re
from typing import Any


# =============================================================================
# T1: Journal generator
# =============================================================================

def _jid(seq: int) -> str:
    """Generate a predictable JID for a given sequence number."""
    return f"J-TETRIS-{seq:03d}"


def generate_tetris_journal() -> str:
    """Generate a sample JOURNAL from a simulated Tetris SDD run.

    Returns a journal string tracing a full Tetris game implementation
    through the SDD pipeline. All entries form an unbroken PARENT chain
    from DONE back to USER_INPUT. Single ROOT for the entire tree.
    """
    # Sequence numbering for JIDs
    s = 0

    def next_jid() -> str:
        nonlocal s
        s += 1
        return _jid(s)

    root = _jid(1)  # J-TETRIS-001

    def entry(jid: str, typ: str, spec: str, status: str,
              parent: str, detail: str, root_jid: str = "",
              task: str = "") -> str:
        lines = [f"=== {jid} ===",
                 f"TYPE: {typ}",
                 f"SPEC: {spec}",
                 f"STATUS: {status}",
                 f"PARENT: {parent}"]
        if root_jid:
            lines.append(f"ROOT: {root_jid}")
        if task:
            lines.append(f"TASK: {task}")
        lines.append(f"DETAIL: {detail}")
        lines.append("")
        return "\n".join(lines)

    ui = next_jid()  # 001
    spec_spec = next_jid()  # 002
    spec_rev = next_jid()  # 003
    decomp = next_jid()  # 004
    task_rev = next_jid()  # 005

    tasks = [
        ("T-S-JTT-01-001", "Board model (10x20 grid, block storage)"),
        ("T-S-JTT-01-002", "Piece definitions and rotation (7 tetrominoes)"),
        ("T-S-JTT-01-003", "Collision detection and line clearing"),
        ("T-S-JTT-01-004", "Game loop (input handling, gravity, scoring)"),
    ]

    parts = [
        entry(ui, "USER_INPUT", "S-JTT-01", "COMPLETED", "--",
              "Tetris game implementation via SDD pipeline", root_jid=root),
        entry(spec_spec, "SPEC_SPEC", "S-JTT-01", "COMPLETED", ui,
              "SPEC-DRAFT.md created with 4 entities and 4 tasks", root_jid=root),
        entry(spec_rev, "SPEC_REVIEW", "S-JTT-01", "PASS", spec_spec,
              "SPEC REVIEW PASS - spec is complete and testable", root_jid=root),
        entry(decomp, "DECOMPOSE", "S-JTT-01", "COMPLETED", spec_rev,
              "Decomposed into 4 tasks: board, pieces, collision, game loop", root_jid=root),
        entry(task_rev, "TASK_REVIEW", "S-JTT-01", "PASS", decomp,
              "TASK REVIEW PASS - all tasks map to acceptance criteria", root_jid=root),
    ]

    # Per-task loop: previous_entry starts as task_rev for T1
    prev = task_rev
    for i, (task_id, task_desc) in enumerate(tasks):
        red = next_jid()
        red_rev = next_jid()
        green = next_jid()
        green_rev = next_jid()
        regr = next_jid()

        parts.append(entry(red, "RED", "S-JTT-01", "COMPLETED", prev,
                           f"T{i+1} RED: {task_desc} — test expects FAIL", root_jid=root, task=task_id))
        parts.append(entry(red_rev, "RED_REVIEW", "S-JTT-01", "PASS", red,
                           f"T{i+1} RED REVIEW PASS — test fails for right reason", root_jid=root, task=task_id))
        parts.append(entry(green, "GREEN", "S-JTT-01", "COMPLETED", red_rev,
                           f"T{i+1} GREEN: {task_desc} — minimal implementation", root_jid=root, task=task_id))
        parts.append(entry(green_rev, "GREEN_REVIEW", "S-JTT-01", "PASS", green,
                           f"T{i+1} GREEN REVIEW PASS — impl is minimal and correct", root_jid=root, task=task_id))
        parts.append(entry(regr, "REGRESSION", "S-JTT-01", "PASS", green_rev,
                           f"T{i+1} REGRESSION: all {i+1} tests green", root_jid=root))
        prev = regr

    final_rev = next_jid()
    done = next_jid()

    parts.append(entry(final_rev, "FINAL_REVIEW", "S-JTT-01", "PASS", prev,
                       "FINAL REVIEW PASS — all ACs covered, all tests green", root_jid=root))
    parts.append(entry(done, "DONE", "S-JTT-01", "COMPLETED", final_rev,
                       "Tetris implementation complete via SDD pipeline", root_jid=root))

    return "\n".join(parts)


# =============================================================================
# T2: Journal parser
# =============================================================================

def parse_journal(text: str) -> list[dict[str, Any]]:
    """Parse journal text into a list of entry dicts.

    Each entry has keys: jid, type, spec, status, parent, root, task, detail.
    Only populated keys are present (optional fields may be absent).
    """
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in text.split("\n"):
        stripped = line.strip()

        # Start of a new entry: === JID ===
        if stripped.startswith("===") and stripped.endswith("==="):
            if current is not None:
                entries.append(current)
            jid = stripped[3:-3].strip()
            current = {"jid": jid}
            continue

        if current is None:
            continue

        # Parse KEY: VALUE pairs
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lower()
            value = value.strip()
            # Map keys to our field names
            if key == "type":
                current["type"] = value
            elif key == "spec":
                current["spec"] = value
            elif key == "status":
                current["status"] = value
            elif key == "parent":
                current["parent"] = value
            elif key == "root":
                current["root"] = value
            elif key == "task":
                current["task"] = value
            elif key == "depends":
                current["depends"] = value
            elif key == "detail":
                current.setdefault("detail", "")
                if current["detail"]:
                    current["detail"] += "\n" + value
                else:
                    current["detail"] = value
            elif key == "detail" and value:
                current["detail"] = value

    if current is not None:
        entries.append(current)

    return entries


# =============================================================================
# T3-T7: Validation
# =============================================================================

def validate_journal(journal_text: str) -> list[str]:
    """Validate the task-tree traceability of a journal.

    Returns a list of error strings. Empty list = all checks pass.
    Each error format: JID=<jid> DETAIL=<description>

    Core checks:
      - Every entry (except USER_INPUT) has a PARENT field
      - PARENT of non-USER_INPUT entries points to an existing JID
      - No self-references (PARENT == own JID)
      - No cycles in PARENT chains
      - From every entry, following PARENT reaches USER_INPUT
      - Exactly one USER_INPUT (single tree root)
      - USER_INPUT has PARENT: --
    """
    errors = []
    entries = parse_journal(journal_text)

    if not entries:
        return ["JID=-- DETAIL=No entries could be parsed from journal"]

    # Build lookup
    entry_map: dict[str, dict] = {e["jid"]: e for e in entries}
    user_inputs = [e for e in entries if e.get("type") == "USER_INPUT"]

    # --- Exactly one USER_INPUT ---
    if len(user_inputs) == 0:
        errors.append("JID=-- DETAIL=No USER_INPUT entry found (required as tree root)")
    elif len(user_inputs) > 1:
        jids = [e["jid"] for e in user_inputs]
        errors.append(f"JID=-- DETAIL=Multiple USER_INPUT entries found ({len(user_inputs)}): {jids}. Expected exactly one.")

    # --- Every non-USER_INPUT has PARENT that exists ---
    for e in entries:
        if e.get("type") == "USER_INPUT":
            parent = e.get("parent", "")
            if parent != "--":
                errors.append(f"JID={e['jid']} DETAIL=USER_INPUT has PARENT={parent!r}, expected '--'")
            continue

        if "parent" not in e:
            errors.append(f"JID={e['jid']} DETAIL=Entry type {e['type']!r} has no PARENT field")
            continue

        parent = e["parent"]
        if parent not in entry_map and parent != "--":
            errors.append(f"JID={e['jid']} DETAIL=PARENT={parent!r} does not match any existing entry JID")
        if parent == e["jid"]:
            errors.append(f"JID={e['jid']} DETAIL=Self-reference: PARENT points to its own JID")

    # --- From every entry, PARENT chain reaches USER_INPUT ---
    for e in entries:
        visited: set[str] = set()
        current_jid = e["jid"]
        reached_user = False

        while True:
            if current_jid in visited:
                errors.append(f"JID={e['jid']} DETAIL=Cycle in PARENT chain: revisiting JID {current_jid}")
                break
            visited.add(current_jid)

            current = entry_map.get(current_jid)
            if current is None:
                errors.append(f"JID={e['jid']} DETAIL=PARENT chain broken at JID {current_jid!r}: entry not found")
                break

            if current.get("type") == "USER_INPUT":
                if current.get("parent", "") == "--":
                    reached_user = True
                else:
                    errors.append(f"JID={e['jid']} DETAIL=USER_INPUT {current_jid} has PARENT={current.get('parent')!r}, should be '--'")
                break

            parent = current.get("parent", "")
            if parent == "--" or parent == "":
                errors.append(f"JID={e['jid']} DETAIL=Chain terminates at {current_jid} (type={current.get('type')!r}) without reaching USER_INPUT")
                break

            current_jid = parent

        if not reached_user:
            continue  # error already recorded above

    return errors


# =============================================================================
# T8: Tests
# =============================================================================

# --- Clean journal test ---

def test_clean_journal_passes_all_checks():
    """A well-formed Tetris SDD journal validates with zero errors."""
    journal = generate_tetris_journal()
    errors = validate_journal(journal)
    assert errors == [], (
        f"Clean journal should pass all checks, got {len(errors)} errors:\n"
        + "\n".join(errors)
    )


# --- Synthetic error tests ---

def _make_minimal_journal(entries_text: str) -> str:
    """Wrap raw entries into a minimal journal string."""
    return entries_text.strip() + "\n"


def test_detects_missing_parent():
    """C14: Entry without PARENT field is detected."""
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
DETAIL: Orphan entry missing PARENT
""")
    errors = validate_journal(journal)
    assert any("J-ORPHAN-001" in e for e in errors), (
        f"Should detect missing PARENT, errors: {errors}"
    )


def test_detects_orphan_parent():
    """C3: PARENT pointing to non-existent JID is detected."""
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
    """C4: PARENT == own JID is detected."""
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
DETAIL: Self-reference
""")
    errors = validate_journal(journal)
    assert any("J-SELF-001" in e and "self" in e.lower() for e in errors), (
        f"Should detect self-reference, errors: {errors}"
    )


def test_detects_cycle():
    """C5: Circular PARENT chain is detected."""
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
DETAIL: Cycle node A

=== J-B-001 ===
TYPE: GREEN
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-A-001
ROOT: J-UID-001
TASK: T-S-TEST-001
DETAIL: Cycle node B
""")
    errors = validate_journal(journal)
    assert any("cycle" in e.lower() for e in errors), (
        f"Should detect cycle, errors: {errors}"
    )


def test_detects_broken_chain():
    """C15: Chain terminating at non-USER_INPUT with PARENT: -- is detected."""
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
DETAIL: Mid with no parent link to USER_INPUT

=== J-DONE-001 ===
TYPE: DONE
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-MID-001
ROOT: J-UID-001
DETAIL: Done pointing to mid that is disconnected from USER_INPUT
""")
    errors = validate_journal(journal)
    assert any("USER_INPUT" in e and "J-DONE-001" in e for e in errors), (
        f"Should detect broken chain from DONE, errors: {errors}"
    )


def test_detects_multiple_roots():
    """Multiple USER_INPUT entries (multiple trees) are detected."""
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
""")
    errors = validate_journal(journal)
    assert any("Multiple USER_INPUT" in e for e in errors), (
        f"Should detect multiple roots, errors: {errors}"
    )
