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

import lib
from abc import ABC, abstractmethod

from lib.algorithms import MazeHistoryCallbackCell, history_callback


class MazeTransformer(ABC):
    """Base class of the transformations applied to a generated maze.
    Subclasses implement _transform(), and report what they do through
    _emit()."""
    # check lib/algorithms/algorithms.py, the architecture is similar
    _history_callback: list[history_callback]

    def __init__(self) -> None:
        """Create a transformer with no history callback registered."""
        super().__init__()
        self._history_callback = []

    def transform(self, maze: lib.Maze) -> bool:
        """Transform the maze in place. Returns True if the transformer
        fully achieved its goal, False if it could only do part of it."""
        return self._transform(maze, maze.config.seed)

    def register_history_callback(self, callback: history_callback) -> None:
        """Register a callback to be called whenever a cell is opened or
        reset."""
        self._history_callback.append(callback)

    def _emit(self, cell: lib.Cell, kind: MazeHistoryCallbackCell) -> None:
        """Tell every registered callback what just happened to *cell*.
        Transformers call this from _transform()."""
        for callback in self._history_callback:
            callback(cell, kind)

    @abstractmethod
    def _transform(self, maze: lib.Maze, seed: str | None) -> bool:
        """Change *maze* in place, seeding the random module with *seed*.
        Returns True if the goal was fully achieved."""
