"""Tests for Tetris Board model (T1)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tetris.board import Board


def test_board_init():
    """Board initializes as 10x20 empty grid."""
    b = Board()
    assert b.width == 10
    assert b.height == 20
    for y in range(20):
        for x in range(10):
            assert b.get_cell(x, y) == 0, f"Cell ({x},{y}) should be 0"


def test_set_and_get_cell():
    """set_cell and get_cell work correctly."""
    b = Board()
    b.set_cell(5, 10, 3)
    assert b.get_cell(5, 10) == 3
    assert b.get_cell(0, 0) == 0


def test_is_row_full():
    """is_row_full detects full and partial rows."""
    b = Board()
    assert not b.is_row_full(0), "Empty row is not full"
    for x in range(10):
        b.set_cell(x, 5, 1)
    assert b.is_row_full(5), "Row 5 should be full"


def test_clear_row():
    """clear_row removes a row and shifts above down."""
    b = Board()
    # Fill row 5
    for x in range(10):
        b.set_cell(x, 5, 1)
    # Place something above
    b.set_cell(3, 3, 2)
    b.clear_row(5)
    # Row 5 should now be empty
    for x in range(10):
        assert b.get_cell(x, 5) == 0, f"Cell ({x},5) should be 0 after clear"
    # Row 3 should have shifted to row 4
    assert b.get_cell(3, 4) == 2, "Row above should shift down"
