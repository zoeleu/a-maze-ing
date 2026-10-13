"""Fixtures shared by every test module."""
from pathlib import Path

import pytest

from mazegen import Config, Maze
from tests.helpers import (VALID_CONFIG, MakeConfig, MakeMaze,
                           WriteConfig)


@pytest.fixture
def make_config() -> MakeConfig:
    """Build a Config without a file. Like Config.from_dict, it skips the
    checks, so the entry and exit must be valid cells for the size."""
    def factory(width: int = 10, height: int = 8,
                entry: tuple[int, int] = (0, 0),
                exit: tuple[int, int] | None = None,
                output_file: str = "maze.txt", perfect: bool = True,
                seed: str | None = "42") -> Config:
        """A Config of these values; the exit defaults to the far corner."""
        return Config.from_dict({
            "WIDTH": width,
            "HEIGHT": height,
            "ENTRY": entry,
            "EXIT": exit if exit is not None else (width - 1, height - 1),
            "OUTPUT_FILE": output_file,
            "PERFECT": perfect,
            "SEED": seed,
        })
    return factory


@pytest.fixture
def make_maze(make_config: MakeConfig) -> MakeMaze:
    """Build a Maze with every wall closed."""
    def factory(width: int = 10, height: int = 8,
                entry: tuple[int, int] = (0, 0),
                exit: tuple[int, int] | None = None,
                output_file: str = "maze.txt", perfect: bool = True,
                seed: str | None = "42") -> Maze:
        """A Maze, every wall closed, for a Config with the given values."""
        return Maze(make_config(width, height, entry, exit, output_file,
                                perfect, seed))
    return factory


@pytest.fixture
def write_config(tmp_path: Path) -> WriteConfig:
    """Write *text* to a config file in the test's temporary directory and
    return its path."""
    def factory(text: str, name: str = "config.txt") -> str:
        """Write *text* to *name* and return the file's path."""
        path = tmp_path / name
        path.write_text(text)
        return str(path)
    return factory


@pytest.fixture
def valid_config(write_config: WriteConfig) -> str:
    """The path to a valid 10x8 config."""
    return write_config(VALID_CONFIG)


@pytest.fixture
def in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the test from its temporary directory, so output files written
    to a relative path land there."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
