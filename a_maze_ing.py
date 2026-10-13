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

"""Build the maze described by a config file, write it to its output file,
and show it in the interface.

Usage: python3 a_maze_ing.py <config file>
"""
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # only for the type checker: importing ui needs Textual, which main()
    # checks for first
    from ui import Session

USAGE = "usage: python3 a_maze_ing.py <config file>"


def error(message: str) -> int:
    """Print *message* as an error and return the exit status for it."""
    print(f"Error: {message}", file=sys.stderr)
    return 1


def interactive() -> bool:
    """Whether a person is at the terminal, so the interface can run."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def show_progress(step: str, done: int, total: int) -> None:
    """Rewrite the progress line on stderr: back to the start of the line
    (\\r), clear it (ESC [K), then print where the build is."""
    from ui import describe

    # \r (carriage return) moves the cursor back to the start of the line,
    # without going to a new one, so the next text is written over the old.
    # \033[K is a terminal code that erases the rest of the line: a shorter
    # text would leave the end of the longer one behind.
    # end="": no newline, so the next report overwrites this one.
    # flush=True: print it now. Python holds text back until a whole line
    # is complete, and this line never is.
    print(f"\r\033[K{describe(step, done, total)}", end="", file=sys.stderr,
          flush=True)


def load(config_path: str) -> "Session":
    """Read the config and build its maze, showing how far the build has
    got on stderr if it is a terminal: a big maze takes minutes. Warns
    first if the maze may not fit in memory, but builds it anyway.

    Raises ConfigProblem if the config stops the maze from being built.
    """
    from ui import Session, load_config
    from ui.memory import too_big, warning

    config = load_config(config_path)
    if too_big(config.width, config.height):
        print(f"Warning: {warning(config.width, config.height)}",
              file=sys.stderr)
    if not sys.stderr.isatty():
        return Session(config_path)
    try:
        return Session(config_path, progress=show_progress)
    finally:
        # clear the progress line, for whatever is printed next
        print("\r\033[K", end="", file=sys.stderr, flush=True)


def build(config_path: str) -> int:
    """Build the maze and write its output file, without the interface,
    printing what went wrong if anything did. Returns the exit status."""
    from ui import ConfigProblem
    from ui.memory import OUT_OF_MEMORY

    try:
        session = load(config_path)
    except MemoryError:
        # past the cap set by limit_memory(): the build stops here instead
        # of freezing the computer
        return error(OUT_OF_MEMORY)
    except ConfigProblem as problem:
        # where the problem is, if it is tied to a key or a line
        where = f"{config_path}"
        if problem.key is not None:
            where += f", {problem.key}"
        elif problem.line is not None:
            where += f", line {problem.line + 1}"
        return error(f"{where}: {problem.title}: {problem.detail}")
    run = session.current
    if run.write_error is not None:
        return error(f"could not write {session.config.output_file}: "
                     f"{run.write_error}")
    if not run.braided:
        print("Warning: could not remove all dead ends from the maze",
              file=sys.stderr)
    return 0


def main(args: list[str]) -> int:
    """Run the program on the command line arguments *args*, not counting
    the program name. Returns the exit status."""
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        return 1
    config_path = args[0]
    try:
        # the interface needs Textual, which `make install` sets up
        from ui import AMazeIngApp
    except ImportError as missing:
        return error(f"{missing}. Run `make install`, then `make run`.")
    from ui.memory import limit_memory

    # before any maze is built: past this cap, a build stops with a
    # MemoryError instead of freezing the computer
    limit_memory()
    try:
        if not interactive():
            return build(config_path)
        # the app builds the maze and writes the output file itself, and
        # shows what is wrong with the config, if anything is
        AMazeIngApp(config_path).run()
    except KeyboardInterrupt:
        return 130
    except Exception as unexpected:
        return error(f"unexpected {type(unexpected).__name__}: {unexpected}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
