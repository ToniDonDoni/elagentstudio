# Tetris Game — SDD Implementation Task

**Task ID:** T-S-JTT-01
**Spec ID:** S-JTT-01
**Date:** 2026-06-14

## Goal

Implement a classic Tetris game using the spec-driven TDD pipeline defined in SKILL.md.

## Entities

1. **Board** — 10x20 grid where blocks are placed
2. **Tetrominoes** — 7 standard pieces (I, O, T, S, Z, J, L) each with 4 rotation states
3. **Collision System** — detection of wall/floor/stack collisions, line clearing
4. **Game Loop** — gravity timer, input handling, scoring, game-over detection

## Tasks

| ID | Name | Description |
|----|------|-------------|
| T1 | Board model | 10x20 grid, cell storage, clear/query methods |
| T2 | Piece definitions | 7 tetrominoes with rotation matrices |
| T3 | Collision & line clear | Collision detection, completed row clearing |
| T4 | Game loop | Drop timer, input, scoring, game state machine |

## Acceptance Criteria

- All 4 tasks completed through the full SDD pipeline (RED → GREEN → REVIEW)
- JOURNAL_SDD_TDD_SKILL.log produced with complete, unbroken PARENT chain
- Every task entry traceable back to USER_INPUT
