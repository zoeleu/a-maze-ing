*This project has been created as part of the 42 curriculum by zleullie, fpinheir.*

# A-Maze-ing

## Description

A-Maze-ing is a maze generator written in Python. It reads a configuration
file, generates a random but reproducible maze, writes it to a file using a
hexadecimal wall encoding, and shows it in an interactive terminal interface.

Every maze has a "42" drawn in its centre with fully closed cells, and comes
in one of two modes:

- **Perfect** (`PERFECT=True`): exactly one path between any two cells, so a
  single path from the entry to the exit.
- **Pac-Man board** (`PERFECT=False`, the default): a fully connected board
  with many loops and no dead ends, with the four corners and the centre open,
  usable as a Pac-Man-like level.

The generation logic lives in its own package, `mazegen`, so it can be
reused in later projects without the interface.

## Instructions

### Requirements

- Python 3.10 or later
- `make`

### Installation

```bash
make install
```

This creates a virtual environment in `.venv` and installs the dependencies
listed in `requirements.txt` (Textual and Rich for the interface,
`typing_extensions` for the library; flake8, mypy and build for development)
and MiniLibX, unpacked from `mlx-2.2.tar.gz` at the root of the repository.
`run`, `test`, `lint` and the other rules do this first if it has not been
done yet.

To use another Python, give its command as `PY`, on any rule:

```bash
make PY=python3.13 test
make PY=pypy3 run
```

Each Python gets its own virtual environment (`.venv` for `python3`,
`.venv-<name>` for the others, e.g. `.venv-pypy3`), so switching back and
forth never mixes them; `make PY=pypy3 python` shows which interpreter a
rule would use. On Debian and Ubuntu, PyPy needs the `pypy3-venv` package
to create a virtual environment.

### Running

```bash
make run
```

which is the same as:

```bash
.venv/bin/python a_maze_ing.py config.txt
```

