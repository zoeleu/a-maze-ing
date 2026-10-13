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

"""MazeGen: the whole maze generator behind a single class."""
import mazegen
from typing import TypedDict


class MazeGenResult(TypedDict):
    """What MazeGen.generate() returns.

    grid: the closed walls of every cell, indexed grid[y][x].
    solution: the shortest path from the entry to the exit, one Direction
        per step.
    fully_braided: in Pac-Man mode, whether every dead end could be removed;
        None for a perfect maze, which is not braided.
    """
    grid: list[list[mazegen.Direction]]
    solution: list[mazegen.Direction]
    fully_braided: bool | None


class MazeGen:
    """Generates a maze, with Wilson's algorithm unless another one is
    given, braids it into a Pac-Man board unless it is perfect, and
    solves it.

    Example:
        result = MazeGen(20, 15, (0, 0), (19, 14), seed="42").generate()
        result["grid"][0][0]          # walls of the top-left cell
        result["solution"]            # [Direction.EAST, ...]
    """
    maze: mazegen.Maze
    generator: mazegen.Generator
    transformer: mazegen.MazeTransformer | None

    def __init__(self, width: int, height: int,
                 entry: tuple[int, int], exit: tuple[int, int],
                 perfect: bool = True, seed: str | None = None,
                 algorithm: type[mazegen.Generator] = mazegen.WilsonsGenerator
                 ) -> None:
        """Set up a maze of *width* x *height* cells, with every wall closed.

        Args:
            width: number of columns, at least 1.
            height: number of rows, at least 1.
            entry: the entry cell, as (x, y).
            exit: the exit cell, as (x, y); a different cell from *entry*.
            perfect: True for a single path between any two cells, False for
                a Pac-Man board with loops and no dead ends.
            seed: the same seed and parameters always give the same maze;
                None picks a random one.
            algorithm: the generator class that carves the maze, e.g.
                BacktrackerGenerator for long corridors with few branches.

        Raises:
            ValueError: if the size is below 1, or the entry or exit is
                outside the maze, on the "42" pattern, or the same cell.
        """
        config = mazegen.Config.from_dict({
            'WIDTH': width,
            'HEIGHT': height,
            'ENTRY': entry,
            'EXIT': exit,
            'PERFECT': perfect,
            'SEED': seed,
            'OUTPUT_FILE': 'never_used_but_required'
        })
        # from_dict() does not check the values, and an exit that cannot be
        # reached would make the generator retry forever
        config.validate()
        self.maze = mazegen.Maze(config)
        self.generator = algorithm()
        if not perfect:
            self.transformer = mazegen.TaintTransformer()
        else:
            self.transformer = None

    def generate(self) -> MazeGenResult:
        """Generate the maze, braid it in Pac-Man mode, and solve it.

        Returns:
            A copy of the grid of walls, the shortest path from the entry
            to the exit, and whether braiding removed every dead end.
        """
        self.generator.generate(self.maze)
        fully_braided = None
        if self.transformer:
            fully_braided = self.transformer.transform(self.maze)
        return {
            # copy the grid
            'grid': [row[:] for row in self.maze.grid],
            'solution': self.maze.solve(),
            'fully_braided': fully_braided
        }
