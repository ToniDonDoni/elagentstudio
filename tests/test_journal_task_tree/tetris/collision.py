"""Tetris Collision detection, landing, line clearing, and scoring."""

from tetris.board import Board
from tetris.pieces import get_rotated


def fit(board: Board, piece_type: str, rotation: int,
        pos_x: int, pos_y: int) -> bool:
    """Check if piece fits at (pos_x, pos_y) with given rotation.

    Returns True if all piece cells are within bounds and on empty cells.
    """
    offsets = get_rotated(piece_type, rotation)
    for dx, dy in offsets:
        x = pos_x + dx
        y = pos_y + dy
        # Allow buffer rows (y can be -1, -2 during spawn)
        if y < -2:
            return False
        if x < 0 or x >= board.width:
            return False
        if y >= board.height:
            return False
        # Check if cell is occupied (only for visible rows)
        if y >= 0 and board.get_cell(x, y) != 0:
            return False
    return True


def land(board: Board, piece_type: str, rotation: int,
         pos_x: int, pos_y: int):
    """Write piece cells to board."""
    offsets = get_rotated(piece_type, rotation)
    from tetris.pieces import COLORS
    color = COLORS[piece_type]
    for dx, dy in offsets:
        x = pos_x + dx
        y = pos_y + dy
        if 0 <= x < board.width and 0 <= y < board.height:
            board.set_cell(x, y, color)


def clear_lines(board: Board) -> int:
    """Clear all full rows, shift above down, return number cleared."""
    cleared = 0
    y = board.height - 1
    while y >= 0:
        if board.is_row_full(y):
            board.clear_row(y)
            cleared += 1
            # Re-check same y index (rows shifted down)
        else:
            y -= 1
    return cleared


def score(lines_cleared: int) -> int:
    """Calculate score for clearing N lines simultaneously."""
    return {1: 100, 2: 300, 3: 500, 4: 800}.get(lines_cleared, 0)
