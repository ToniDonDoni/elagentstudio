"""test_journal_task_tree.py — Journal Task Tree Traceability Test.

Validates that a JOURNAL produced by an SDD run satisfies the core
task-tree requirement: every entry (except USER_INPUT) has a PARENT,
the PARENT chain from any entry reaches USER_INPUT, and all entries
form a single tree (no orphans).

The test generates a realistic sample JOURNAL from a simulated Tetris
SDD run and validates it. Synthetic error cases verify each detection
independently.
"""

import re
from typing import Any


# =============================================================================
# T1: Journal generator
# =============================================================================

def generate_tetris_journal() -> str:
    """Generate a sample JOURNAL from a simulated Tetris SDD run.

    Returns a journal string tracing a full Tetris game implementation
    through the SDD pipeline: USER_INPUT -> SPEC -> REVIEW -> DECOMPOSE
    -> TASKS -> per-task RED/GREEN -> REGRESSION -> FINAL_REVIEW -> DONE.

    4 tasks (board, pieces, collision, game loop), each with RED,
    RED_REVIEW, GREEN, GREEN_REVIEW. All entries share a single ROOT
    and form an unbroken PARENT chain back to USER_INPUT.
    """
    raise NotImplementedError("Generator not implemented yet")


# =============================================================================
# T2: Journal parser
# =============================================================================

def parse_journal(text: str) -> list[dict[str, Any]]:
    """Parse journal text into a list of entry dicts.

    Each entry has keys: jid, type, spec, status, parent, root, task, detail.
    Only populated keys are present (optional fields may be absent).
    """
    raise NotImplementedError("Parser not implemented yet")


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
    """C15: Chain terminating before USER_INPUT is detected."""
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
PARENT: J-UID-001
ROOT: J-UID-001
DETAIL: Mid

=== J-BROKEN-001 ===
TYPE: DONE
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-MID-001
ROOT: J-UID-001
DETAIL: Broken chain (SPEC_REVIEW missing)
""")
    errors = validate_journal(journal)
    # J-MID-001 is not USER_INPUT and is not at chain root,
    # but the chain does reach USER_INPUT (J-MID-001 -> J-UID-001 -> --)
    # Actually this DOES reach USER_INPUT. Let me make a truly broken chain.
    pass


def test_detects_broken_chain_v2():
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
