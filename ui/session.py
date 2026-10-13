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

"""The bridge between the screens and the maze library.

Nothing in here knows about Textual: it loads the config, builds mazes and
keeps what the screens need to draw them, and to replay how they were built.
"""
import copy
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from mazegen import (Cell, Config, Direction, Generator, GeneratorError,
                     Maze, MazeHistoryCallbackCell, TaintTransformer,
                     WilsonsGenerator)

CLOSED = Direction.NORTH | Direction.EAST | Direction.SOUTH | Direction.WEST

# The generators the UI can pick from, with the name it shows for each.
ALGORITHMS: list[tuple[str, type[Generator]]] = [
    ("wilson's (loop-erased walk)", WilsonsGenerator),
]

# What each key expects, to explain a value the config parser rejected.
_EXPECTED: dict[str, str] = {
    "WIDTH": "a whole number of cells",
    "HEIGHT": "a whole number of cells",
    "ENTRY": "a cell written x,y",
    "EXIT": "a cell written x,y",
    "OUTPUT_FILE": "a file name",
    "PERFECT": "True or False",
}


class ConfigProblem(Exception):
    """Something in the config file stops a maze from being built.

    *key* names the offending setting and *part* which of its comma
    separated values is wrong, when that is known. *line* is a 0-based line
    number, for problems that are not tied to a key.
    """

    def __init__(self, title: str, detail: str, path: str,
                 key: str | None = None, part: int | None = None,
                 line: int | None = None) -> None:
        """Describe the problem; *detail* is shown to the user as is."""
        super().__init__(f"{title}: {detail}")
        self.title = title
        self.detail = detail
        self.path = path
        self.key = key
        self.part = part
        self.line = line

    def source(self) -> list[str]:
        """The config file's lines, or none if it cannot be read."""
        try:
            return Path(self.path).read_text().splitlines()
        except (OSError, ValueError):
            return []

    def locate(self, lines: list[str]) -> tuple[int, int, int] | None:
        """Where the problem sits in *lines*: (line, start, end) of the
        characters to point at, or None when it is not on a single line."""
        index = self.line
        if index is None and self.key is not None:
            # the parser keeps the last occurrence of a key
            for number, text in enumerate(lines):
                # get the last line that defines the key,
                # ignoring comments and blank lines
                if not text.startswith("#") and "=" in text \
                        and text.split("=", 1)[0].strip() == self.key:
                    index = number
        if index is None or not 0 <= index < len(lines):
            return None

        text = lines[index]
        # get the index of the start of the value definition, to show
        # in the UI
        start = text.index("=") + 1 if "=" in text else 0
        start += len(text[start:]) - len(text[start:].lstrip())
        end = len(text.rstrip())
        # shows which part of the value is wrong, useful for
        # entry and exit, which are comma-separated coordinates
        if self.part is not None:
            parts = text[start:end].split(",")
            # if something happened and the value was modified between the
            # error and the error being shown, prevent a crash
            if self.part < len(parts):
                start += sum(len(p) + 1 for p in parts[:self.part])
                end = start + len(parts[self.part])
        return index, start, max(end, start + 1)


