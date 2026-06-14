# TASKS: S-JTT-01 — Journal Task Tree Traceability Test

**Spec:** S-JTT-01
**Date:** 2026-06-14

## Task 1: Journal generator (`generate_tetris_journal()`)

- **Spec ref:** R2, R5
- **Acceptance:** Function returns a string containing exactly 27 journal entries reproducing the full Tetris SDD lifecycle as specified in R5
- **Dependencies:** None
- **File:** `tests/test_journal_task_tree.py`

## Task 2: Journal parser (`parse_journal()`)

- **Spec ref:** R3 (needed by all C1-C15)
- **Acceptance:** Function parses journal text into `list[dict]` with keys: jid, type, spec, status, parent, root, task, detail
- **Dependencies:** Task 1 (generator provides the format)
- **File:** `tests/test_journal_task_tree.py`

## Task 3: Validation engine (`validate_journal()`)

- **Spec ref:** R3 (C1-C15)
- **Acceptance:** Function implements all 15 checks, returns `list[str]` errors in `JID=<jid> CHECK=<name> DETAIL=<detail>` format
- **Dependencies:** Task 2 (parser provides structured entries)
- **File:** `tests/test_journal_task_tree.py`

## Task 4: Test functions and synthetic error cases

- **Spec ref:** R4, AC6-AC13
- **Acceptance:** `test_journal_task_tree_compliance()` passes on clean journal; 8 synthetic error cases (self-ref, cycle, dup JID, empty, missing ROOT, missing TASK, orphan, broken chain) each produce correct validation errors
- **Dependencies:** Task 3 (validation engine)
- **File:** `tests/test_journal_task_tree.py`
