"""Tetris Board model — 10x20 grid with cell operations."""


class Board:
    """10x20 Tetris board. Cells are 0 (empty) or 1-7 (piece type)."""

    def __init__(self, width: int = 10, height: int = 20):
        self.width = width
        self.height = height
        self._grid = [[0] * width for _ in range(height)]

    def get_cell(self, x: int, y: int) -> int:
        """Get cell value at (x, y)."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Cell ({x},{y}) out of bounds")
        return self._grid[y][x]

    def set_cell(self, x: int, y: int, value: int):
        """Set cell value at (x, y)."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Cell ({x},{y}) out of bounds")
        self._grid[y][x] = value

    def is_row_full(self, y: int) -> bool:
        """Check if row y is completely filled."""
        return all(cell != 0 for cell in self._grid[y])

    def clear_row(self, y: int):
        """Clear row y and shift all rows above down by 1."""
        if not (0 <= y < self.height):
            raise IndexError(f"Row {y} out of bounds")
        # Remove the row
        del self._grid[y]
        # Add empty row at top
        self._grid.insert(0, [0] * self.width)