def load_config(path: str) -> Config:
    """Read and check the config at *path*.

    Raises ConfigProblem with a readable explanation when the file is
    missing, malformed, or describes a maze that cannot be built.
    """
    try:
        config = Config(path)
    except FileNotFoundError:
        raise ConfigProblem("Config not found",
                            f"There is no file at {path}.", path) from None
    except IndexError as error:
        # in regex, () signal a capturing group, which is the pattern that
        # the matcher will return
        # here, it means we want to capture the name of the missing key,
        # which is in the error message
        # the keys are uppercase, and can have underscores
        # so [A-Z_] matches one character that is inbetween A and Z,
        # or an underscore
        # '[A-Z_]' means we want to match that pattern, inbetween single quotes
        # '[A-Z_]+' means we want to match one or more of those characters,
        # inbetween single quotes
        # finally, ([A-Z_]+) means we want to *capture* that pattern,
        # inbetween single quotes
        missing = re.findall(r"'([A-Z_]+)'", str(error))
        if str(error).startswith("Missing") and missing:
            raise ConfigProblem("Missing keys",
                                # sorted, so the message does not depend on
                                # the order of the set in the error
                                f"Add {', '.join(sorted(missing))} "
                                f"to the config.", path) from None
        raise ConfigProblem("Invalid config", str(error), path) from None
    except UnicodeDecodeError:
        raise ConfigProblem("Unreadable config",
                            "The file is not plain text.", path) from None
    except ValueError as error:
        # a line with no `=`; the parser counts lines from 1, the UI from 0
        syntax = re.match(r"Line (\d+) is not KEY=VALUE", str(error))
        if syntax is not None:
            raise ConfigProblem("Bad syntax", "Every line must be KEY=VALUE.",
                                path, line=int(syntax.group(1)) - 1) from None
        # Config's messages read "Invalid value `V` at key `KEY`: reason"
        # the regex captures the key and the reason, to show in the UI
        # \s matches whitespace; + means 1 or more of the previous pattern,
        # and * means 0 or more. \s+ is needed after "at key" because one of
        # Config's messages has a run of spaces there
        # [^`]+ matches one or more characters that are not a backtick
        # (a ^ at the start of [...] means 'any character except these')
        # (.*) captures the reason: the rest of the string, since . matches
        # any character
        # tldr: we capture the key between the backticks that follow
        # "at key", and everything after "`KEY`:(whitespace)" as the reason
        match = re.search(r"at key\s+`([^`]+)`:\s*(.*)", str(error))
        if match is None:
            raise ConfigProblem("Invalid value", str(error), path) from None
        key, reason = match.groups()
        if reason == "in config file":  # the value did not parse, or was empty
            reason = f"{key} must be {_EXPECTED.get(key, 'valid')}"
        # an out of bounds cell names the coordinate that is wrong
        part = {"x": 0, "y": 1}.get(reason.split(" ", 1)[0])
        title = "Out of bounds" if part is not None else "Invalid value"
        raise ConfigProblem(title, reason, path, key=key,
                            part=part) from None
    except OSError as error:
        raise ConfigProblem("Unreadable config",
                            error.strerror or str(error), path) from None
    return config


class WallChange(NamedTuple):
    """A cell's walls were set: a change to the maze itself."""
    # a namedtuple is like a dataclass, but immutable and with less features

    cell: Cell
    walls: Direction


class CellEvent(NamedTuple):
    """What the generator reported about a cell through its history
    callback."""

    cell: Cell
    kind: MazeHistoryCallbackCell


# One step of a maze's history
Event = WallChange | CellEvent


class _RecordingMaze(Maze):
    """A maze that remembers every wall change, so its building can be
    replayed afterwards."""
    history: list[Event]

    def __init__(self, config: Config) -> None:
        """Start with every wall closed and nothing recorded."""
        self.history = []
        super().__init__(config)

    def __setitem__(self, cell: Cell, directions: Direction) -> None:
        """Set the walls of *cell* and record the change."""
        super().__setitem__(cell, directions)
        self.history.append(WallChange(cell, directions))

    def record(self, cell: Cell, kind: MazeHistoryCallbackCell) -> None:
        """Record what the generator reported about *cell*; registered as
        the generator's history callback."""
        self.history.append(CellEvent(cell, kind))


@dataclass
# dataclasses are classes that create __init__ and __repr__ methods
# automatically, and can be compared for equality
class MazeRun:
    """One maze built from the config, with what it took to build it."""

    maze: Maze
    algorithm: str
    # every wall change and generator event, in order; the first `carved`
    # come from the generator and the rest from braiding the maze when it is
    # not perfect
    history: list[Event]
    carved: int
    path: list[Cell]  # entry to exit, both included
    dead_ends: int
    braided: bool  # False if dead ends were left in an imperfect maze
    elapsed: float  # seconds
    write_error: str | None  # why the output file was not written, or None


