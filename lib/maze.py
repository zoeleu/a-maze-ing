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

from collections import deque
from enum import IntFlag
import sys
from typing import Dict, Iterator, List, Tuple
import random

from lib.config import Config

Cell = Tuple[int, int]


class Direction(IntFlag):
    """The four sides of a cell, as the bits the output file uses. A
    combination of them is the set of a cell's closed walls."""
    NORTH = 1
    EAST = 2
    SOUTH = 4
    WEST = 8

    @classmethod
    def random(cls) -> "Direction":
        """Returns a random direction"""
        return random.choice(list(cls))

    @classmethod
    def between(cls, cell: Cell, other: Cell) -> "Direction":
        """The direction that points from *cell* to an adjacent *other* cell.
        Raises a ValueError if the cells are not adjacent."""
        delta = (other[0] - cell[0], other[1] - cell[1])
        try:
            return _DIRECTION_BY_STEP[delta]
        except KeyError:
            raise ValueError(f"{other} is not adjacent to {cell}") from None

    @property
    def opposite(self) -> "Direction":
        """The same wall seen from the neighbouring cell."""
        return _OPPOSITE[self]

    @property
    def step(self) -> Cell:
        """The (row, col) offset to the neighbour on this side."""
        return _STEP[self]

    def __str__(self) -> str:
        """A single side as its letter (N, E, S or W), as used for the
        path in the output file; any other combination as a hex digit."""
        if self == Direction.NORTH:
            return "N"
        elif self == Direction.EAST:
            return "E"
        elif self == Direction.SOUTH:
            return "S"
        elif self == Direction.WEST:
            return "W"
        else:
            return f"{self.value:01x}"

    def __format__(self, format_spec: str) -> str:
        """Formats the walls as a number, e.g. f"{walls:01x}". Python 3.10
        would format the result of __str__ instead, a letter."""
        if not format_spec:
            return str(self)
        return format(self.value, format_spec)

    def has(self, other: "Direction | int") -> bool:
        """Whether any of the walls in *other* is closed here."""
        return bool(self & other)

    def __sub__(self, other: "Direction | int") -> "Direction":
        """These walls without the ones in *other*."""
        return Direction(self & ~other)

    def __add__(self, other: "Direction | int") -> "Direction":
        """These walls plus the ones in *other*."""
        return Direction(self | other)


_OPPOSITE: Dict[Direction, Direction] = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
}

_STEP: Dict[Direction, Cell] = {
    Direction.NORTH: (-1, 0),
    Direction.EAST: (0, 1),
    Direction.SOUTH: (1, 0),
    Direction.WEST: (0, -1),
}

_DIRECTION_BY_STEP: Dict[Cell, Direction] = {
    step: side for side, step in _STEP.items()
}

_LOGO = [(-2, -3), (-2, +1), (-2, +2), (-2, +3), (-1, -3), (-1, +3),
         (0, -3), (0, -2), (0, -1), (0, +1), (0, +2), (0, +3), (+2, +3),
         (+1, -1), (+1, +1), (+2, -1), (+2, +1), (+2, +2), (+2, +3)]


def logo_fits(rows: int, cols: int) -> bool:
    """Whether a maze of rows x cols cells is large enough for the 42 logo"""
    return rows >= 6 and cols >= 8


