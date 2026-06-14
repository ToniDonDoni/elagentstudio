#!/usr/bin/env python3
"""validate_journal.py — Standalone Journal Chain Validator.

Validates two core properties of an SDD journal:

  1. TRACEABILITY: From every entry, following PARENT chain reaches
     a USER_INPUT entry with PARENT: -- (root node).

  2. LINEARITY (after TASK_REVIEW): After the spec is decomposed into
     tasks and reviewed (TASK_REVIEW), the pipeline must be a strict
     linear chain — no entry can be the PARENT of more than one child.
     Before TASK_REVIEW, USER_INPUT may have multiple children
     (multiple specs).

Usage:
    python3 validate_journal.py JOURNAL_SDD_TDD_SKILL.log
    cat JOURNAL_SDD_TDD_SKILL.log | python3 validate_journal.py

Exit code:
    0 — all checks pass
    1 — validation errors found
"""

import sys
import os


# Allow importing from the same directory
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# Import parsing and validation from the test module
try:
    from test_journal_task_tree import parse_journal, validate_journal
except ImportError as e:
    print(f"ERROR: Could not import from test_journal_task_tree: {e}")
    print("Make sure validate_journal.py is in the same directory as")
    print("test_journal_task_tree.py")
    sys.exit(2)


def main() -> int:
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if not os.path.exists(filepath):
            print(f"ERROR: File not found: {filepath}", file=sys.stderr)
            return 1
        with open(filepath, encoding="utf-8") as f:
            journal_text = f.read()
    else:
        # Read from stdin
        journal_text = sys.stdin.read()

    if not journal_text.strip():
        print("ERROR: Empty journal input", file=sys.stderr)
        return 1

    entry_count = sum(1 for line in journal_text.split("\n") if line.strip().startswith("==="))
    print(f"Validating journal ({len(journal_text)} chars, "
          f"{entry_count} entries)...")

    errors = validate_journal(journal_text)

    if not errors:
        print("\nOK — All checks passed.")
        print("  ✓ Every entry traces to USER_INPUT (traceability)")
        print("  ✓ ROOT matches reached USER_INPUT (forest consistency)")
        print("  ✓ Branching allowed only at USER_INPUT / DECOMPOSE / TASK_REVIEW")
        print("  ✓ Linearity within task branches")
        return 0

    print(f"\nFAIL — {len(errors)} validation error(s):\n")
    for err in errors:
        print(f"  ✗ {err}")
    print()
    print(
        "Tip: run the full test suite for detailed diagnostics:\n"
        f"    python3 -m pytest {os.path.join(_THIS_DIR, 'test_journal_task_tree.py')} -v"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
