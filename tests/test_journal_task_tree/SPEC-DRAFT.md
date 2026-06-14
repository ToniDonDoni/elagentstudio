# SPEC-DRAFT: S-TETRIS-01 — Classic Tetris Game

**Spec ID:** S-TETRIS-01
**Version:** 2
**Date:** 2026-06-14
**Source:** USER_INPUT J-TETRIS-001

## §1 Entities

### Board
- 10 columns x 20 visible rows (+2 hidden buffer rows above for spawning)
- Cell states: empty (0) or filled with piece type index (1-7)
- Methods: `get_cell(x, y)`, `set_cell(x, y, val)`, `clear_row(y)`, `is_row_full(y)`, `shift_rows_down(from_row)`
- Coordinates: (0,0) = top-left visible cell; buffer rows at y = -2, -1

### Tetrominoes
- 7 standard pieces with shapes defined as (x, y) offsets from pivot:

**I piece:** `[(0, -1), (0, 0), (0, 1), (0, 2)]` — 4 rotation states (wall kicks: shift left/right if blocked)
**O piece:** `[(0, 0), (1, 0), (0, 1), (1, 1)]` — rotation is identity (no change)
**T piece:** `[(-1, 0), (0, 0), (1, 0), (0, -1)]`
**S piece:** `[(-1, 0), (0, 0), (0, -1), (1, -1)]`
**Z piece:** `[(1, 0), (0, 0), (0, -1), (-1, -1)]`
**J piece:** `[(-1, -1), (-1, 0), (0, 0), (1, 0)]`
**L piece:** `[(1, -1), (-1, 0), (0, 0), (1, 0)]`

- Rotation: apply 90° CW rotation matrix `(x, y) → (-y, x)` to each offset
- Wall kick: if rotated piece collides, try shifting left by 1, then right by 1, then up by 1
- Pivot is at (0, 0), spawn position at top-center of visible board: x = 5, y = 0

### Collision System
- **fit(piece_type, rotation, pos_x, pos_y):** check if piece at this position+rotation is within board bounds AND all cells are empty
- **Wall/floor:** piece must be within 0 ≤ x < 10 and y < 20 (buffer rows allowed during spawn)
- **Land:** when piece cannot move down, write piece cells to board
- **Line clearing:** check all rows 0-19, clear full rows, shift above rows down, count cleared lines
- **Scoring:** 1 line=100, 2=300, 3=500, 4=800

### Game Loop
- **Spawn:** new piece at x=4, y=0 with rotation=0. If blocked → game over
- **Gravity:** piece drops every N frames. N starts at 48, decreases by 1 per level (min 1)
- **Level:** starts at 0, +1 every 10 lines cleared
- **Input:** left (x-1), right (x+1), rotate CW, soft drop (drop 1, reset gravity timer), hard drop (drop until collision)
- **Game state:** {playing, paused, game_over}
- **Next piece:** preview of upcoming piece (optional for v1)

## §2 Tasks

| ID | Name | Description |
|----|------|-------------|
| T1 | Board model | 10×20 grid with cell ops, row clearing, row shift |
| T2 | Tetrominoes | 7 pieces with rotation states and wall kicks |
| T3 | Collision + scoring | Fit check, landing, line clearing, score calc |
| T4 | Game loop | Gravity timer, input, spawn, game state, game over |

## §3 Acceptance Criteria

### AC1 — Board
- Board initializes 10×20, all cells = 0
- `get_cell`/`set_cell` work within bounds (raise error out of bounds)
- `is_row_full(row)` returns True when row has all non-zero cells
- `clear_row(row)` sets row to 0 and shifts all rows above down by 1
- `shift_rows_down(from_row)` moves each row above from_row down by 1

### AC2 — Tetrominoes
- All 7 pieces return correct 4 cells for rotation 0
- `get_rotated(piece_type, rotation)` applies 90° CW rotation correctly
- I piece has 2 unique rotations, O has 1, all others have 4
- `get_spawn_position()` returns ("piece_type", 4, 0, 0) for any piece

### AC3 — Collision + scoring
- `fit()` detects wall collision (piece outside 0-9 x or below y=20)
- `fit()` detects collision with landed pieces
- `land(piece)` writes piece cells to board
- `clear_lines(board)` finds and clears all full rows, returns count
- `score(lines)` returns correct points per line count

### AC4 — Game loop
- Piece starts at spawn and descends by gravity
- Left/right moves piece, stops at wall
- Rotation changes piece state
- Hard drop moves piece to lowest valid Y instantly
- Lines cleared accumulate to score
- Level increases every 10 lines
- Game over when new piece cannot spawn
