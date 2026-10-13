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

"""Keeping a big maze from using up the computer's memory.

Linux almost never says no when a program asks for more memory. When it
runs short, it moves other programs' memory to the disk (swap), and the
whole computer slows to a crawl long before anything stops. Python only
raises a MemoryError when a request is refused, so without a limit the
program never finds out it is in trouble.

limit_memory() sets that limit, so a maze too big for the computer stops
with a MemoryError, which is shown as an error, instead of freezing it.
memory_needed() estimates what a maze takes, to warn before building it.
"""
import resource

MB = 1024 ** 2
GB = 1024 ** 3

# Where Linux tells how much memory is available
MEMINFO = "/proc/meminfo"

# The share of the available memory this program may use: the rest is
# left to the system and the other programs
SHARE = 0.8

# What one cell of one maze takes while it is built and kept for its
# replay. Measured with CPython at about 2.1 KB on mazes up to 400 x 400,
# rounded up: better to warn too early than too late.
BYTES_PER_CELL = 2500

# What the program takes before any maze is built: about 50 MB with
# CPython and 125 MB with PyPy
BASE_BYTES = 150 * MB


def available_memory(path: str = MEMINFO) -> int | None:
    """How much memory, in bytes, the system can give without swapping,
    read from *path*; None if it cannot be read (e.g. not on Linux)."""
    try:
        with open(path) as file:
            for line in file:
                # e.g. "MemAvailable:   19876543 kB"
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def limit_memory() -> None:
    """Cap the memory this program may reserve at SHARE of the memory
    available now. Past the cap, Python raises a MemoryError instead of
    the computer swapping. Keeps a lower cap set before, e.g. with
    `ulimit -v`, and does nothing if the available memory is unknown."""
    available = available_memory()
    if available is None:
        return
    cap = int(available * SHARE)
    # RLIMIT_AS caps the address space: all the memory the program
    # reserves. "soft" is the cap in force, "hard" the highest it may be
    # raised to.
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    if soft != resource.RLIM_INFINITY and soft <= cap:
        return
    if hard != resource.RLIM_INFINITY:
        cap = min(cap, hard)
    resource.setrlimit(resource.RLIMIT_AS, (cap, hard))


def memory_limit() -> int | None:
    """The cap on this program's memory, in bytes, or None if there is
    none."""
    soft, _ = resource.getrlimit(resource.RLIMIT_AS)
    if soft == resource.RLIM_INFINITY:
        return None
    return soft


def memory_needed(width: int, height: int, mazes: int = 1) -> int:
    """Roughly how much memory, in bytes, building a *width* x *height*
    maze takes, with *mazes* of them kept at once: 2 in the interface,
    which keeps the old maze on screen while it builds the new one."""
    return BASE_BYTES + width * height * BYTES_PER_CELL * mazes


def too_big(width: int, height: int, mazes: int = 1) -> bool:
    """Whether building the maze may run out of memory: it needs more
    than the cap on this program's memory."""
    limit = memory_limit()
    return limit is not None and memory_needed(width, height, mazes) > limit


# Shown when a build ran out of memory
OUT_OF_MEMORY = ("The maze needed more memory than this program may use. "
                 "Make WIDTH or HEIGHT smaller.")


def warning(width: int, height: int, mazes: int = 1) -> str:
    """Why building the maze may run out of memory, for the user."""
    needed = memory_needed(width, height, mazes) / GB
    limit = (memory_limit() or 0) / GB
    return (f"A {width}×{height} maze needs about {needed:.1f} GB of "
            f"memory, but this program may only use {limit:.1f} GB. "
            f"Building it may run out of memory: it would then stop with "
            f"an error, without slowing down the rest of the computer.")
