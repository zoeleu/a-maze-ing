from lib import Config
from enum import IntFlag
from random import seed
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


class Maze:
    config: Config
    width: int
    length: int

    def __init__(self, config: Config):
        self.config = config
        self.width = config.width
        self.length = config.length
        
