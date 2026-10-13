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

from .algorithms import (Generator, GeneratorError, MazeHistoryCallbackCell,
                         history_callback)
from .wilsons import WilsonsGenerator
from .backtracker import BacktrackerGenerator


__all__ = [
    "Generator",
    "GeneratorError",
    "MazeHistoryCallbackCell",
    "history_callback",
    "WilsonsGenerator",
    "BacktrackerGenerator",
]
