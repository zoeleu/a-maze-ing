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

"""Run the UI on its own: python3 -m lib.ui config.txt"""
import sys

from lib.ui import AMazeIngApp

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 -m lib.ui <config file>", file=sys.stderr)
        sys.exit(1)
    AMazeIngApp(sys.argv[1]).run()
