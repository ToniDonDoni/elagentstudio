# SPEC-DRAFT: S-JTT-01 — Journal Task Tree Traceability Test

**Spec ID:** S-JTT-01
**Version:** 2
**Date:** 2026-06-14
**Author:** Agent
**Source:** USER_INPUT J-20260614-010000-001
**Review:** SPEC REVIEW FAIL (J-20260614-010200-001) — all 12 issues fixed in v2

## §1 Problem

The SKILL.md defines a task-tree traceability mechanism: Task IDs with spec ancestry, unbroken PARENT chain, ROOT field, TASK field. However, there is no automated test that validates a real JOURNAL produced by an SDD run satisfies these requirements.

We need a test that:

1. Produces a synthetic sample JOURNAL from a nontrivial SDD scenario (Tetris game implementation)
2. Validates that the JOURNAL conforms to all task-tree requirements:
   - Every entry (except USER_INPUT) has a PARENT field that points to an existing JID
   - Following PARENT links from any entry eventually reaches a USER_INPUT with `PARENT: --`
   - No orphan entries (PARENT JID does not exist in journal)
   - No self-references (PARENT = entry's own JID)
   - No circular references (following PARENT returns to a previously visited JID)
   - ROOT field is present on every entry, and all entries share the same ROOT value (pointing to the single USER_INPUT)
   - TASK field is present for RED, GREEN, RED_REVIEW, GREEN_REVIEW entries
   - Task IDs follow the `T-{SPEC_ID}-{NNN}` format where SPEC_ID = S-JTT-01
   - All JIDs are unique within the journal
   - At minimum, the journal contains at least one USER_INPUT and one DONE entry

## §2 Requirements

### R1 — Test file location and naming

- File: `tests/test_journal_task_tree.py`
- The test uses `pytest` framework

### R2 — Sample journal fixture

- The test creates a realistic sample JOURNAL by generating a Tetris SDD scenario
- The scenario covers: USER_INPUT → SPEC_SPEC → SPEC_REVIEW → DECOMPOSE → TASK_REVIEW → (RED → RED_REVIEW → GREEN → GREEN_REVIEW per task) → REGRESSION → FINAL_REVIEW → DONE
- Exactly 4 tasks, each with RED, RED_REVIEW, GREEN, GREEN_REVIEW entries
- Journal has proper JIDs, TYPEs, SPECs, STATUSes, PARENTs, ROOTs, TASKs, DETAILs
- A helper function `generate_tetris_journal() -> str` builds the journal text
- The journal is a Python string in memory (no filesystem I/O)

### R3 — Validation checks

The test includes a function `validate_journal(journal_text: str) -> list[str]` that returns a list of validation error strings (empty list = all pass). Each error is a single descriptive string in format:

```
JID=<jid> CHECK=<check_name> DETAIL=<detail>
```

| # | Check | Logic |
|---|-------|-------|
| C1 | All entries parseable | Every `=== {JID} ===` section has a valid JID (non-empty, no whitespace) |
| C2 | USER_INPUT has PARENT: -- | Root entries use the sentinel `--` (two ASCII hyphens) |
| C3 | Every PARENT JID exists or is sentinel | All PARENT values either reference a real entry JID OR are `--` (sentinel). Non-sentinel values must match an existing entry |
| C4 | No self-references | No entry has PARENT equal to its own JID |
| C5 | No circular references | Following PARENT links from any entry terminates at a `--` sentinel without revisiting entries. Sentinel values stop traversal — they are not checked for existence beyond C3 |
| C6 | Unique JIDs | No two entries share the same JID |
| C7 | Minimum entry count | At least 1 USER_INPUT entry and at least 1 DONE entry exist |
| C8 | ROOT field present on every entry | All entries have a ROOT line with a JID value |
| C9 | ROOT is consistent | All ROOT values in the journal are identical (same JID for all entries) |
| C10 | ROOT points to a real USER_INPUT | The ROOT JID exists and its TYPE is USER_INPUT |
| C11 | TASK field on per-task entries | RED, GREEN, RED_REVIEW, GREEN_REVIEW have a TASK field |
| C12 | TASK ID format | TASK values match `T-S-JTT-01-\d{3}` pattern |
| C13 | SPEC field present | Every entry has a SPEC field with a non-empty value |
| C14 | Non-USER_INPUT must have PARENT field | Every entry with TYPE != USER_INPUT has a PARENT field (even if value is `--`) |
| C15 | Chain completeness | Starting at DONE entry, repeatedly following PARENT links eventually reaches a USER_INPUT with `PARENT: --`. Extract the PARENT value from each entry; stop traversal at sentinel `--`. Each intermediate JID must exist in the journal. All steps must complete without revisiting a JID (cycle detection, same as C5) |

### R4 — Test assertions

The test `test_journal_task_tree_compliance()`:
1. Calls `generate_tetris_journal()` to get a sample journal string in memory
2. Calls `validate_journal()` on it
3. Asserts `len(errors) == 0`, showing all errors if any (pytest `assert` with descriptive message joining errors by newline)

### R5 — Tetris scenario specifics

The simulated Tetris SDD run uses spec ID `S-JTT-01` (not `S-JTT-01.01`):

**Entry sequence and PARENT chain:**

```
Entry #  | TYPE             | PARENT                      | TASK
---------|------------------|-----------------------------|-------
E01      | USER_INPUT       | --                          | —
E02      | SPEC_SPEC        | E01                         | —
E03      | SPEC_REVIEW      | E02                         | —
E04      | DECOMPOSE        | E03                         | —
E05      | TASK_REVIEW      | E04                         | —
E06      | RED              | E05                         | T-S-JTT-01-001
E07      | RED_REVIEW       | E06                         | T-S-JTT-01-001
E08      | GREEN            | E07                         | T-S-JTT-01-001
E09      | GREEN_REVIEW     | E08                         | T-S-JTT-01-001
E10      | REGRESSION       | E09                         | —
E11      | RED              | E10                         | T-S-JTT-01-002
E12      | RED_REVIEW       | E11                         | T-S-JTT-01-002
E13      | GREEN            | E12                         | T-S-JTT-01-002
E14      | GREEN_REVIEW     | E13                         | T-S-JTT-01-002
E15      | REGRESSION       | E14                         | —
E16      | RED              | E15                         | T-S-JTT-01-003
E17      | RED_REVIEW       | E16                         | T-S-JTT-01-003
E18      | GREEN            | E17                         | T-S-JTT-01-003
E19      | GREEN_REVIEW     | E18                         | T-S-JTT-01-003
E20      | REGRESSION       | E19                         | —
E21      | RED              | E20                         | T-S-JTT-01-004
E22      | RED_REVIEW       | E21                         | T-S-JTT-01-004
E23      | GREEN            | E22                         | T-S-JTT-01-004
E24      | GREEN_REVIEW     | E23                         | T-S-JTT-01-004
E25      | REGRESSION       | E24                         | —
E26      | FINAL_REVIEW     | E25                         | —
E27      | DONE             | E26                         | —
```

**Tasks:**
- Task 1 (T-S-JTT-01-001): Board model — 10x20 grid, block storage
- Task 2 (T-S-JTT-01-002): Piece definitions and rotation — 7 tetrominoes with rotation states
- Task 3 (T-S-JTT-01-003): Collision detection and line clearing
- Task 4 (T-S-JTT-01-004): Game loop — input handling, gravity, scoring

Each task goes through RED (failing test, STATUS=COMPLETED) → RED_REVIEW (STATUS=PASS) → GREEN (implementation, STATUS=COMPLETED) → GREEN_REVIEW (STATUS=PASS).

REGRESSION after each task (STATUS=PASS).
FINAL_REVIEW (STATUS=PASS) and DONE (STATUS=COMPLETED) at the end.

**PARENT chain rules for this scenario:**
- USER_INPUT has `PARENT: --`
- SPEC_SPEC PARENT = USER_INPUT
- SPEC_REVIEW PARENT = the artifact being reviewed (SPEC_SPEC)
- DECOMPOSE PARENT = SPEC_REVIEW (the review that approved the spec)
- TASK_REVIEW PARENT = DECOMPOSE
- RED PARENT = TASK_REVIEW (for T1) or REGRESSION (for T2-T4)
- RED_REVIEW PARENT = RED entry
- GREEN PARENT = RED_REVIEW entry
- GREEN_REVIEW PARENT = GREEN entry
- REGRESSION PARENT = GREEN_REVIEW entry
- FINAL_REVIEW PARENT = last REGRESSION entry
- DONE PARENT = FINAL_REVIEW

All entries share ROOT = JID of the USER_INPUT entry.

## §3 Acceptance Criteria

### AC1 — File exists
- `tests/test_journal_task_tree.py` exists

### AC2 — Test passes
- `pytest tests/test_journal_task_tree.py -v` returns PASSED

### AC3 — All 15 validation checks implemented
- The test implements C1-C15 from R3

### AC4 — Sample journal is realistic
- The Tetris journal has exactly 27 entries spanning the full SDD lifecycle (as per R5 table)

### AC5 — Error reporting format
- Each error is string formatted as `JID=<jid> CHECK=<name> DETAIL=<detail>`
- Multiple errors joined by newline in pytest assert message

### AC6 — Cyclic reference detection
- The validator detects cycles in PARENT chain (C5)
- Test includes at least one synthetic case that creates a cycle and verifies it is caught

### AC7 — Self-reference detection
- The validator catches PARENT = entry's own JID (C4)
- Test includes a synthetic case

### AC8 — Missing ROOT detection
- The validator detects entries without ROOT field (C8)
- Test includes a synthetic case

### AC9 — Missing TASK detection
- The validator detects RED/GREEN entries without TASK field (C11)
- Test includes a synthetic case

### AC10 — Orphan detection
- The validator catches PARENT pointing to non-existent JID (C3)
- Test includes a synthetic case

### AC11 — Duplicate JID detection
- The validator catches duplicate JIDs (C6)
- Test includes a synthetic case

### AC12 — Empty journal detection
- The validator rejects empty journals via C7 (minimum entry count)
- Test includes synthetic case with empty journal

### AC13 — Broken chain detection
- The validator catches DONE entry whose PARENT chain doesn't reach USER_INPUT (C15)
- Test includes a synthetic case

## §4 Constraints

1. Pure Python — no external dependencies beyond pytest
2. No network access needed
3. The test must be self-contained with no filesystem side effects. The journal is generated as a Python string in memory.
4. Must work with `pytest tests/test_journal_task_tree.py -v` from project root
