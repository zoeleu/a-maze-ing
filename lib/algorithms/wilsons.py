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
from .algorithms import Generator, MazeHistoryCallbackCell


class WilsonsGenerator(Generator):
    def _generate(self, maze: lib.Maze, seed: str | None) -> None:
        """Generate a perfect maze using Wilson's algorithm.

        Cells that belong to the 42 logo stay walled off, so the walks are
        restricted to the remaining playable cells. The maze is expected to
        start with every wall closed.

        Reports to the history callbacks: MAYBE when a walk reaches a cell,
        RESET when a loop of the walk is erased, and OPEN when a cell joins
        the maze. The walk ends on a cell already in the maze, which gets
        its MAYBE too, and its OPEN once the walk is carved into it.
        """
        random.seed(seed or None)
        playable = [
            (row, col)
            for row, col, _ in maze
            if not maze.in_logo((row, col))
        ]
        if not playable:
            raise lib.GeneratorError("No playable cells to generate a maze")

        neighbours: dict[lib.Cell, list[lib.Cell]] = {}
        for cell in playable:
            neighbours[cell] = []
            for side in lib.Direction:
                other = maze.neighbour(cell, side)
                if other is None:
                    continue
                if other in maze and not maze.in_logo(other):
                    neighbours[cell].append(other)

        first = random.choice(playable)
        in_tree = {first}
        self._emit(first, MazeHistoryCallbackCell.OPEN)

        for start in playable:
            if start in in_tree:
                continue

            # Random walk until the tree is hit. When the walk steps back
            # onto itself, the loop it just made is erased.
            path = [start]
            position = {start: 0}  # where each cell sits in the path
            self._emit(start, MazeHistoryCallbackCell.MAYBE)
            while path[-1] not in in_tree:
                cell = random.choice(neighbours[path[-1]])
                if cell in position:
                    # undo the loop from the head back to where it started
                    for erased in reversed(path[position[cell] + 1:]):
                        del position[erased]
                        self._emit(erased, MazeHistoryCallbackCell.RESET)
                    del path[position[cell] + 1:]
                    continue
                position[cell] = len(path)
                path.append(cell)
                self._emit(cell, MazeHistoryCallbackCell.MAYBE)

            # Carve the loop-erased walk into the maze.
            for cell, other in zip(path, path[1:]):
                maze.open_path(cell, lib.Direction.between(cell, other))
                in_tree.add(cell)
                self._emit(cell, MazeHistoryCallbackCell.OPEN)
            # the cell the walk ended on was already in the maze, and now
            # has the walk's last passage opened onto it
            self._emit(path[-1], MazeHistoryCallbackCell.OPEN)
