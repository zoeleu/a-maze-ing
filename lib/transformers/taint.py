# A-Maze-Ing - A 42 School project to generate mazes.
# Copyright (C) 2026 Zoe T. Leullier
# Copyright (C) 2026 Flora P. C. Carvalho
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import random

import lib
from lib.algorithms import MazeHistoryCallbackCell
from .transformers import MazeTransformer


class TaintTransformer(MazeTransformer):
    """This transformer 'taints' the maze, by making it imperfect.
    It removes as many dead ends as it can, and opens the corners and
    center."""

    BLOCK = 3

    def _transform(self, maze: lib.Maze, seed: str | None) -> bool:
        """Knock down a wall next to every dead end.

        A wall is only removed if it does not create an open area of
        3x3 cells or more, so a few dead ends may survive when every
        possible wall would break that rule.

        Returns True if no dead end is left, False otherwise. Dead ends
        walled in by the logo and the border can never be opened, so they
        do not count.

        Reports to the history callbacks: MAYBE when a wall is tried, RESET
        when it has to be closed again or a dead end cannot be fixed, and
        OPEN when an opening stays.
        """
        # be deterministic, so the same maze is always transformed the same way
        random.seed(seed or None)
        # initial setup: open the logo's center corridor and the inner walls
        # of the corners
        self._open_center(maze)
        self._open_corners(maze)
        dead_ends = [
            (row, col)
            for row, col, _ in maze
            if self._is_dead_end(maze, (row, col))
        ]
        random.shuffle(dead_ends)

        for cell in dead_ends:
            if not self._is_dead_end(maze, cell):
                continue  # already fixed from a neighbouring dead end
            self._remove_dead_end(maze, cell)

        return not any(
            self._is_dead_end(maze, (row, col))
            and self._has_openable_wall(maze, (row, col))
            for row, col, _ in maze
        )

    def _open_center(self, maze: lib.Maze) -> None:
        """Open the corridor in the middle of the logo.

        It runs between the 4 and the 2: the three cells from the centre
        down, plus their links to the cell above and the cell below.
        Each step removes the south wall of a cell, so it has to start one
        row above the centre to open the top of the first corridor cell.
        """
        # if the maze has no logo, there's no corridor to open
        if not maze.has_logo:
            return
        row, col = maze.center_cell
        for top in ((row - 1, col), (row, col), (row + 1, col),
                    (row + 2, col)):
            below = (top[0] + 1, top[1])
            opened = maze.open_path(top, lib.Direction.SOUTH)
            if maze.is_open(top, lib.Direction.SOUTH):
                # mark the corridor cells so Maze.debug_render() draws them
                # as O (debugging aid only, does not change the maze)
                maze.marked.update({top, below})
            if opened:
                self._emit(top, MazeHistoryCallbackCell.OPEN)
                self._emit(below, MazeHistoryCallbackCell.OPEN)

    def _open_corners(self, maze: lib.Maze) -> None:
        """Open both inner walls of each corner, so a corner is a bend and
        never a dead end. Skips a wall that would create a 3x3 open area, or
        that touches the logo."""
        last_row, last_col = maze.rows - 1, maze.cols - 1
        # for each corner cell
        for corner in ((0, 0), (0, last_col), (last_row, 0),
                       (last_row, last_col)):
            # mark them as processing
            self._emit(corner, MazeHistoryCallbackCell.MAYBE)
            opened = False
            # for each neighbour
            for side in lib.Direction:
                # get the neighbour
                other = maze.neighbour(corner, side)
                # skip the sides facing out of the maze
                if other is None or other not in maze:
                    continue
                # skip walls that cannot be opened: already open, or
                # touching the logo
                if not maze.open_path(corner, side):
                    continue
                # mark the neighbour as processing
                self._emit(other, MazeHistoryCallbackCell.MAYBE)
                # if we created a 3x3 block, undo our change
                if self._has_open_block(maze, corner) or \
                        self._has_open_block(maze, other):
                    maze[corner] += side
                    maze[other] += side.opposite
                    # reset the cell state
                    self._emit(other, MazeHistoryCallbackCell.RESET)
                    continue
                opened = True
                # mark as open
                self._emit(other, MazeHistoryCallbackCell.OPEN)
            # marked is mostly for debugging
            if sum(1 for _ in maze.open_sides(corner)) == 2:
                maze.marked.add(corner)
            # send the appropriate message to the listening event handlers
            self._emit(corner, MazeHistoryCallbackCell.OPEN if opened
                       else MazeHistoryCallbackCell.RESET)

    @staticmethod
    def _is_dead_end(maze: lib.Maze, cell: lib.Cell) -> bool:
        """A playable cell with exactly one open side."""
        if maze.in_logo(cell):
            return False
        return sum(1 for _ in maze.open_sides(cell)) == 1

    @staticmethod
    def _has_openable_wall(maze: lib.Maze, cell: lib.Cell) -> bool:
        """Whether a closed side of the cell faces a playable cell."""
        for side in lib.Direction:
            other = maze.neighbour(cell, side)
            if other is None or other not in maze or maze.in_logo(other):
                continue
            if not maze.is_open(cell, side):
                return True
        return False

    def _remove_dead_end(self, maze: lib.Maze, cell: lib.Cell) -> bool:
        """Try to open one of the walls around the dead end, without
        creating an open BLOCK x BLOCK area. Returns True on success."""
        candidates: list[tuple[lib.Direction, lib.Cell]] = []
        for side in lib.Direction:
            other = maze.neighbour(cell, side)
            if other is None:
                continue
            if other not in maze or maze.in_logo(other):
                continue
            if maze.is_open(cell, side):
                continue
            candidates.append((side, other))

        random.shuffle(candidates)
        # Prefer joining two dead ends, which fixes both at once.
        candidates.sort(key=lambda c: not self._is_dead_end(maze, c[1]))

        # mark cell as processing
        self._emit(cell, MazeHistoryCallbackCell.MAYBE)
        # for each candidate for opening
        for side, other in candidates:
            # the candidates are closed walls between playable cells, so
            # this should always open; skip the wall just in case
            if not maze.open_path(cell, side):
                continue
            # mark the other one as processing too
            self._emit(other, MazeHistoryCallbackCell.MAYBE)
            # if we opened a 3x3 block, close again and try another one
            if self._has_open_block(maze, cell) or \
                    self._has_open_block(maze, other):
                maze[cell] += side
                maze[other] += side.opposite
                self._emit(other, MazeHistoryCallbackCell.RESET)
                continue
            # we did it, mark as open and return
            self._emit(other, MazeHistoryCallbackCell.OPEN)
            self._emit(cell, MazeHistoryCallbackCell.OPEN)
            return True
        # couldn't open
        self._emit(cell, MazeHistoryCallbackCell.RESET)
        return False

    def _has_open_block(self, maze: lib.Maze, cell: lib.Cell) -> bool:
        """Whether a BLOCK x BLOCK fully open area contains the cell."""
        row, col = cell
        span = range(self.BLOCK)
        # the top-left corners of every box that contains the cell
        corners = ((row - dr, col - dc) for dr in span for dc in span)
        for top, left in corners:
            # the set of cells in the box
            block = {(top + r, left + c) for r in span for c in span}
            # if every passage between the box's cells is open
            if all(maze.is_open(inner, side)
                   for inner in block for side in lib.Direction
                   if maze.neighbour(inner, side) in block):
                return True
        return False
