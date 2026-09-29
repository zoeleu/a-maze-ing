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

LOGO = [(-3, +2), (-3, +1), (-3, 0), (-2, 0), (-1, 0), (-1, -1),
        (-1, -2), (+1, +2), (+1, 0), (+1, -1), (+1, -2), (+2, +2),
        (+2, 0), (+2, -2), (+3, +2), (+3, +1), (+3, 0), (+3, -2)]


class Maze:
    grid: List[List[int]]


    def __init__(self, grid: List[List[int]]):
        self.grid = [col[:] for col in grid]
        self.rows = len(grid)
        self.cols = len(grid[0]) if grid else 0
        self.center_cell = ((self.cols - 1) // 2, self.rows // 2)

    def __contains__(self, cell: Cell):
        row, col = cell
        return 0 <= row < self.rows and 0 <= col < self.cols

    def __iter__(self) -> Iterator[Cell]:
        for row in range(self.rows):
            for col in range(self.cols):
                yield row, col

    def in_logo(self, cell: Cell):
        row, col = cell
        center_row, center_col = self.center_cell
        return (row - center_row, col - center_col) in LOGO


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

        self.grid = [[0 for i in range(self.height)]
                     for j in range(self.width)]
        self.maze = Maze(self.grid)
        self.maze.add_logo

