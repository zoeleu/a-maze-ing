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

import mazegen
from .algorithms import Generator, MazeHistoryCallbackCell


class BacktrackerGenerator(Generator):
    """The recursive backtracker: a randomised depth-first search, which
    makes long winding corridors with few branches and few dead ends."""

    def _generate(self, maze: mazegen.Maze, seed: str | None) -> None:
        """Generate a perfect maze with a randomised depth-first search.

        From a random cell, it keeps carving into a random neighbour it has
        not visited yet, and backs up when there is none, until it is back
        at the start. The path is kept on a list rather than in recursive
        calls, so big mazes do not hit Python's recursion limit.

        Cells that belong to the 42 logo stay walled off. The maze is
        expected to start with every wall closed.

        Reports to the history callbacks: MAYBE when a cell is added to the
        path, and OPEN when the search backs up out of it for good, so the
        cells between a MAYBE and their OPEN are the current path.
        """
        random.seed(seed or None)
        neighbours = self._neighbours(maze)

        start = random.choice(list(neighbours))
        visited = {start}
        path = [start]
        self._emit(start, MazeHistoryCallbackCell.MAYBE)
        while path:
            cell = path[-1]
            unvisited = [other for other in neighbours[cell]
                         if other not in visited]
            if not unvisited:
                # a dead end: back up to the last cell with somewhere to go
                path.pop()
                self._emit(cell, MazeHistoryCallbackCell.OPEN)
                continue
            other = random.choice(unvisited)
            maze.open_path(cell, mazegen.Direction.between(cell, other))
            visited.add(other)
            path.append(other)
            self._emit(other, MazeHistoryCallbackCell.MAYBE)
