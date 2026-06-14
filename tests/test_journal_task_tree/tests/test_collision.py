"""Tests for Tetris Collision detection and scoring (T3)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tetris.board import Board
from tetris.pieces import PIECES, get_rotated
from tetris.collision import fit, land, clear_lines, score


def test_fit_returns_true_for_empty_board():
    """A piece fits on empty board at valid position."""
    b = Board()
    assert fit(b, "T", 0, 5, 0), "T piece should fit at top center"


def test_fit_wall_collision_left():
    """Piece outside left wall returns False."""
    b = Board()
    # I piece at x=-1 → would have cell at x=-1
    assert not fit(b, "I", 0, -1, 0), "Should detect left wall"


def test_fit_wall_collision_right():
    """Piece outside right wall returns False."""
    b = Board()
    # T piece at x=9 → rightmost cell at x=10, outside
    assert not fit(b, "T", 0, 9, 0), "Should detect right wall"


def test_fit_collision_with_landed_piece():
    """Piece overlapping landed piece returns False."""
    b = Board()
    b.set_cell(5, 1, 1)  # Block at position where T piece would be
    assert not fit(b, "T", 0, 5, 1), "Should detect collision"


def test_land_writes_to_board():
    """land() writes piece cells to board."""
    b = Board()
    land(b, "T", 0, 5, 18)
    assert b.get_cell(5, 18) != 0, "Pivot cell should be set"
    assert b.get_cell(4, 18) != 0, "Left cell should be set"


def test_clear_lines_removes_full_rows():
    """clear_lines detects and removes full rows, returns count."""
    b = Board()
    # Fill bottom row
    for x in range(10):
        b.set_cell(x, 19, 1)
    # Fill second-to-last row partially
    b.set_cell(3, 18, 1)
    cleared = clear_lines(b)
    assert cleared == 1, f"Expected 1 cleared line, got {cleared}"
    assert b.get_cell(0, 19) == 0, "Row 19 should be empty after clear"


def test_score_calculation():
    """score() returns correct points per line count."""
    assert score(1) == 100
    assert score(2) == 300
    assert score(3) == 500
    assert score(4) == 800