@dataclass
class Session:
    """What the UI works on: a config, the last maze built from it, and the
    choices made since (seed, mode, algorithm, colours)."""

    config_path: str
    config: Config = field(init=False)
    seed: str = field(init=False)
    algorithm: int = 0
    wall_colour: int = 0
    logo_colour: int = 0
    expanded: bool = False  # full-size tiles even if the maze then scrolls
    current: MazeRun = field(init=False)

    # called after the dataclass generated __init__ method
    def __post_init__(self) -> None:
        """Load the config and build the first maze from it.

        Raises ConfigProblem if either fails.
        """
        self.config = load_config(self.config_path)
        self.seed = self.config.seed or _new_seed()
        self.current = self._build()

    def regenerate(self) -> MazeRun:
        """Build a new maze from a fresh seed."""
        self.seed = _new_seed()
        self.current = self._build()
        return self.current

    def toggle_perfect(self) -> MazeRun:
        """Switch between a perfect maze and a braided (pac-man) one,
        keeping the seed so the two can be compared."""
        self.config.perfect = not self.config.perfect
        self.current = self._build()
        return self.current

    def next_algorithm(self) -> MazeRun:
        """Rebuild the maze with the next generator, keeping the seed."""
        self.algorithm = (self.algorithm + 1) % len(ALGORITHMS)
        self.current = self._build()
        return self.current

    def _build(self) -> MazeRun:
        """Generate, braid, solve and write out a maze for the config."""
        config = copy.copy(self.config)
        config.seed = self.seed
        # use a recordingmaze so the replay can show how the maze was built
        maze = _RecordingMaze(config)

        name, algorithm = ALGORITHMS[self.algorithm]
        generator = algorithm()
        # register the maze's record() method as the generator's history
        # callback, so the maze can remember what the generator did to it
        generator.register_history_callback(maze.record)
        started = time.perf_counter()
        try:
            generator.generate(maze)
        except GeneratorError as error:
            raise ConfigProblem("Impossible maze", str(error),
                                self.config_path) from None
        carved = len(maze.history)
        braided = True
        if not config.perfect:
            transformer = TaintTransformer()
            transformer.register_history_callback(maze.record)
            braided = transformer.transform(maze)
        try:
            sides = maze.solve()
        except ValueError:
            raise ConfigProblem("No way out",
                                "the exit cannot be reached from the entry",
                                self.config_path, key="EXIT") from None
        elapsed = time.perf_counter() - started

        cell = (config.entry[1], config.entry[0])
        path = [cell]
        for side in sides:
            cell = (cell[0] + side.step[0], cell[1] + side.step[1])
            path.append(cell)

        return MazeRun(maze=maze, algorithm=name, history=maze.history,
                       carved=carved, path=path, dead_ends=dead_ends(maze),
                       braided=braided, elapsed=elapsed,
                       write_error=_write(maze))


def dead_ends(maze: Maze) -> int:
    """How many playable cells have a single way in or out."""
    return sum(1 for row, col, _ in maze
               if not maze.in_logo((row, col))
               and len(list(maze.open_sides((row, col)))) == 1)


def _write(maze: Maze) -> str | None:
    """Write the maze to its output file; returns why that failed, if it
    did."""
    try:
        with open(maze.config.output_file, "w") as file:
            file.write(maze.get_output())
    except (OSError, ValueError) as error:
        return getattr(error, "strerror", None) or str(error)
    return None


def _new_seed() -> str:
    """A short random seed, readable enough to show and type back in."""
    return secrets.token_hex(3)


class Replay:
    """Steps through a MazeRun's history, from a maze with every wall
    closed to the finished one."""
    run: MazeRun
    maze: Maze
    position: int
    touched: int
    playable: int
    walk: list[Cell]

    def __init__(self, run: MazeRun) -> None:
        """Start from the beginning of *run*."""
        self.run = run
        # a copy to replay into; its grid is written directly so the replay
        # is not recorded on top of the history it reads
        self.maze = copy.copy(run.maze)
        self.maze.grid = [[CLOSED] * run.maze.cols
                          for _ in range(run.maze.rows)]
        self.position = 0
        self.touched = 0
        self.playable = sum(1 for row, col, _ in run.maze
                            if not run.maze.in_logo((row, col)))
        self.walk = []  # the generator's walk, oldest cell first

    @property
    def done(self) -> bool:
        """Whether every event has been replayed."""
        return self.position >= len(self.run.history)

    @property
    def phase(self) -> str:
        """What the replayed changes are doing at this point.
        "carving" means the replay is still in the generator's events,
        "braiding" means it is in the transformer's, removing dead ends,
        "done" means every event has been replayed."""
        if self.done:
            return "done"
        return "carving" if self.position < self.run.carved else "braiding"

    def advance(self, events: int) -> None:
        """Replay the next *events* events.

        Wall changes rebuild the maze. The generator's events follow its
        walk: a cell joins the walk (MAYBE), and leaves it either when a
        loop is erased (RESET) or when it joins the maze (OPEN). When the
        generator starts over (MAZE_RESET), the walk is dropped.
        """
        history = self.run.history
        for _ in range(events):
            if self.done:
                break
            event = history[self.position]
            self.position += 1
            # the maze's grid is written directly,
            # so the replay is not recorded on top of the history it reads
            if isinstance(event, WallChange):
                row, col = event.cell
                before = self.maze.grid[row][col]
                # keep counts up to date
                self.touched += int(event.walls != CLOSED) \
                    - int(before != CLOSED)
                self.maze.grid[row][col] = event.walls
            elif event.kind is MazeHistoryCallbackCell.MAYBE:
                self.walk.append(event.cell)
            elif event.kind is MazeHistoryCallbackCell.MAZE_RESET:
                # the walls going back up were recorded as wall changes
                self.walk = []
            elif event.cell in self.walk:
                self.walk.remove(event.cell)
        if self.done:
            self.walk = []

    def finish(self) -> None:
        """Replay everything that is left."""
        self.advance(len(self.run.history) - self.position)
