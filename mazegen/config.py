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

from pathlib import Path
from typing import Callable, Any, TypedDict
import re

from typing_extensions import Self

# The widest and tallest maze, in cells. A cell takes about 1.8 KB while
# the maze is built and recorded for its replay, and the interface holds two
# mazes while it builds a new one: 1500 x 1500 cells fit in about 8 GB.
MAX_SIZE = 1500


class ConfigDict(TypedDict):
    """The parsed values of a config, keyed like the config file, for
    Config.from_dict()."""
    WIDTH: int
    HEIGHT: int
    ENTRY: tuple[int, int]
    EXIT: tuple[int, int]
    OUTPUT_FILE: str
    PERFECT: bool
    SEED: str | None


class Config:
    """A class that reads a config file and sets the attributes of the Config
    object accordingly. The config file should have the following format,
    one KEY=VALUE per line, with lines starting with # ignored:

    WIDTH=<int>
    HEIGHT=<int>
    ENTRY=<x>,<y>
    EXIT=<x>,<y>
    OUTPUT_FILE=<path>
    PERFECT=<True|False>
    SEED=<str>          (optional)
    """
    width: int
    height: int
    entry: tuple[int, int]
    exit: tuple[int, int]
    output_file: str
    perfect: bool
    seed: str | None = None

    def __init__(self, config_path: str):
        """Reads a config file and sets the attributes of the Config object
        accordingly."""
        path = Path(config_path)

        if not path.is_file():
            raise FileNotFoundError(f"Config file not found at {config_path}!")

        # Read the config file and store the key-value pairs in a dictionary
        kv = self.__read_file_dict(config_path)

        # Defines the regex patterns to check if
        # the values are valid
        check_dict: dict[str, str] = {
            "WIDTH": "^[0-9]+$",
            "HEIGHT": "^[0-9]+$",
            "ENTRY": "^[0-9]+,[0-9]+$",
            "EXIT": "^[0-9]+,[0-9]+$",
            "OUTPUT_FILE": r"^(?!.*\0).+$",
            "PERFECT": "^(True|False)$",
            "SEED": "^.*$"
        }

        # Defines the functions that parse the values
        parse_dict: dict[str, Callable[[str], Any]] = {
            "WIDTH": lambda w: int(w),
            "HEIGHT": lambda h: int(h),
            "ENTRY": lambda e: tuple(map(int, e.split(","))),
            "EXIT": lambda e: tuple(map(int, e.split(","))),
            "OUTPUT_FILE": lambda o: o,
            "PERFECT": lambda p: p == "True",
            "SEED": lambda s: s
        }

        mandatory = {
            "WIDTH",
            "HEIGHT",
            "ENTRY",
            "EXIT",
            "OUTPUT_FILE",
            "PERFECT"
        }

        if not mandatory.issubset(kv.keys()):
            raise IndexError(f"Missing the following keys: "
                             f"{mandatory.difference(kv.keys())}")

        for key in kv.keys():
            # unknown keys are skipped with a warning
            if key not in check_dict:
                print(f"Warning: Unknown key `{key}` in config file."
                      f"Ignoring...")
                continue
            # only possible if check_dict and parse_dict drift apart
            if key not in parse_dict:
                print(f"Warning: key `{key}` was found in config file but no "
                      f"parser is defined."
                      f"Ignoring...")
                continue
            if not re.match(check_dict[key], kv[key]):
                raise ValueError(f"Invalid value `{kv[key]}` at key \
                                 `{key}`: in config file")
            setattr(self, key.lower(), parse_dict[key](kv[key]))

        self.validate()

    def validate(self) -> None:
        """Checks that the values make a maze that can be built: a size
        between 1 and MAX_SIZE, and an entry and exit that are different
        cells, inside the maze and not on the 42 pattern. Raises a
        ValueError otherwise.

        Config(path) calls it; call it yourself after Config.from_dict(),
        which does not.
        """
        # check bounds
        for key, size in (("WIDTH", self.width), ("HEIGHT", self.height)):
            if size < 1:
                raise ValueError(f"Invalid value `{size}` at key `{key}`: "
                                 f"must be at least 1")
            if size > MAX_SIZE:
                raise ValueError(f"Invalid value `{size}` at key `{key}`: "
                                 f"must be at most {MAX_SIZE}")
        for key, (x, y) in (("ENTRY", self.entry), ("EXIT", self.exit)):
            if not 0 <= x < self.width:
                raise ValueError(f"Invalid value `{x},{y}` at key `{key}`: "
                                 f"x must be between 0 and {self.width - 1} "
                                 f"(WIDTH={self.width})")
            if not 0 <= y < self.height:
                raise ValueError(f"Invalid value `{x},{y}` at key `{key}`: "
                                 f"y must be between 0 and {self.height - 1} "
                                 f"(HEIGHT={self.height})")
        if self.entry == self.exit:
            raise ValueError(f"Invalid value `{self.exit[0]},{self.exit[1]}` "
                             f"at key `EXIT`: must be a different cell from "
                             f"ENTRY")

        # check the entry and exit are not walled in by the 42 logo.
        # Imported here: mazegen.maze imports this module, so importing it at
        # the top of the file would be circular.
        from mazegen.maze import in_logo
        for key, (x, y) in (("ENTRY", self.entry), ("EXIT", self.exit)):
            # the config gives (x, y), while cells are (row, col)
            if in_logo((y, x), self.height, self.width):
                raise ValueError(f"Invalid value `{x},{y}` at key `{key}`: "
                                 f"falls on the 42 pattern")

    @classmethod
    def from_dict(cls, config_dict: ConfigDict) -> Self:
        """Creates a Config object from a dictionary of key-value pairs,
        without checking them: call validate() for that."""
        instance = cls.__new__(cls)

        for key, value in config_dict.items():
            setattr(instance, key.lower(), value)

        return instance

    def __read_file_dict(self, filename: str) -> dict[str, str]:
        """Read *filename* into a KEY -> VALUE dict of raw strings, skipping
        comments and blank lines. A key given twice keeps its last value.
        Raises ValueError for a line that is not KEY=VALUE."""
        with open(filename) as file:
            lines_read = file.readlines()

        result: dict[str, str] = {}
        for number, line in enumerate(lines_read, start=1):
            # skip comments and empty lines
            if line.startswith("#") or line.strip() == "":
                continue
            if "=" not in line:
                raise ValueError(f"Line {number} is not KEY=VALUE: "
                                 f"`{line.strip()}`")
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
        return result