def logo_center(rows: int, cols: int) -> Cell:
    """The cell the 42 logo is centred on, in a maze of rows x cols cells"""
    return ((rows - 1) // 2, (cols - 1) // 2)


def in_logo(cell: Cell, rows: int, cols: int) -> bool:
    """Tells you if a given cell is part of the 42 logo of a maze of
    rows x cols cells. Always False if the maze is too small for the logo.
    Works without a Maze, so the config can be checked before building one."""
    if not logo_fits(rows, cols):
        return False
    center_row, center_col = logo_center(rows, cols)
    return (cell[0] - center_row, cell[1] - center_col) in _LOGO


class Maze:
    """A grid of cells, each holding its closed walls, with the 42 logo in
    the middle when the maze is large enough. Cells are (row, col), while
    the config gives the entry and exit as (x, y)."""
    grid: List[List[Direction]]
    rows: int
    cols: int
    center_cell: Cell
    has_logo: bool
    config: Config
    marked: set[Cell]  # cells debug_render() draws as O (debugging aid)

    def __init__(self, config: Config) -> None:
        """Create a maze of the config's size with every wall closed.
        Prints a warning on stderr if it is too small for the 42 logo."""
        rows = config.height
        cols = config.width
        self.config = config
        self.marked = set()
        self.grid = [[Direction(sum(Direction)) for _ in range(cols)]
                     for _ in range(rows)]
        self.rows = rows
        self.cols = cols
        self.center_cell = logo_center(rows, cols)
        self.has_logo = logo_fits(rows, cols)
        if not self.has_logo:
            print("Error: Maze is too small for the 42 logo, it should have a "
                  "width of at least 8 and a height of at least 6",
                  file=sys.stderr)

    def __contains__(self, cell: Cell) -> bool:
        """Checks whether a given cell is in the mazes confines"""
        row, col = cell
        return 0 <= row < self.rows and 0 <= col < self.cols

    def __iter__(self) -> Iterator[Tuple[int, int, Direction]]:
        """Iterates over all cells in the maze, yielding (row, col, directions)
        """
        for row in range(self.rows):
            for col in range(self.cols):
                yield row, col, self.grid[row][col]

    def __setitem__(self, cell: Cell, directions: Direction) -> None:
        """Sets the walls of a given cell to the given directions"""
        row, col = cell
        self.grid[row][col] = directions

    def __getitem__(self, cell: Cell) -> Direction:
        """Returns the walls of a given cell"""
        row, col = cell
        return self.grid[row][col]

    def neighbour(self, cell: Cell, side: Direction) -> Cell | None:
        """Returns the cell's neighbour in the given direction. The
        neighbour may be outside the maze; None only if *cell* itself is."""
        row, col = cell
        if cell not in self:
            return None
        return (row + side.step[0], col + side.step[1])

    def in_logo(self, cell: Cell) -> bool:
        """Tells you if a given cell is part of the maze's 42 logo.
        Always False if the maze is too small to contain the logo."""
        return in_logo(cell, self.rows, self.cols)

    def is_open(self, cell: Cell, side: Direction) -> bool:
        """Tells you if a path between cells is open"""
        neighbour_cell = self.neighbour(cell, side)
        if neighbour_cell is None:
            return False
        if neighbour_cell not in self:
            return False
        return not (self[cell].has(side) or
                    self[neighbour_cell].has(side.opposite))

    def open_sides(self, cell: Cell) -> Iterator[Direction]:
        """Iterates over all open sides of a given cell"""
        for side in Direction:
            if self.is_open(cell, side):
                yield side

    def debug_render(self) -> str:
        """Render the maze and its 42 logo as an ASCII map."""
        lines: List[str] = []
        # the config gives (x, y), while cells are (row, col)
        entry = (self.config.entry[1], self.config.entry[0])
        goal = (self.config.exit[1], self.config.exit[0])
        # cells on the solution, and which passages between them it follows
        trail = {entry}
        steps: set[Tuple[Cell, Direction]] = set()
        cell = entry
        for side in self.solve():
            other = self.neighbour(cell, side)
            assert other is not None  # satisfies type checker
            steps.add((cell, side))
            steps.add((other, side.opposite))
            trail.add(other)
            cell = other
        for row in range(self.rows):
            top = "+"
            for col in range(self.cols):
                cell = (row, col)
                if (cell, Direction.NORTH) in steps:
                    top += " . "
                elif self.is_open(cell, Direction.NORTH):
                    top += "   "
                else:
                    top += "---"
                top += "+"
            lines.append(top)

            middle = "|"
            for col in range(self.cols):
                cell = (row, col)
                if cell == entry:
                    content = " E "
                elif cell == goal:
                    content = " X "
                elif cell in self.marked:
                    content = " O "
                elif cell in trail:
                    content = " . "
                elif self.in_logo(cell):
                    content = "42 "
                else:
                    content = "   "
                middle += content
                if (cell, Direction.EAST) in steps:
                    middle += "."
                elif self.is_open(cell, Direction.EAST):
                    middle += " "
                else:
                    middle += "|"
            lines.append(middle)

        bottom = "+"
        for col in range(self.cols):
            cell = (self.rows - 1, col)
            if (cell, Direction.SOUTH) in steps:
                bottom += " . "
            elif self.is_open(cell, Direction.SOUTH):
                bottom += "   "
            else:
                bottom += "---"
            bottom += "+"
        lines.append(bottom)
        return "\n".join(lines)

    def get_output(self) -> str:
        """The maze in the output file format: one hex digit of closed
        walls per cell, a blank line, the entry and the exit as x,y, then
        the shortest path as N, E, S and W letters.

        Raises ValueError if the exit cannot be reached."""
        output = ""
        last_row = 0
        for row, _, directions in self:
            if row != last_row:
                output += "\n"
                last_row = row
            # hex
            output += f"{directions:01x}"
        # the config already gives (x, y), which is what the file expects
        output += "\n\n"
        output += f"{self.config.entry[0]},{self.config.entry[1]}"
        output += "\n"
        output += f"{self.config.exit[0]},{self.config.exit[1]}"

        output += "\n"
        output += "".join([str(d) for d in self.solve()])
        output += "\n"

        return output

    def solve(self) -> list[Direction]:
        """Returns a list of directions that lead from the entry to the exit.

        Floods the maze outwards from the entry, remembering for each cell
        the step it was first reached by, then walks that trail back from
        the exit. The result is a shortest path.
        """
        # the config gives (x, y), while cells are (row, col)
        start = (self.config.entry[1], self.config.entry[0])
        goal = (self.config.exit[1], self.config.exit[0])

        came_from: Dict[Cell, Tuple[Cell, Direction]] = {}
        seen = {start}
        queue = deque([start])
        while queue and goal not in seen:
            cell = queue.popleft()
            for side in self.open_sides(cell):
                other = self.neighbour(cell, side)
                if other is None or other in seen:
                    continue
                seen.add(other)
                came_from[other] = (cell, side)
                queue.append(other)

        if goal not in seen:
            raise ValueError("No path between the entry and the exit")

        path: list[Direction] = []
        cell = goal
        while cell != start:
            cell, side = came_from[cell]
            path.append(side)
        path.reverse()
        return path

    def open_path(self, cell: Cell, side: Direction) -> bool:
        """Tries to open a path between two cells,
         and returns True on success"""
        neighbour_cell = self.neighbour(cell, side)
        if neighbour_cell is None:
            return False
        if self.is_open(cell, side):
            return False
        if self.in_logo(cell) or self.in_logo(neighbour_cell):
            return False
        if neighbour_cell not in self:
            return False
        self[cell] -= side
        self[neighbour_cell] -= side.opposite
        return True


__all__ = ["Maze", "Direction", "Cell"]
