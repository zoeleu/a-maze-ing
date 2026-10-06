from lib.config import Config
from enum import IntFlag

from typing import Dict, Iterator, List, Tuple

# import sys
# import random

Cell = Tuple[int, int]


class Direction(IntFlag):
    NORTH = 1
    EAST = 2
    SOUTH = 4
    WEST = 8

    @property
    def opposite(self) -> "Direction":
        """The same wall seen from the neighbouring cell."""
        return _OPPOSITE[self]

    @property
    def step(self) -> Cell:
        """The (row, col) offset to the neighbour on this side."""
        return _STEP[self]


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

_LOGO = [(-2, -3), (-2, +1), (-2, +2), (-2, +3), (-1, -3), (-1, +3),
         (0, -3), (0, -2), (0, -1), (0, +1), (0, +2), (0, +3), (+2, +3),
         (+1, -1), (+1, +1), (+2, -1), (+2, +1), (+2, +2), (+2, +3)]


class Maze:
    grid: List[List[Direction]]
    rows: int
    cols: int
    center_cell: Cell

    def __init__(self, grid: List[List[Direction]]) -> None:
        self.grid = [col[:] for col in grid]
        self.rows = len(grid)
        self.cols = len(grid[0]) if grid else 0
        self.center_cell = ((self.rows - 1) // 2, (self.cols - 1) // 2)

    def __contains__(self, cell: Cell) -> bool:
        """Checks whether a given cell is in the mazes confines"""
        row, col = cell
        return 0 <= row < self.rows and 0 <= col < self.cols

    def __iter__(self) -> Iterator[Cell]:
        """Yields every cell in the maze"""
        for row in range(self.rows):
            for col in range(self.cols):
                yield row, col

    def walls(self, cell: Cell) -> int:
        """Gives access to which walls of a given cell are open"""
        row, col = cell
        return self.grid[row][col]

    def __setitem__(self, cell: Cell, directions: Direction) -> None:
        row, col = cell
        self.grid[row][col] = directions

    def neighbour(self, cell: Cell, side: Direction) -> Cell:
        """Returns the cell's neighbour in the given direction"""
        row, col = cell
        return (row + side.step[0], col + side.step[1])

    def in_logo(self, cell: Cell) -> bool:
        """Tells you if a given cell is part of the maze's 42 logo"""
        row, col = cell
        center_row, center_col = self.center_cell
        return (row - center_row, col - center_col) in _LOGO

    def is_open(self, cell: Cell, side: Direction) -> bool:
        """Tells you if a path between cells is open"""
        neighbour_cell = self.neighbour(cell, side)
        if neighbour_cell not in self:
            return False
        return side not in self.walls(cell) and \
            side not in self.walls(neighbour_cell)

    def open_sides(self, cell: Cell) -> Iterator[Direction]:
        for side in Direction:
            if self.is_open(cell, side):
                yield side

    def render(self) -> str:
        """Render the maze and its 42 logo as an ASCII map.
        REMOVE AFTERWARDS, THIS IS FOR DEBUGGING PURPOSES ONLY"""
        lines: List[str] = []
        for row in range(self.rows):
            top = "+"
            for col in range(self.cols):
                cell = (row, col)
                top += "   " if self.is_open(cell, Direction.NORTH) else "---"
                top += "+"
            lines.append(top)

            middle = "|"
            for col in range(self.cols):
                cell = (row, col)
                content = "42 " if self.in_logo(cell) else "   "
                middle += content
                middle += " " if self.is_open(cell, Direction.EAST) else "|"
            lines.append(middle)

        bottom = "+"
        for col in range(self.cols):
            cell = (self.rows - 1, col)
            bottom += "   " if self.is_open(cell, Direction.SOUTH) else "---"
            bottom += "+"
        lines.append(bottom)
        lines.append("42: logo")
        return "\n".join(lines)

    def open_path(self, cell: Cell, side: Direction) -> bool:
        """Tries to open a path between two cells,
         and returns True on success"""
        if self.is_open(cell, side):
            return False
        if self.in_logo(cell) or self.in_logo(self.neighbour(cell, side)):
            return False
        if self.neighbour(cell, side) not in self:
            return False
        self[cell] -= side
        self[self.neighbour(cell, side)] -= Direction.opposite()


class MazeGenerationError(Exception):
    pass


class MazeGenerator:
    config: Config
    width: int
    height: int
    grid: List[List[int]]
    maze: Maze

    def __init__(self, config: Config):
        self.config = config
        self.width = config.width
        self.height = config.height

        if self.height <= 5 or self.width <= 7:
            raise MazeGenerationError("Maze height/width is too small")

        self.grid = [[15 for i in range(self.height)]
                     for j in range(self.width)]
        self.maze = Maze(self.grid)

    def wilson_algorithm(self):
        pass


if __name__ == "__main__":
    all_dir = Direction.NORTH | Direction.EAST | \
        Direction.SOUTH | Direction.WEST
    row_max = 8
    col_max = 8
    for row in range(6, row_max + 1):
        for col in range(8, col_max + 1):
            maze = Maze([[all_dir for i in range(col)] for j in range(row)])
            print(maze.render())
