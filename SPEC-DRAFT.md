# SPEC-DRAFT: S-JTT-01 — Journal Task Tree Traceability Test

**Spec ID:** S-JTT-01
**Version:** 1
**Date:** 2026-06-14
**Author:** Agent
**Source:** USER_INPUT J-20260614-010000-001

## §1 Problem

The SKILL.md defines a task-tree traceability mechanism: Task IDs with spec ancestry, unbroken PARENT chain, ROOT field, TASK field. However, there is no automated test that validates a real JOURNAL produced by an SDD run satisfies these requirements.

We need a test that:

1. Produces a synthetic or replay-based JOURNAL from a nontrivial SDD scenario (Tetris game implementation)
2. Validates that the JOURNAL conforms to all task-tree requirements:
   - Every entry (except USER_INPUT) has a PARENT that points to an existing JID
   - Following PARENT links from any entry eventually reaches a USER_INPUT with `PARENT: --`
   - No orphan entries (PARENT JID does not exist in journal)
   - No self-references (PARENT == entry's own JID)
   - No circular references (following PARENT returns to a previously visited JID)
   - ROOT field is present and consistent for all entries
   - TASK field is present for RED, GREEN, RED_REVIEW, GREEN_REVIEW entries
   - Task IDs follow the `T-{SPEC_ID}-{NNN}` format

## §2 Requirements

### R1 — Test file location and naming

- File: `tests/test_journal_task_tree.py`
- The test uses `pytest` framework

### R2 — Sample journal fixture

- The test creates a realistic sample JOURNAL by generating a Tetris SDD scenario
- The scenario covers: SPEC → SPEC_REVIEW → DECOMPOSE → TASK_REVIEW → per-task RED/GREEN cycle → REGRESSION → DONE
- At least 3 tasks, each with RED, RED_REVIEW, GREEN, GREEN_REVIEW entries
- Journal has proper JIDs, TYPEs, SPECs, STATUSes, PARENTs, ROOTs, TASKs, DETAILs
- A helper function `generate_tetris_journal() -> str` builds the journal text

### R3 — Validation function

The test includes a function `validate_journal(journal_text: str) -> list[str]` that returns a list of validation errors (empty list = all pass):

| Check | Logic |
|-------|-------|
| C1 — All entries parseable | `=== {JID} ===` — every entry has a valid JID |
| C2 — USER_INPUT has PARENT: -- | Root entries have no parent |
| C3 — Every PARENT JID exists | All PARENT values reference a real entry JID |
| C4 — No self-references | No entry has PARENT == its own JID |
| C5 — No circular references | Following PARENT links from any entry terminates at USER_INPUT without revisiting entries |
| C6 — ROOT field present on every entry | All entries have a ROOT JID |
| C7 — ROOT points to a real USER_INPUT | ROOT JID exists and its TYPE is USER_INPUT |
| C8 — TASK field on per-task entries | RED, GREEN, RED_REVIEW, GREEN_REVIEW have a TASK field |
| C9 — TASK ID format | TASK values match `T-S-JTT-01-\d{3}` pattern |
| C10 — SPEC field present | Every entry has a SPEC field |
| C11 — Chain completeness | From DONE entry, following PARENT reaches USER_INPUT |

### R4 — Test assertions

The test `test_journal_task_tree_compliance()`:
1. Calls `generate_tetris_journal()` to get a sample journal
2. Calls `validate_journal()` on it
3. Asserts `len(errors) == 0`, showing all errors if any

### R5 — Tetris scenario specifics

The simulated Tetris SDD run:
- **Spec:** S-JTT-01 (itself) — or a sub-spec S-JTT-01.01
- **Tasks:**
  - T1 (T-S-JTT-01-001): Board model — 10x20 grid, block storage
  - T2 (T-S-JTT-01-002): Piece definitions and rotation — 7 tetrominoes with rotation states
  - T3 (T-S-JTT-01-003): Collision detection and line clearing
  - T4 (T-S-JTT-01-004): Game loop — input handling, gravity, scoring
- Each task goes through RED (failing test) → RED_REVIEW (PASS) → GREEN (implementation) → GREEN_REVIEW (PASS)
- The REGRESSION step runs after each task (all green)
- FINAL_REVIEW and DONE at the end
- All entries use unbroken PARENT chain from DONE back to USER_INPUT

## §3 Acceptance Criteria

### AC1 — File exists
- `tests/test_journal_task_tree.py` exists

### AC2 — Test passes
- `pytest tests/test_journal_task_tree.py -v` returns PASSED

### AC3 — All 11 validation checks pass
- The test validates all C1-C11 from R3

### AC4 — Sample journal is realistic
- The Tetris journal has at least 20 entries spanning the full SDD lifecycle

### AC5 — Error reporting
- When validation finds errors, the error list is descriptive (contains entry JID + check name + detail)

### AC6 — Cyclic reference detection
- The validator detects cycles in PARENT chain (C5)

### AC7 — Self-reference detection
- The validator catches PARENT == entry's own JID (C4)

### AC8 — Missing ROOT detection
- The validator detects entries without ROOT field (C6)

### AC9 — Missing TASK detection
- The validator detects RED/GREEN entries without TASK field (C8)

## §4 Constraints

1. Pure Python — no external deps beyond pytest
2. No network access needed
3. The test must be self-contained (no filesystem side effects beyond reading the generated journal string)
4. Must work with `pytest tests/test_journal_task_tree.py` from project root
