"""Tetris Tetrominoes — 7 standard pieces with rotation."""

import random

# Piece shapes defined as (x, y) offsets from pivot at (0,0)
# Pivot is at the piece's origin; spawn position offsets apply
PIECES: dict[str, list[tuple[int, int]]] = {
    "I": [(0, -1), (0, 0), (0, 1), (0, 2)],
    "O": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "T": [(-1, 0), (0, 0), (1, 0), (0, -1)],
    "S": [(-1, 0), (0, 0), (0, -1), (1, -1)],
    "Z": [(1, 0), (0, 0), (0, -1), (-1, -1)],
    "J": [(-1, -1), (-1, 0), (0, 0), (1, 0)],
    "L": [(1, -1), (-1, 0), (0, 0), (1, 0)],
}

# Colors (ANSI/display indices, not critical for logic)
COLORS: dict[str, int] = {
    "I": 1, "O": 2, "T": 3, "S": 4, "Z": 5, "J": 6, "L": 7,
}


def _rotate_90_cw(offsets: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Apply 90° clockwise rotation: (x, y) → (-y, x)."""
    return [(-y, x) for (x, y) in offsets]


def get_rotated(piece_type: str, rotation: int) -> list[tuple[int, int]]:
    """Return piece offsets after N 90° CW rotations.

    Rotation is applied modulo 4 (0-3). rotation=4 returns original.
    """
    offsets = PIECES[piece_type]
    for _ in range(rotation % 4):
        offsets = _rotate_90_cw(offsets)
    return offsets


def get_spawn_position() -> tuple[str, int, int, int]:
    """Return (piece_type, x, y, rotation) for a new piece at spawn."""
    piece_type = random.choice(list(PIECES.keys()))
    return (piece_type, 4, 0, 0)
