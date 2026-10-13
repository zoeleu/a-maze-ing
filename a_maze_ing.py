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

import sys
from sys import argv

from lib import Maze, WilsonsGenerator, TaintTransformer, Config

if __name__ == "__main__":
    maze = Maze(Config(argv[1]))
    generator = WilsonsGenerator()
    generator.generate(maze)
    if not maze.config.perfect:
        transformer = TaintTransformer()
        result = transformer.transform(maze)
        if not result:
            print("Warning: could not remove all dead ends from the maze",
                  file=sys.stderr)
    with open(maze.config.output_file, "w") as f:
        f.write(maze.get_output())
