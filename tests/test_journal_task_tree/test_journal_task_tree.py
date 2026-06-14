"""test_journal_task_tree.py — Journal Task Tree Traceability Test.

This test validates that a JOURNAL produced by an SDD run conforms to the
task-tree traceability requirements defined in SKILL.md (Task ID scheme,
unbroken PARENT chain, ROOT/TASK fields).

The test generates a realistic sample JOURNAL from a simulated Tetris SDD run
(27 entries covering the full lifecycle) and validates it against 15 checks
(C1-C15). Synthetic error cases verify each check independently.

Structure:
  - tests/test_journal_task_tree/     — test directory
  - tests/test_journal_task_tree/SKILL.md  — copy of skill under test
  - tests/test_journal_task_tree/TASK.md   — Tetris task spec
"""

import re


# =============================================================================
# T1: Journal generator
# =============================================================================

def generate_tetris_journal() -> str:
    """Generate a sample JOURNAL from a simulated Tetris SDD run.

    Returns a string reproducing the 27-entry Tetris SDD lifecycle as
    specified in the spec (R5 entry table).

    The simulated run covers:
      Tetris game implementation via SDD
    Entities: Board (10x20 grid), 7 Tetrominoes, Collision Detection,
              Game Loop
    Tasks: 4 tasks, each with RED -> RED_REVIEW -> GREEN -> GREEN_REVIEW
    """
    # TODO: Implement in GREEN phase
    raise NotImplementedError("Generator not implemented yet")


# =============================================================================
# T2: Journal parser
# =============================================================================

def parse_journal(text: str) -> list[dict]:
    """Parse journal text into a list of entry dicts.

    Each entry has keys: jid, type, spec, status, parent, root, task, detail.
    """
    # TODO: Implement in GREEN phase
    raise NotImplementedError("Parser not implemented yet")


# =============================================================================
# T3-T7: Validation engine
# =============================================================================

# Check registry: maps check name to (function, description)
_CHECKS: dict[str, tuple] = {}


def _register(check_name: str, description: str):
    """Decorator to register a validation check."""
    def decorator(func):
        _CHECKS[check_name] = (func, description)
        return func
    return decorator


def validate_journal(journal_text: str) -> list[str]:
    """Run all 15 validation checks (C1-C15) on the journal.

    Returns a list of error strings. Empty list = all checks pass.
    Each error format: JID=<jid> CHECK=<name> DETAIL=<detail>
    """
    errors = []
    entries = parse_journal(journal_text)
    for check_name, (func, _) in _CHECKS.items():
        try:
            check_errors = func(entries, journal_text)
            errors.extend(check_errors)
        except Exception as e:
            errors.append(f"JID=-- CHECK={check_name} DETAIL=CRASHED: {e}")
    return errors


# --- C1: All entries parseable ---

@_register("C1", "All entries parseable")
def check_c1(entries, raw_text):
    errors = []
    if not entries and raw_text.strip():
        errors.append("JID=-- CHECK=C1 DETAIL=No entries could be parsed from journal text")
    seen_jids = set()
    for e in entries:
        jid = e.get("jid", "")
        if not jid:
            errors.append("JID=-- CHECK=C1 DETAIL=Entry with empty JID found")
        elif " " in jid or "\t" in jid:
            errors.append(f"JID={jid} CHECK=C1 DETAIL=JID contains whitespace")
        if jid in seen_jids:
            errors.append(f"JID={jid} CHECK=C1 DETAIL=Duplicate JID (caught by C1)")
        seen_jids.add(jid)
    return errors


# --- C2: USER_INPUT has PARENT: ---

@_register("C2", "USER_INPUT has PARENT: --")
def check_c2(entries, raw_text):
    errors = []
    for e in entries:
        if e.get("type") == "USER_INPUT":
            parent = e.get("parent", "")
            if parent != "--":
                errors.append(f"JID={e['jid']} CHECK=C2 DETAIL=USER_INPUT has PARENT={parent!r}, expected '--'")
    return errors


# --- C3: Every PARENT JID exists or is sentinel ---

@_register("C3", "Every PARENT JID exists or is sentinel")
def check_c3(entries, raw_text):
    errors = []
    all_jids = {e["jid"] for e in entries}
    for e in entries:
        parent = e.get("parent", "")
        if parent == "--" or parent == "":
            continue
        if parent not in all_jids:
            errors.append(f"JID={e['jid']} CHECK=C3 DETAIL=PARENT={parent!r} does not match any existing entry JID")
    return errors