`config.txt` is the only argument and can be any file following the format
below. The program writes the maze to `OUTPUT_FILE`, then opens the
interface. If the config is invalid, the interface shows what is wrong
instead (see [The interface](#the-interface)).

When it is not run from a terminal, for example with its output redirected
or from a script, the program only writes the maze to `OUTPUT_FILE`,
without the interface. Problems are then printed, naming the key or line at
fault, and the program exits with status 1:

```
$ python3 a_maze_ing.py config.txt > /dev/null
Error: config.txt, EXIT: Out of bounds: x must be between 0 and 31 (WIDTH=32)
```

Running it without exactly one argument prints its usage. It never stops
with a traceback: a missing Textual install, Ctrl+C or an unexpected error
are reported as a message too.

### Makefile rules

| Rule          | What it does                                                   |
|---------------|----------------------------------------------------------------|
| `install`     | Create the virtual environment and install the dependencies    |
| `python`      | Show the Python and virtual environment the rules use          |
| `run`         | Run `a_maze_ing.py` with `config.txt`                          |
| `debug`       | Run it under Python's debugger, `pdb`                          |
| `test`        | Run the `pytest` suite in `tests/`                             |
| `clean`       | Remove `__pycache__`, `.mypy_cache`, build leftovers           |
| `fclean`      | `clean`, plus the built package and the unpacked MiniLibX      |
| `lint`        | `flake8` and `mypy` with the flags required by the subject     |
| `lint-strict` | `flake8` and `mypy --strict`                                   |
| `build`       | Build the `mazegen` wheel at the root of the repository        |

## Configuration file

One `KEY=VALUE` pair per line. Lines starting with `#` and blank lines are
ignored, and spaces around keys and values are stripped. If a key appears
twice, the last one wins.

| Key           | Required | Format         | Example                | Meaning                          |
|---------------|----------|----------------|------------------------|----------------------------------|
| `WIDTH`       | yes      | 1 to 1500      | `WIDTH=20`             | Number of columns                |
| `HEIGHT`      | yes      | 1 to 1500      | `HEIGHT=15`            | Number of rows                   |
| `ENTRY`       | yes      | `x,y`          | `ENTRY=0,0`            | Entry cell (x = column, y = row) |
| `EXIT`        | yes      | `x,y`          | `EXIT=19,14`           | Exit cell                        |
| `OUTPUT_FILE` | yes      | file name      | `OUTPUT_FILE=maze.txt` | Where the maze is written        |
| `PERFECT`     | yes      | `True`/`False` | `PERFECT=False`        | Perfect maze or Pac-Man board    |
| `SEED`        | no       | any text       | `SEED=hello`           | Seed for reproducible mazes      |
| `ALGORITHM`   | no       | `wilson`/`backtracker` | `ALGORITHM=backtracker` | Generation algorithm (default `wilson`) |

The configuration is rejected, with a message pointing at the faulty line,
when:

- a mandatory key is missing, or a line has no `=`;
- a value has the wrong format (e.g. `WIDTH=abc`, `PERFECT=yes`);
- `WIDTH` or `HEIGHT` is above 1500 (see below);
- `ALGORITHM` is not `wilson` or `backtracker`;
- `ENTRY` or `EXIT` is outside the maze, they are the same cell, or one of
  them falls on the "42" pattern.

Unknown keys are reported and ignored. With `SEED` missing or empty, a random
seed is picked; the same seed and config always produce the same maze.

A maze is at most 1500 × 1500 cells. This is a sensible default, to keep
mazes to a size a computer can build. Measured on the interface's build, a
cell takes about 2.1 KB: the grid, the lists the algorithms work on, and
the history kept for the replay. The interface keeps the old maze on screen
while it builds the new one, so two mazes are in memory at once:
1500 × 1500 × 2 × 2.1 KB ≈ 9.5 GB. Building the largest maze takes several
minutes, with its progress shown as it goes (see [Progress](#progress)).

The "42" needs a maze at least 8 cells wide and 6 cells high. A smaller maze
is still generated, without the pattern, and an error message is printed.

Default `config.txt`:

```
# This is a comment!
WIDTH=32
HEIGHT=32
ENTRY=0,0
EXIT=31,31
OUTPUT_FILE=maze.txt
PERFECT=False
SEED=
```

### Memory

A computer may have less memory than a maze needs. Linux almost never
refuses a program more memory: it moves other programs' memory to the disk
instead, and the whole computer slows to a crawl long before anything
stops. So the program protects the computer in two ways:

- **A cap.** At start, the program caps the memory it may use at 80% of
  the memory free at that moment (`resource.setrlimit()`, the same limit as
  the shell's `ulimit -v`; a lower one set before is kept). A build that
  goes past it stops with a `MemoryError`, which is shown as an error
  ("Out of memory"), and the rest of the computer is not slowed down. This
  works on Linux, which says how much memory is free in `/proc/meminfo`.
- **A warning.** Before building, the program estimates what the maze
  needs: 2.5 KB per cell (the 2.1 KB measured, rounded up), twice in the
  interface, plus 150 MB for the program itself. If that is more than the
  cap, the interface asks whether to *accept the risk and build* anyway,
  or quit; without the interface, a warning is printed and the maze is
  built. It is only a warning: the estimate is rough, and the cap keeps the
  computer safe either way.

See `ui/memory.py`.

## Output file

One hexadecimal digit per cell, one row per line. Each bit of the digit is a
closed wall:

| Bit     | Value | Wall  |
|---------|-------|-------|
| 0 (LSB) | 1     | North |
| 1       | 2     | East  |
| 2       | 4     | South |
| 3       | 8     | West  |

So `9` (`1001`) is a cell closed to the north and west, and `F` a fully
closed cell. After an empty line come the entry, the exit, and the shortest
path from one to the other as a string of `N`, `E`, `S`, `W`:

```
95393939151555391153
...

0,0
19,14
EESSSENEESESEEEEEENEESEESSSESS...
```

`maze_analyzer.py`, provided with the subject, checks that a file is coherent
and that it matches the requested mode:

```bash
python3 maze_analyzer.py maze.txt
```

## The interface

The maze is shown in the terminal with [Textual](https://textual.textualize.io/),
next to panels with the generation algorithms, the config (including the
seed in use) and statistics (mode, shortest path length, dead ends, build
time). Keys:

| Key | Action                                                           |
|-----|------------------------------------------------------------------|
| `R` | Generate a new maze from a fresh seed                            |
| `P` | Show / hide the shortest path from entry to exit                 |
| `C` | Cycle the wall colour (chalk, amber, moss, cyan, rose, steel)    |
| `F` | Cycle the colour of the "42" pattern                             |
| `M` | Switch between perfect and Pac-Man mode, keeping the seed        |
| `A` | Cycle the generation algorithm, keeping the seed                 |
| `G` | Watch an animated replay of how the maze was built               |
| `Z` | Expand / shrink the maze when it does not fit the terminal       |
| `W` | Open the maze in an MLX window, when the terminal is too narrow  |
| `Q` | Quit                                                             |

In the replay screen: `Space` pauses or resumes, `+`/`-` change the speed,
`S` skips to the end, `R` restarts, `A` switches algorithm, `Esc` goes back.

Both screens list the algorithms, the one in use marked with `▸`: clicking
another rebuilds the maze with it, from the same seed, like `A`. The choice
is shared, so the replay screen replays the algorithm picked on the main
screen, and the other way round. The interface starts with the algorithm
the config's `ALGORITHM` names, Wilson's by default; without the interface,
that is the one used.

When the config is invalid, an error screen shows the file with the faulty
line highlighted; fix the file and press `R` to reload it.

### Progress

A big maze takes minutes to build, so every build shows how far it has
got: which step it is on (mapping the cells, carving, checking the exit,
braiding, solving, writing) and, when the step can tell, how much of it is
done.

- **Without the interface** (when the output is not a terminal), the
  progress is one line on stderr, rewritten in place with `\r`, and cleared
  once the maze is built. It is only shown when stderr is a terminal, so
  logs and pipes stay clean.
- **In the interface**, the maze is built on a thread of its own, behind a
  screen with a progress bar. Built on the interface's thread, it would
  freeze the interface until done. Python's GIL lets only one thread run
  Python code at a time, so this does not make the build faster, but
  Python switches threads every few milliseconds, which keeps the
  interface drawing. The build thread only talks to the interface through
  Textual's `app.call_from_thread()`, which runs a function on the
  interface's thread: Textual widgets must not be touched from any other.
  The thread is a *daemon*, so `Q` quits at once, without waiting for the
  build (see `AMazeIngApp.build()` in `ui/app.py`, and
  `ui/screens/building.py` for the screen).

The library reports progress for every cell, far more often than it can be
shown, so the session passes it on at most 10 times a second.

When the terminal is too narrow to draw the maze at all, a notice replaces
it with an **Open in a window** button (or press `W`) that shows the maze in
a separate MiniLibX (MLX) window, kept in sync with the interface: colours,
the path, and the replay all show there as they change. Nothing opens until
you ask. Close it with its close button or `Esc`; it also closes once the
terminal is wide enough again. The window runs in the interface's thread:
`mlx_loop()` never returns on its own, so it is run one pass at a time from
a timer (see `ui/mlx_window.py`).

## How the maze is generated

Generation happens in two steps: a **generator** builds a perfect maze, then,
in Pac-Man mode, a **transformer** reworks it into a board with loops. There
are two generators: Wilson's algorithm, the default, and the recursive
backtracker.

### Wilson's algorithm (`mazegen/algorithms/wilsons.py`)

The maze starts with every wall closed. The cells of the "42" pattern are
removed from the grid before generation starts, so they stay fully closed.

1. A random cell is added to the maze.
2. From a cell not yet in the maze, a random walk wanders until it hits a
   cell that is.
3. Whenever the walk crosses its own path, the loop it made is erased.
4. The remaining, loop-free walk is carved into the maze.
5. Steps 2 to 4 repeat until every cell is in the maze.

The result is a spanning tree of the grid: every cell is reachable and there
is exactly one path between any two cells, which is a perfect maze. As a
safety net, if the exit cannot be reached, the maze is regenerated from a
seed derived from the previous one, so the result stays reproducible.

### Why Wilson's algorithm

- **Unbiased mazes.** Wilson's algorithm picks uniformly among all possible
  perfect mazes of the grid. Other algorithms leave a visible signature:
  the recursive backtracker makes long winding corridors with few branches,
  and Prim's makes many short dead ends. Uniform mazes are a fair starting
  point for both modes.
- **Holes are not a problem.** It works on any connected set of cells, so
  leaving the "42" cells out of the grid is enough; no special case is needed.
- **It is easy to show.** The walk, its erased loops and the carving are
  clear steps, which the replay screen animates.

Its drawback is speed: the first walks are long, since they wander until they
find the few cells already in the maze. In practice a 32×32 maze, braiding
included, is built in under a tenth of a second.

### Recursive backtracker (`mazegen/algorithms/backtracker.py`)

A randomised depth-first search, the second algorithm to choose from:

1. A random cell starts the path.
2. From the cell at the end of the path, a random neighbour that has not
   been visited yet is carved into and added to the path.
3. When the end of the path has no unvisited neighbour left, the search
   backs up one cell.
4. Steps 2 and 3 repeat until the search has backed up past its first cell.

Like Wilson's, it leaves out the "42" cells and builds a spanning tree, so a
perfect maze. The path is kept in a list rather than in recursive calls, so
large mazes do not hit Python's recursion limit.

Its mazes look very different: the search goes as deep as it can before
turning back, which gives long winding corridors with few branches. A 30×20
maze has about 55 to 75 dead ends, against 150 to 185 with Wilson's, and the
path from entry to exit is longer. It is also much faster, since every cell
is visited exactly once.

To use it, click it in the algorithm list, or press `A`, on the main or the
replay screen: the maze is rebuilt from the same seed. In code, pass it to
`MazeGen` (see [Reusable code](#reusable-code)).

### Braiding into a Pac-Man board (`mazegen/transformers/taint.py`)

`TaintTransformer` turns the perfect maze into a board:

1. It opens the corridor in the middle of the "42", between the 4 and the 2,
   and the inner walls of the four corners, where ghosts and the player start.
2. It visits every dead end in random order and knocks down one of its
   walls, preferring a wall shared with another dead end, which fixes both at
   once. Each opening adds a loop.
3. An opening is undone if it creates a 3×3 open area, since corridors may
   not be wider than 2 cells.

The result usually has no dead ends at all. If some cannot be removed without
breaking the 3×3 rule, a warning is shown.

### Shortest path

`Maze.solve()` uses a breadth-first search from the entry. It explores the
maze in rings of increasing distance, so the first time it reaches the exit
is along a shortest path, which it then walks back.

## Reusable code

The maze generator is a standalone package, `mazegen`, with no dependency on
the interface, which lives in its own folder, `ui`. Build it with:

```bash
make build
```

which produces `mazegen-1.0.0-py3-none-any.whl` at the root of the
repository. Install it in another project with:

```bash
pip install mazegen-1.0.0-py3-none-any.whl
```

### Usage

`MazeGen` is the whole generator in one class:

```python
from mazegen import Direction, MazeGen

# Size, entry and exit as (x, y), mode, and seed for reproducibility
generator = MazeGen(width=20, height=15, entry=(0, 0), exit=(19, 14),
                    perfect=False, seed="42")
result = generator.generate()

# The structure: the closed walls of every cell, as Direction flags,
# indexed grid[y][x]
grid = result["grid"]
grid[0][0]                                 # Direction.NORTH|WEST
grid[0][0].has(Direction.NORTH)            # True: the wall is closed

# A solution: the shortest path from entry to exit
path = result["solution"]                  # [Direction.EAST, ...]
"".join(str(step) for step in path)        # "EESSSENEESES..."

# Pac-Man mode only: whether every dead end could be removed
result["fully_braided"]                    # True (None for a perfect maze)
```

| Parameter   | Default            | Meaning                                            |
|-------------|--------------------|----------------------------------------------------|
| `width`     |                    | Number of columns, from 1 to 1500                  |
| `height`    |                    | Number of rows, from 1 to 1500                     |
| `entry`     |                    | Entry cell, `(x, y)`                               |
| `exit`      |                    | Exit cell, `(x, y)`, a different cell from `entry` |
| `perfect`   | `True`             | Perfect maze, or Pac-Man board when `False`        |
| `seed`      | `None`             | Same seed, same maze; `None` picks a random one    |
| `algorithm` | `WilsonsGenerator` | The generator class, e.g. `BacktrackerGenerator`   |

`MazeGen` raises a `ValueError` when the size is below 1 or above 1500, or
when the entry or exit is outside the maze, on the "42" pattern, or the same
cell. The returned grid is a copy: changing it does not change the
generator's maze, which stays available as `generator.maze`.

### Lower-level pieces

`MazeGen` is built from smaller pieces, which can also be used directly, for
example to read a config file or to get the output file format:

```python
from mazegen import Config, Direction, Maze, TaintTransformer, WilsonsGenerator

# Parameters: size, entry/exit as (x, y), mode, and seed for reproducibility.
# Config("config.txt") reads them from a file instead.
config = Config.from_dict({
    "WIDTH": 20, "HEIGHT": 15,
    "ENTRY": (0, 0), "EXIT": (19, 14),
    "OUTPUT_FILE": "maze.txt", "PERFECT": False, "SEED": "42",
})
config.validate()                          # from_dict() does not check

maze = Maze(config)
WilsonsGenerator().generate(maze)          # a perfect maze
if not config.perfect:
    TaintTransformer().transform(maze)     # loops, no dead ends

# The structure: cells are (row, col), walls are Direction flags
walls = maze[(0, 0)]
walls.has(Direction.NORTH)                 # True: the wall is closed
list(maze.open_sides((0, 0)))              # [Direction.EAST, Direction.SOUTH]
for row, col, walls in maze:               # every cell
    ...

# A solution: the shortest path from entry to exit
path = maze.solve()                        # [Direction.EAST, ...]
"".join(str(step) for step in path)        # "EESSSENEE..."

# The output file format, as a string
text = maze.get_output()
```

Note that `Config` uses `(x, y)` coordinates, like the config file, while
`Maze` cells are `(row, col)`.

Main pieces:

| Name                                  | Role                                            |
|---------------------------------------|-------------------------------------------------|
| `MazeGen`, `MazeGenResult`            | The whole generator, and what it returns        |
| `Config`                              | Reads and checks a config file, or wraps a dict |
| `Maze`                                | The grid of walls, solving and output           |
| `Direction`                           | Wall flags (`NORTH`, `EAST`, `SOUTH`, `WEST`)   |
| `Generator`                           | Generator base class                            |
| `WilsonsGenerator`                    | Wilson's algorithm                              |
| `BacktrackerGenerator`                | The recursive backtracker                       |
| `MazeTransformer`, `TaintTransformer` | Transformer base class and braiding             |

New algorithms subclass `Generator` and implement `_generate(maze, seed)`;
new post-processing steps subclass `MazeTransformer`.

Generators and transformers can also report every step they take, which is
how the interface animates them:

```python
def on_step(cell, kind):          # kind: MAYBE, OPEN, RESET or MAZE_RESET
    print(cell, kind)

generator = WilsonsGenerator()
generator.register_history_callback(on_step)
generator.generate(maze)
```

They can also report how far they have got, for a progress bar:

```python
def on_progress(step, done, total):   # total is 0 when it cannot tell
    print(f"{step}: {done} / {total}")

generator = WilsonsGenerator()
generator.register_progress_callback(on_progress)
generator.generate(maze)              # "mapping the cells", "carving", ...
```

`MazeGen` keeps its generator and transformer as `generator.generator` and
`generator.transformer`, to register callbacks on them before calling
`generate()`.

## Team and project management

### Roles

- **fpinheir** (Flora): project structure, the config parser and the first
  version of the `Maze` class (cell access, iteration, the "42" pattern).
- **zleullie** (Zoe): the generation framework and Wilson's algorithm, the
  braiding transformer, the Textual interface, the Makefile and packaging.

### Planning and how it evolved

- **Late September:** project structure, config parsing and the first
  `Maze` methods.
- **Early October:** the `Maze` class up and running.
- **October 9 onwards:** generation with Wilson's algorithm, the output file
  and shortest path, then braiding for the Pac-Man mode.
- **Then:** the interactive interface with the replay animation, packaging,
  licensing and documentation.

Building a perfect maze and braiding it ended up as two separate steps,
generators and transformers, sharing the same history callbacks; that is
also what made the replay animation possible.

### What worked well

- Storing walls as `Direction` bit flags: the output file is a direct dump,
  and wall checks are bitwise operations.
- The history callbacks: the interface replays generation without the
  algorithms knowing anything about it.
- `maze_analyzer.py` to check that both modes produce what they should.
- Small HTML step-by-step visualizers (`visualizers/`) of Wilson's algorithm,
  the BFS and the 3×3 check, to understand and explain them.

### What could be improved

- Automated tests should have been written earlier, alongside the code.

### Tools

- git, Python virtual environments, `make`
- flake8 and mypy for linting and type checking, `pdb` for debugging
- [Textual](https://textual.textualize.io/) and Rich for the interface
- `build` and setuptools for packaging
- `maze_analyzer.py` to check the output
- Agentic AI, see below

## Resources

- Jamis Buck's blog: his
  [series of articles on maze algorithms](https://weblog.jamisbuck.org/2011/2/7/maze-generation-algorithm-recap),
  and in particular [Wilson's algorithm](https://weblog.jamisbuck.org/2011/1/20/maze-generation-wilson-s-algorithm)
- [Mazes](https://professor-l.github.io/mazes/), maze generation
  algorithms with interactive visualizations
- [Textual documentation](https://textual.textualize.io/)
- Python documentation: [`enum.IntFlag`](https://docs.python.org/3/library/enum.html#enum.IntFlag),
  [`typing`](https://docs.python.org/3/library/typing.html)
- [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.html)

### How AI was used

Agentic AI was used to reduce repetitive work and to speed up
the project:

- **Explaining concepts:** maze algorithms (Wilson's, BFS), Makefile syntax,
  packaging and software licences.
- **Writing code:** parts of the code were AI-generated, mostly in the
  interface (`ui`). All of it was discussed, read, modified and
  commented by us; no code was submitted without review.
- **Review and debugging:** troubleshooting errors, fixing flake8 and mypy
  issues, and checking the project against the subject.
- **Tests:** writing the test programs used to check the project.
- **Documentation:** drafting docstrings, the licence headers and this
  README.

## License

A-Maze-ing is free software, released under the GNU General Public License
version 3 or later. See [LICENSE.md](LICENSE.md).
