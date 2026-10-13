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
from abc import ABC, abstractmethod
from typing import Callable
from enum import Enum, auto
import lib


class MazeHistoryCallbackCell(Enum):
    """What a generator or transformer reports about a cell to the history
    callbacks."""
    MAYBE = auto()  # cell is being considered for opening a wall
    OPEN = auto()   # cell was opened
    # cell went back to how it was (an erased loop, or an undone opening)
    RESET = auto()
    # every wall was closed again: the maze was unsolvable, so generation
    # starts over with a new seed. The cell it comes with means nothing.
    MAZE_RESET = auto()


# this is the type definition for a callback function to the history
# this will be used for renderers or any other system that needs to
# keep track of what the algorithms are doing, it will be called
# with the cell, and what the algorithm is thinking about
history_callback = Callable[[lib.Cell, MazeHistoryCallbackCell], None]


class GeneratorError(Exception):
    """Raised when a generator cannot build a maze at all."""


class Generator(ABC):
    """Base class of the maze generation algorithms. Subclasses implement
    _generate(), and report what they do through _emit()."""
    # all the callbacks that need to be updated when a cell changes
    _history_callback: list[history_callback]

    def __init__(self) -> None:
        """Create a generator with no history callback registered."""
        super().__init__()
        self._history_callback = []

    def generate(self, maze: lib.Maze) -> None:
        """Generate a maze in place.

        If the exit cannot be reached, every wall is closed again, MAZE_RESET
        is emitted (its cell means nothing), and the maze is generated again
        from a seed derived from the last one.
        """
        # define the initial seed
        cur_seed = maze.config.seed
        while True:
            # generate the maze
            self._generate(maze, cur_seed)
            try:
                # if the maze is solvable, just exit the loop and return
                maze.solve()
                break
            except ValueError:
                # the maze isn't solvable, deterministically get the next seed
                # and try again
                random.seed(cur_seed)
                cur_seed = random.randbytes(8).hex()
                closed = lib.Direction(sum(lib.Direction))
                for row, col, _ in maze:
                    maze[(row, col)] = closed
                self._emit((0, 0), MazeHistoryCallbackCell.MAZE_RESET)

    def register_history_callback(self, callback: history_callback) -> None:
        """Register a callback to be called whenever a cell is opened or
        reset."""
        self._history_callback.append(callback)

    def _emit(self, cell: lib.Cell, kind: MazeHistoryCallbackCell) -> None:
        """Tell every registered callback what just happened to *cell*.
        Generators call this from _generate()."""
        for callback in self._history_callback:
            callback(cell, kind)

    @abstractmethod
    def _generate(self, maze: lib.Maze, seed: str | None) -> None:
        """Carve a maze into *maze*, which starts with every wall closed,
        seeding the random module with *seed*."""
