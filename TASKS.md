# TASKS: S-JTT-01 — Journal Task Tree Traceability Test

**Spec:** S-JTT-01
**Date:** 2026-06-14
**Version:** 2

Tasks use hierarchical spec IDs: `S-JTT-01.NN`. All code goes in `tests/test_journal_task_tree.py`.
Each task builds on its predecessors.

## S-JTT-01.01 — Journal generator

**Spec ref:** R2 (fixture), R5 (scenario specifics)
**Acceptance:** `generate_tetris_journal() -> str` returns a string containing exactly 27 journal entries reproducing the full Tetris SDD lifecycle as specified in R5 entry table
**Dependencies:** None

## S-JTT-01.02 — Journal parser

**Spec ref:** R3 (foundation for all checks)
**Acceptance:** `parse_journal(text: str) -> list[dict]` parses journal text into structured entries with keys: jid, type, spec, status, parent, root, task, detail
**Dependencies:** S-JTT-01.01

## S-JTT-01.03 — Validation: structural checks (C1-C4)

**Spec ref:** R3 C1-C4
**Acceptance:**
- C1: All entries parseable — each `=== {JID} ===` section has a valid JID (non-empty, no whitespace)
- C2: USER_INPUT entries have `PARENT: --` sentinel
- C3: Every PARENT value either references a real entry JID or is `--` sentinel
- C4: No entry has PARENT equal to its own JID
**Dependencies:** S-JTT-01.02

## S-JTT-01.04 — Validation: chain integrity (C5-C7)

**Spec ref:** R3 C5-C7
**Acceptance:**
- C5: Following PARENT links from any entry terminates at `--` sentinel without revisiting entries
- C6: No two entries share the same JID
- C7: At least 1 USER_INPUT entry and at least 1 DONE entry exist
**Dependencies:** S-JTT-01.03 (uses parsed entries with PARENT validated)

## S-JTT-01.05 — Validation: ROOT field checks (C8-C10)

**Spec ref:** R3 C8-C10
**Acceptance:**
- C8: Every entry has a ROOT line with a JID value
- C9: All ROOT values in the journal are identical
- C10: The ROOT JID exists and its TYPE is USER_INPUT
**Dependencies:** S-JTT-01.04

## S-JTT-01.06 — Validation: TASK and SPEC field checks (C11-C13)

**Spec ref:** R3 C11-C13
**Acceptance:**
- C11: RED, GREEN, RED_REVIEW, GREEN_REVIEW entries have a TASK field
- C12: TASK values match `T-S-JTT-01-\d{3}` pattern
- C13: Every entry has a SPEC field with a non-empty value
**Dependencies:** S-JTT-01.05

## S-JTT-01.07 — Validation: completeness checks (C14-C15)

**Spec ref:** R3 C14-C15
**Acceptance:**
- C14: Every entry with TYPE != USER_INPUT has a PARENT field (even if value is `--`)
- C15: Starting at DONE entry, following PARENT links reaches a USER_INPUT with `PARENT: --`. All intermediate JIDs exist. No cycles.
**Dependencies:** S-JTT-01.06

## S-JTT-01.08 — Main test and synthetic error cases

**Spec ref:** R4, AC6-AC13
**Acceptance:**
- `test_journal_task_tree_compliance()`: clean 27-entry journal passes with zero errors
- Synthetic error tests (8 cases): self-reference (C4), cycle (C5), duplicate JID (C6), empty journal (C7), missing ROOT (C8), missing TASK (C11), orphan PARENT (C3), broken chain (C15) — each correctly detected
**Dependencies:** S-JTT-01.07
