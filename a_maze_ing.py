from lib import Config
from enum import IntFlag
import random
from typing import Dict, FrozenSet, Iterator, List, Optional, Set, Tuple
import sys

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

_LOGO = [(-3, +2), (-3, +1), (-3, 0), (-2, 0), (-1, 0), (-1, -1),
         (-1, -2), (+1, +2), (+1, 0), (+1, -1), (+1, -2), (+2, +2),
         (+2, 0), (+2, -2), (+3, +2), (+3, +1), (+3, 0), (+3, -2)]


class Maze:
    grid: List[List[int]]
    rows: int
    cols: int
    center_cell: Cell

    def __init__(self, grid: List[List[int]]) -> None:
        self.grid = [col[:] for col in grid]
        self.rows = len(grid)
        self.cols = len(grid[0]) if grid else 0
        self.center_cell = ((self.cols - 1) // 2, self.rows // 2)

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

    def __setitem__(self, cell: Cell, num: int) -> None:
        row, col = cell
        self.grid[row][col] = num

    def neighbour(self, cell: Cell, side: Direction) -> Cell:
        """Returns the cell's neighbour in the given direction"""
        row, col = cell
        step = side.step()
        return (row + step[0], col + step[1])

    def in_logo(self, cell: Cell) -> bool:
        """Tells you if a given cell is part of the maze's 42 logo"""
        row, col = cell
        center_row, center_col = self.center_cell
        return (row - center_row, col - center_col) in _LOGO

    def is_open(self, cell: Cell, side: Direction) -> bool:
        """Tells you if a path between cells is open"""
        return side in self.walls(cell)

    def open_path(self, cell: Cell, side: Direction)-> bool:
        """Tries to open a path between two cells, and returns True on success"""
        pass




class MazeError(Exception):
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
            raise MazeError("Maze height/width is too small")

        self.grid = [[15 for i in range(self.height)]
                     for j in range(self.width)]
        self.maze = Maze(self.grid)

    def wilson_algorithm(self)
