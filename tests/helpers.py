"""Data shared by the tests, and types for the fixtures in conftest.py."""
from typing import Protocol

from lib import Config, Maze

VALID_CONFIG = """\
# a valid config
WIDTH=10
HEIGHT=8
ENTRY=0,0
EXIT=9,7
OUTPUT_FILE=maze.txt
PERFECT=True
SEED=42
"""


class MakeConfig(Protocol):
    """The type of the make_config fixture."""

    def __call__(self, width: int = ..., height: int = ...,
                 entry: tuple[int, int] = ...,
                 exit: tuple[int, int] | None = ...,
                 output_file: str = ..., perfect: bool = ...,
                 seed: str | None = ...) -> Config:
        """Build a Config from keyword values, without checking them."""
        ...  # stub: signature only, so VS Code doesn't expect a return


class MakeMaze(Protocol):
    """The type of the make_maze fixture."""

    def __call__(self, width: int = ..., height: int = ...,
                 entry: tuple[int, int] = ...,
                 exit: tuple[int, int] | None = ...,
                 output_file: str = ..., perfect: bool = ...,
                 seed: str | None = ...) -> Maze:
        """Build a Maze with every wall closed."""
        ...


class WriteConfig(Protocol):
    """The type of the write_config fixture."""

    def __call__(self, text: str, name: str = ...) -> str:
        """Write *text* to a config file and return its path."""
        ...
