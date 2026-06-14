"""Tests for Tetris Tetrominoes (T2)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tetris.pieces import PIECES, get_rotated, get_spawn_position


def test_all_7_pieces_defined():
    """All 7 standard tetrominoes exist with correct names."""
    assert set(PIECES.keys()) == {"I", "O", "T", "S", "Z", "J", "L"}


def test_each_piece_has_4_cells():
    """Each piece shape has exactly 4 cells."""
    for name, shape in PIECES.items():
        assert len(shape) == 4, f"{name} should have 4 cells, got {len(shape)}"


def test_o_piece_is_2x2():
    """O piece occupies exactly 4 cells in a square."""
    o = PIECES["O"]
    xs = [p[0] for p in o]
    ys = [p[1] for p in o]
    assert max(xs) - min(xs) == 1
    assert max(ys) - min(ys) == 1


def test_rotation_changes_shape():
    """Rotation 0 → 1 changes piece shape (except O)."""
    for name in PIECES:
        if name == "O":
            continue  # O is symmetric
        r0 = get_rotated(name, 0)
        r1 = get_rotated(name, 1)
        assert r0 != r1, f"{name} should change shape on rotation"


def test_4_rotations_return_to_original():
    """4 rotations (360°) return to original shape."""
    for name in PIECES:
        if name == "O":
            continue
        r0 = get_rotated(name, 0)
        r4 = get_rotated(name, 4)
        assert r0 == r4, f"{name} should return to original after 4 rotations"


def test_get_spawn_position():
    """Spawn position returns correct default."""
    piece_type, x, y, rot = get_spawn_position()
    assert piece_type in PIECES
    assert x == 4
    assert y == 0
    assert rot == 0
