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

from .maze import Maze, Cell, Direction, in_logo, logo_center, logo_fits
from .config import Config
from .algorithms import (Generator, GeneratorError, MazeHistoryCallbackCell,
                         history_callback, progress_callback,
                         WilsonsGenerator, BacktrackerGenerator)
from .transformers import MazeTransformer, TaintTransformer
from .mazegen import MazeGen, MazeGenResult


__all__ = [
    "Maze",
    "Cell",
    "Direction",
    "in_logo",
    "logo_center",
    "logo_fits",
    "Config",
    "Generator",
    "GeneratorError",
    "MazeHistoryCallbackCell",
    "history_callback",
    "progress_callback",
    "WilsonsGenerator",
    "BacktrackerGenerator",
    "MazeTransformer",
    "TaintTransformer",
    "MazeGen",
    "MazeGenResult"
]
