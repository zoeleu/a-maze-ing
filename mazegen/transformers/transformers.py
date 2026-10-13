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

import mazegen
from abc import ABC, abstractmethod

from mazegen.algorithms import (MazeHistoryCallbackCell, history_callback,
                                progress_callback)


class MazeTransformer(ABC):
    """Base class of the transformations applied to a generated maze.
    Subclasses implement _transform(), and report what they do through
    _emit() and _report()."""
    # check mazegen/algorithms/algorithms.py, the architecture is similar
    _history_callback: list[history_callback]
    _progress_callback: list[progress_callback]

    def __init__(self) -> None:
        """Create a transformer with no callback registered."""
        super().__init__()
        self._history_callback = []
        self._progress_callback = []

    def transform(self, maze: mazegen.Maze) -> bool:
        """Transform the maze in place. Returns True if the transformer
        fully achieved its goal, False if it could only do part of it."""
        return self._transform(maze, maze.config.seed)

    def register_history_callback(self, callback: history_callback) -> None:
        """Register a callback to be called whenever a cell is opened or
        reset."""
        self._history_callback.append(callback)

    def _emit(self, cell: mazegen.Cell, kind: MazeHistoryCallbackCell) -> None:
        """Tell every registered callback what just happened to *cell*.
        Transformers call this from _transform()."""
        for callback in self._history_callback:
            callback(cell, kind)

    def register_progress_callback(self, callback: progress_callback) -> None:
        """Register a callback to be told how far the transformation has
        got."""
        self._progress_callback.append(callback)

    def _report(self, step: str, done: int, total: int) -> None:
        """Tell every registered progress callback that *done* out of
        *total* of *step* is done. Transformers call this from
        _transform()."""
        for callback in self._progress_callback:
            callback(step, done, total)

    @abstractmethod
    def _transform(self, maze: mazegen.Maze, seed: str | None) -> bool:
        """Change *maze* in place, seeding the random module with *seed*.
        Returns True if the goal was fully achieved."""