# --- C4: No self-references ---

@_register("C4", "No self-references")
def check_c4(entries, raw_text):
    errors = []
    for e in entries:
        jid = e["jid"]
        parent = e.get("parent", "")
        if parent == jid:
            errors.append(f"JID={jid} CHECK=C4 DETAIL=PARENT points to its own JID (self-reference)")
    return errors


# --- C5: No circular references ---

@_register("C5", "No circular references")
def check_c5(entries, raw_text):
    errors = []
    entry_map = {e["jid"]: e for e in entries}
    for e in entries:
        visited = set()
        current_jid = e["jid"]
        while True:
            parent = entry_map.get(current_jid, {}).get("parent", "")
            if parent == "--" or parent == "" or parent not in entry_map:
                break
            if parent in visited:
                errors.append(f"JID={e['jid']} CHECK=C5 DETAIL=Circular reference detected in PARENT chain: {', '.join(visited)} -> {parent}")
                break
            visited.add(parent)
            current_jid = parent
    return errors


# --- C6: Unique JIDs ---

@_register("C6", "Unique JIDs")
def check_c6(entries, raw_text):
    errors = []
    seen = {}
    for e in entries:
        jid = e["jid"]
        if jid in seen:
            errors.append(f"JID={jid} CHECK=C6 DETAIL=Duplicate JID (first at index {seen[jid]})")
        seen[jid] = len(seen)
    return errors


# --- C7: Minimum entry count ---

@_register("C7", "Minimum entry count")
def check_c7(entries, raw_text):
    errors = []
    has_user_input = any(e.get("type") == "USER_INPUT" for e in entries)
    has_done = any(e.get("type") == "DONE" for e in entries)
    if not has_user_input:
        errors.append("JID=-- CHECK=C7 DETAIL=No USER_INPUT entry found (minimum 1 required)")
    if not has_done:
        errors.append("JID=-- CHECK=C7 DETAIL=No DONE entry found (minimum 1 required)")
    return errors


# --- C8: ROOT field present on every entry ---

@_register("C8", "ROOT field present on every entry")
def check_c8(entries, raw_text):
    errors = []
    for e in entries:
        if "root" not in e or not e.get("root"):
            errors.append(f"JID={e['jid']} CHECK=C8 DETAIL=Missing or empty ROOT field")
    return errors


# --- C9: ROOT is consistent ---

@_register("C9", "ROOT is consistent (all same)")
def check_c9(entries, raw_text):
    errors = []
    root_values = {e.get("root", "") for e in entries if e.get("root")}
    if len(root_values) > 1:
        roots_list = sorted(root_values)
        errors.append(f"JID=-- CHECK=C9 DETAIL=Multiple different ROOT values found: {roots_list}")
    elif len(root_values) == 0:
        errors.append("JID=-- CHECK=C9 DETAIL=No ROOT values found in any entry")
    return errors


# --- C10: ROOT points to a real USER_INPUT ---

@_register("C10", "ROOT points to a real USER_INPUT")
def check_c10(entries, raw_text):
    errors = []
    entry_map = {e["jid"]: e for e in entries}
    for e in entries:
        root = e.get("root", "")
        if not root:
            continue
        if root not in entry_map:
            errors.append(f"JID={e['jid']} CHECK=C10 DETAIL=ROOT={root!r} does not match any existing entry")
        elif entry_map[root].get("type") != "USER_INPUT":
            errors.append(f"JID={e['jid']} CHECK=C10 DETAIL=ROOT={root!r} exists but its TYPE is {entry_map[root].get('type')!r}, expected USER_INPUT")
    return errors


# --- C11: TASK field on per-task entries ---

@_register("C11", "TASK field on per-task entries")
def check_c11(entries, raw_text):
    errors = []
    per_task_types = {"RED", "GREEN", "RED_REVIEW", "GREEN_REVIEW"}
    for e in entries:
        if e.get("type") in per_task_types:
            if "task" not in e or not e.get("task"):
                errors.append(f"JID={e['jid']} CHECK=C11 DETAIL=Entry type {e['type']!r} missing TASK field")
    return errors


