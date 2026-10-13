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

USAGE = "usage: python3 a_maze_ing.py <config file>"


def error(message: str) -> int:
    """Print *message* as an error and return the exit status for it."""
    print(f"Error: {message}", file=sys.stderr)
    return 1


def interactive() -> bool:
    """Whether a person is at the terminal, so the interface can run."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def build(config_path: str) -> int:
    """Build the maze and write its output file, without the interface,
    printing what went wrong if anything did. Returns the exit status."""
    from ui import ConfigProblem, Session

    try:
        session = Session(config_path)
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
