# SPEC-DRAFT: S-TETRIS-01 — Classic Tetris Game

**Spec ID:** S-TETRIS-01
**Version:** 1
**Date:** 2026-06-14
**Source:** USER_INPUT J-TETRIS-001

## §1 Entities

### Board
- 10 columns x 20 rows grid
- Cell states: empty (0) or filled (1-7 for piece type)
- Methods: `get_cell(x, y)`, `set_cell(x, y, val)`, `clear_row(y)`, `is_row_full(y)`

### Tetrominoes
- 7 standard pieces: I, O, T, S, Z, J, L
- Each piece has 4 rotation states (0°, 90°, 180°, 270°)
- Piece represented as list of `(x, y)` offsets from pivot
- Color assigned per piece type

### Collision System
- Check if piece fits at position with rotation
- Detect wall/floor collisions
- Land piece on board
- Clear completed rows
- Score: 1 line = 100, 2 = 300, 3 = 500, 4 = 800

### Game Loop
- Gravity: piece drops every N ticks (decreasing with level)
- Input handling: left, right, rotate CW, hard drop, soft drop
- Level increases every 10 cleared lines
- Game over when new piece can't spawn

## §2 Tasks

| ID | Name | Description |
|----|------|-------------|
| T1 | Board model | 10x20 grid with cell operations |
| T2 | Tetrominoes | 7 pieces with rotation states |
| T3 | Collision | Fit check, landing, line clearing |
| T4 | Game loop | Gravity, input, scoring, game state |

## §3 Acceptance Criteria

### AC1 — Board
- Board initializes as 10×20 empty grid
- `set_cell`/`get_cell` work correctly
- `is_row_full` detects full rows
- `clear_row` removes a row and shifts above down

### AC2 — Tetrominoes
- All 7 pieces defined with correct shapes
- Rotation produces correct 4 states (I piece special case)
- Can retrieve piece by type string

### AC3 — Collision
- Detects wall collision (left, right, bottom)
- Detects collision with landed pieces
- Piece lands correctly: cells set on board
- Line clearing works with scoring

### AC4 — Game loop
- Piece drops on timer
- Left/right/rotate inputs work
- Hard drop lands instantly
- Lines cleared → score + level up
- Game over triggers correctly
