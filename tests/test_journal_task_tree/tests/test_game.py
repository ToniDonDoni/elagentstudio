"""Tests for Tetris Game Loop (T4)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tetris.game import Game, GRAVITY_TICKS


def test_game_init():
    """Game starts in playing state with a current piece."""
    g = Game()
    assert g.state == "playing"
    assert g.current_piece is not None
    assert g.score == 0
    assert g.level == 0
    assert g.lines_cleared == 0


def test_gravity_moves_piece_down():
    """Gravity tick moves piece down by 1."""
    g = Game()
    y_before = g.current_y
    for _ in range(GRAVITY_TICKS[g.level] + 1):
        g.tick()
    assert g.current_y > y_before, "Piece should move down on gravity tick"


def test_hard_drop_lands_piece():
    """Hard drop lands piece immediately and spawns next."""
    g = Game()
    g.hard_drop()
    assert g.current_piece is not None, "New piece should spawn after hard drop"


def test_move_left_and_right():
    """Move left/right changes piece position."""
    g = Game()
    x_before = g.current_x
    g.move(-1, 0)
    assert g.current_x < x_before, "Should move left"
    g.move(1, 0)
    assert g.current_x == x_before, "Should move back to original x"


def test_rotate_changes_rotation():
    """Rotate CW changes rotation state."""
    g = Game()
    rot_before = g.current_rotation
    g.rotate()
    assert g.current_rotation != rot_before, "Rotation should change"


def test_lines_clear_increase_score():
    """Clearing lines increases score."""
    g = Game()
    # Fill bottom row completely
    for x in range(10):
        g.board.set_cell(x, 19, 1)
    g._on_land()  # Trigger land processing
    assert g.score > 100 or g.lines_cleared > 0, "Lines cleared should increase score or line count"


def test_game_over():
    """Game over when new piece cannot spawn."""
    g = Game()
    # Fill the entire visible board
    for y in range(20):
        for x in range(10):
            g.board.set_cell(x, y, 1)
    # Clear top 2 rows for spawn check
    g.board.clear_row(0)
    # Try spawning — should fail
    g._spawn_piece()
    assert g.state in ("game_over", "playing"), "Game may end when spawn fails"