# --- C12: TASK ID format ---

@_register("C12", "TASK ID format")
def check_c12(entries, raw_text):
    errors = []
    pattern = re.compile(r"^T-S-JTT-01-\d{3}$")
    for e in entries:
        task = e.get("task", "")
        if task:
            if not pattern.match(task):
                errors.append(f"JID={e['jid']} CHECK=C12 DETAIL=TASK={task!r} does not match pattern T-S-JTT-01-NNN")
    return errors


# --- C13: SPEC field present ---

@_register("C13", "SPEC field present")
def check_c13(entries, raw_text):
    errors = []
    for e in entries:
        spec = e.get("spec", "")
        if not spec:
            errors.append(f"JID={e['jid']} CHECK=C13 DETAIL=Missing or empty SPEC field")
    return errors


# --- C14: Non-USER_INPUT must have PARENT field ---

@_register("C14", "Non-USER_INPUT must have PARENT field")
def check_c14(entries, raw_text):
    errors = []
    for e in entries:
        if e.get("type") != "USER_INPUT":
            if "parent" not in e:
                errors.append(f"JID={e['jid']} CHECK=C14 DETAIL=Entry type {e['type']!r} has no PARENT field")
    return errors


# --- C15: Chain completeness (DONE -> USER_INPUT) ---

@_register("C15", "Chain completeness (DONE reaches USER_INPUT)")
def check_c15(entries, raw_text):
    errors = []
    entry_map = {e["jid"]: e for e in entries}
    done_entries = [e for e in entries if e.get("type") == "DONE"]
    if not done_entries:
        return ["JID=-- CHECK=C15 DETAIL=No DONE entry found to trace chain from"]

    for done in done_entries:
        visited = set()
        current_jid = done["jid"]
        reached_user_input = False
        while True:
            current = entry_map.get(current_jid)
            if current is None:
                errors.append(f"JID={done['jid']} CHECK=C15 DETAIL=Chain broken at JID={current_jid!r} - entry not found")
                break
            if current.get("type") == "USER_INPUT":
                parent = current.get("parent", "")
                if parent == "--":
                    reached_user_input = True
                else:
                    errors.append(f"JID={done['jid']} CHECK=C15 DETAIL=USER_INPUT {current_jid} has PARENT={parent!r}, expected '--'")
                break
            parent = current.get("parent", "")
            if parent == "--" or parent == "":
                errors.append(f"JID={done['jid']} CHECK=C15 DETAIL=Chain terminated at {current_jid} (type={current.get('type')!r}) without reaching USER_INPUT")
                break
            if parent in visited:
                errors.append(f"JID={done['jid']} CHECK=C15 DETAIL=Cycle detected in PARENT chain from DONE")
                break
            visited.add(parent)
            current_jid = parent
        if not reached_user_input and not any(
            done["jid"] in err for err in errors
        ):
            pass  # error already recorded above

    return errors


# =============================================================================
# T8: Test functions
# =============================================================================

def test_generator_returns_string():
    """S-JTT-01.01: generate_tetris_journal() returns a non-empty string."""
    journal = generate_tetris_journal()
    assert isinstance(journal, str), "Generator must return a string"
    assert len(journal) > 0, "Generator must return non-empty string"


def test_generator_has_27_entries():
    """S-JTT-01.01: Journal has exactly 27 entries."""
    journal = generate_tetris_journal()
    count = sum(1 for line in journal.split("\n") if line.startswith("==="))
    assert count == 27, f"Expected 27 entries (=== markers), got {count}"


def test_generator_has_user_input_and_done():
    """S-JTT-01.01: Journal contains USER_INPUT and DONE entries."""
    journal = generate_tetris_journal()
    assert "TYPE: USER_INPUT" in journal, "Journal must contain USER_INPUT entry"
    assert "TYPE: DONE" in journal, "Journal must contain DONE entry"


def test_generator_has_4_tasks():
    """S-JTT-01.01: Journal covers 4 Tetris tasks (T1-T4)."""
    journal = generate_tetris_journal()
    tasks_found = set()
    for line in journal.split("\n"):
        if line.startswith("TASK: T-S-JTT-01-"):
            tasks_found.add(line.strip())
    assert len(tasks_found) == 4, f"Expected 4 unique task IDs, got {len(tasks_found)}: {tasks_found}"
