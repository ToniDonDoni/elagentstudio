"""Tetris Game Loop — gravity, input, scoring, game state."""

import random
from tetris.board import Board
from tetris.pieces import PIECES, get_rotated, get_spawn_position
from tetris.collision import fit, land, clear_lines, score

# Gravity: ticks per drop at each level (starts at 48, -1 per level, min 1)
GRAVITY_TICKS = [max(48 - level, 1) for level in range(100)]


class Game:
    """Main Tetris game controller."""

    def __init__(self):
        self.board = Board()
        self.score = 0
        self.level = 0
        self.lines_cleared = 0
        self.state = "playing"  # playing | paused | game_over
        self._gravity_counter = 0
        self.current_piece: str | None = None
        self.current_x: int = 0
        self.current_y: int = 0
        self.current_rotation: int = 0
        self._spawn_piece()

    def _spawn_piece(self):
        """Spawn a new piece at the top. If blocked, game over."""
        piece_type, x, y, rot = get_spawn_position()
        if fit(self.board, piece_type, rot, x, y):
            self.current_piece = piece_type
            self.current_x = x
            self.current_y = y
            self.current_rotation = rot
        else:
            self.state = "game_over"

    def _on_land(self):
        """Called when current piece lands on something."""
        if self.current_piece is None:
            return
        land(self.board, self.current_piece,
             self.current_rotation, self.current_x, self.current_y)
        cleared = clear_lines(self.board)
        if cleared > 0:
            self.score += score(cleared)
            self.lines_cleared += cleared
            self.level = self.lines_cleared // 10
        self._spawn_piece()

    def tick(self, n: int = 1):
        """Advance game by N ticks (gravity)."""
        if self.state != "playing" or self.current_piece is None:
            return
        for _ in range(n):
            self._gravity_counter += 1
            threshold = GRAVITY_TICKS[self.level]
            while self._gravity_counter >= threshold:
                self._gravity_counter -= threshold
                new_y = self.current_y + 1
                if fit(self.board, self.current_piece,
                       self.current_rotation, self.current_x, new_y):
                    self.current_y = new_y
                else:
                    self._on_land()
                    return

    def move(self, dx: int, dy: int):
        """Move current piece by (dx, dy). Does nothing if blocked."""
        if self.state != "playing" or self.current_piece is None:
            return
        new_x = self.current_x + dx
        new_y = self.current_y + dy
        if fit(self.board, self.current_piece,
               self.current_rotation, new_x, new_y):
            self.current_x = new_x
            self.current_y = new_y

    def rotate(self):
        """Rotate current piece 90° CW with wall kicks."""
        if self.state != "playing" or self.current_piece is None:
            return
        new_rot = (self.current_rotation + 1) % 4
        # Try basic rotation
        if fit(self.board, self.current_piece,
               new_rot, self.current_x, self.current_y):
            self.current_rotation = new_rot
            return
        # Wall kick: try shifting left by 1, right by 1, up by 1
        for kick_dx, kick_dy in [(-1, 0), (1, 0), (0, -1)]:
            if fit(self.board, self.current_piece,
                   new_rot, self.current_x + kick_dx, self.current_y + kick_dy):
                self.current_x += kick_dx
                self.current_y += kick_dy
                self.current_rotation = new_rot
                return

    def hard_drop(self):
        """Drop piece to lowest valid position instantly."""
        if self.state != "playing" or self.current_piece is None:
            return
        while fit(self.board, self.current_piece,
                  self.current_rotation, self.current_x, self.current_y + 1):
            self.current_y += 1
        self._on_land()
