"""Generator, the base class, and Wilson's algorithm."""
import random
from collections import Counter

import pytest

from mazegen import (Cell, Direction, Generator, GeneratorError, Maze,
                     MazeHistoryCallbackCell, WilsonsGenerator)
from tests.helpers import MakeMaze

CLOSED = Direction(sum(Direction))
Kind = MazeHistoryCallbackCell
Events = list[tuple[Cell, MazeHistoryCallbackCell]]

# (width, height, entry, exit): small, odd, just big enough for the logo,
# and bigger
SIZES = [
    (2, 1, (0, 0), (1, 0)),
    (1, 2, (0, 0), (0, 1)),
    (3, 3, (0, 0), (2, 2)),
    (8, 6, (7, 0), (7, 5)),
    (10, 8, (0, 0), (9, 7)),
    (21, 13, (20, 0), (0, 12)),
]
SEEDS = ["0", "42", "seed", "a-maze-ing"]


def playable(maze: Maze) -> list[Cell]:
    """The cells of *maze* that are not part of the logo."""
    return [(r, c) for r, c, _ in maze if not maze.in_logo((r, c))]


def passages(maze: Maze) -> int:
    """How many open passages the maze has, each counted once."""
    return sum(maze.is_open((r, c), side) for r, c, _ in maze
               for side in (Direction.EAST, Direction.SOUTH))


def reachable(maze: Maze, start: Cell) -> set[Cell]:
    """The cells that can be reached from *start* through open passages."""
    seen = {start}
    stack = [start]
    while stack:
        cell = stack.pop()
        for side in maze.open_sides(cell):
            other = maze.neighbour(cell, side)
            assert other is not None
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return seen


def walls_agree(maze: Maze) -> bool:
    """Whether every shared wall is recorded the same from both sides."""
    for row, col, walls in maze:
        for side in Direction:
            other = maze.neighbour((row, col), side)
            if other is None or other not in maze:
                continue
            if walls.has(side) != maze[other].has(side.opposite):
                return False
    return True


def generate(make_maze: MakeMaze, width: int, height: int,
             entry: tuple[int, int], exit: tuple[int, int],
             seed: str | None) -> tuple[Maze, Events]:
    """Build a maze with Wilson's algorithm and return it with the events its
    generator reported."""
    maze = make_maze(width, height, entry, exit, seed=seed)
    events: Events = []
    generator = WilsonsGenerator()
    generator.register_history_callback(
        lambda cell, kind: events.append((cell, kind)))
    generator.generate(maze)
    return maze, events


class Scripted(Generator):
    """Fails the first time (carves nothing), then carves a corridor
    along the first row. Meant for one-row mazes."""

    def __init__(self) -> None:
        """Start with no recorded run."""
        super().__init__()
        self.seeds: list[str | None] = []
        self.grids: list[list[Direction]] = []

    def _generate(self, maze: Maze, seed: str | None) -> None:
        """Record the seed and the walls; the first time, only try to open
        the outer border, which is refused, and from then on carve a corridor
        along the first row."""
        self.seeds.append(seed)
        self.grids.append([walls for _, _, walls in maze])
        if len(self.seeds) == 1:
            # the border on a one-row maze: refused, so nothing is carved
            maze.open_path((0, 0), Direction.SOUTH)
            return
        for col in range(maze.cols - 1):
            maze.open_path((0, col), Direction.EAST)


class TestGenerator:
    """Generator, the base class every algorithm builds on."""

    def test_is_abstract(self) -> None:
        """Generator cannot be used without an algorithm."""
        with pytest.raises(TypeError):
            Generator()  # type: ignore[abstract]

    def test_generate_passes_the_config_seed(self,
                                             make_maze: MakeMaze) -> None:
        """The algorithm is given the seed from the maze's config."""
        generator = Scripted()
        generator.seeds.append("skip the failing run")
        generator.generate(make_maze(width=3, height=1, seed="xyz"))
        assert generator.seeds[1:] == ["xyz"]

    def test_retries_until_the_maze_is_solvable(
            self, make_maze: MakeMaze) -> None:
        """An unsolvable maze is walled up, MAZE_RESET is reported, and the
        algorithm runs again."""
        maze = make_maze(width=3, height=1, seed="first")
        events: Events = []
        generator = Scripted()
        generator.register_history_callback(
            lambda cell, kind: events.append((cell, kind)))
        generator.generate(maze)

        assert len(generator.seeds) == 2
        assert maze.solve() == [Direction.EAST, Direction.EAST]
        # the maze is walled up again before the second try
        assert generator.grids[1] == [CLOSED] * 3
        assert events == [((0, 0), Kind.MAZE_RESET)]

    def test_next_seed_is_derived_from_the_last(
            self, make_maze: MakeMaze) -> None:
        """The retry's seed is derived from the previous seed, so retries are
        reproducible."""
        generator = Scripted()
        generator.generate(make_maze(width=3, height=1, seed="first"))
        random.seed("first")
        assert generator.seeds == ["first", random.randbytes(8).hex()]

    def test_callbacks_are_called_in_order(self) -> None:
        """Callbacks are called in the order they were registered."""
        calls: list[str] = []
        generator = WilsonsGenerator()
        generator.register_history_callback(lambda c, k: calls.append("a"))
        generator.register_history_callback(lambda c, k: calls.append("b"))
        generator._emit((0, 0), Kind.OPEN)
        assert calls == ["a", "b"]

    def test_callbacks_receive_the_cell_and_kind(self) -> None:
        """Callbacks get the cell and what happened to it."""
        events: Events = []
        generator = WilsonsGenerator()
        generator.register_history_callback(
            lambda cell, kind: events.append((cell, kind)))
        generator._emit((3, 4), Kind.MAYBE)
        assert events == [((3, 4), Kind.MAYBE)]

    def test_callbacks_are_per_instance(self) -> None:
        """Registering a callback on one generator does not affect another."""
        first, second = WilsonsGenerator(), WilsonsGenerator()
        first.register_history_callback(lambda c, k: None)
        assert second._history_callback == []

    def test_emitting_without_callbacks_is_fine(self) -> None:
        """Reporting an event with no callback registered does nothing."""
        WilsonsGenerator()._emit((0, 0), Kind.OPEN)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize(("width", "height", "entry", "exit"), SIZES)
class TestWilsonsMazes:
    """Properties every maze from Wilson's algorithm must have, checked over
    several sizes and seeds."""

    def test_is_a_spanning_tree(self, make_maze: MakeMaze, width: int,
                                height: int, entry: tuple[int, int],
                                exit: tuple[int, int], seed: str) -> None:
        """Every playable cell is reachable, and there is no loop: one passage
        fewer than cells."""
        maze, _ = generate(make_maze, width, height, entry, exit, seed)
        cells = playable(maze)
        # connected, and exactly one passage fewer than cells: no loops
        start = (entry[1], entry[0])
        assert reachable(maze, start) == set(cells)
        assert passages(maze) == len(cells) - 1

    def test_is_solvable(self, make_maze: MakeMaze, width: int,
                         height: int, entry: tuple[int, int],
                         exit: tuple[int, int], seed: str) -> None:
        """There is a path from the entry to the exit."""
        maze, _ = generate(make_maze, width, height, entry, exit, seed)
        assert maze.solve()

    def test_walls_are_coherent(self, make_maze: MakeMaze, width: int,
                                height: int, entry: tuple[int, int],
                                exit: tuple[int, int], seed: str) -> None:
        """Every shared wall is recorded the same way by both cells."""
        maze, _ = generate(make_maze, width, height, entry, exit, seed)
        assert walls_agree(maze)

    def test_border_and_logo_stay_closed(self, make_maze: MakeMaze,
                                         width: int, height: int,
                                         entry: tuple[int, int],
                                         exit: tuple[int, int],
                                         seed: str) -> None:
        """The outer border and the logo cells keep all their walls."""
        maze, _ = generate(make_maze, width, height, entry, exit, seed)
        for row, col, walls in maze:
            if maze.in_logo((row, col)):
                assert walls == CLOSED
            for side in Direction:
                other = maze.neighbour((row, col), side)
                if other is not None and other not in maze:
                    assert walls.has(side)

    def test_is_deterministic(self, make_maze: MakeMaze, width: int,
                              height: int, entry: tuple[int, int],
                              exit: tuple[int, int], seed: str) -> None:
        """The same seed gives the same maze and the same events."""
        first, first_events = generate(make_maze, width, height, entry,
                                       exit, seed)
        second, second_events = generate(make_maze, width, height, entry,
                                         exit, seed)
        assert first.grid == second.grid
        assert first_events == second_events

    def test_history_events(self, make_maze: MakeMaze, width: int,
                            height: int, entry: tuple[int, int],
                            exit: tuple[int, int], seed: str) -> None:
        """Events only concern playable cells, start with an OPEN, and every
        playable cell is opened."""
        maze, events = generate(make_maze, width, height, entry, exit, seed)
        cells = set(playable(maze))
        assert events[0][1] is Kind.OPEN  # the first cell of the tree
        assert {cell for cell, _ in events} <= cells
        assert {cell for cell, kind in events if kind is Kind.OPEN} == cells
        assert all(kind is not Kind.MAZE_RESET for _, kind in events)
        # every cell a walk reaches either gets erased or joins the maze
        kinds = Counter(kind for _, kind in events)
        assert kinds[Kind.MAYBE] <= kinds[Kind.RESET] + kinds[Kind.OPEN]


class TestWilsons:
    """Wilson's algorithm in particular cases."""

    def test_different_seeds_give_different_mazes(
            self, make_maze: MakeMaze) -> None:
        """Different seeds give different mazes."""
        mazes = {tuple(walls for _, _, walls in
                       generate(make_maze, 20, 15, (0, 0), (19, 14), seed)[0])
                 for seed in SEEDS}
        assert len(mazes) == len(SEEDS)

    @pytest.mark.parametrize("seed", [None, ""])
    def test_without_a_seed(self, make_maze: MakeMaze,
                            seed: str | None) -> None:
        """Without a seed, a valid maze is still built."""
        maze, _ = generate(make_maze, 10, 8, (0, 0), (9, 7), seed)
        assert passages(maze) == len(playable(maze)) - 1

    def test_a_single_cell(self, make_maze: MakeMaze) -> None:
        """A one-cell maze is just that cell, opened and nothing else."""
        maze = make_maze(width=1, height=1, exit=(0, 0))
        events: Events = []
        generator = WilsonsGenerator()
        generator.register_history_callback(
            lambda cell, kind: events.append((cell, kind)))
        generator._generate(maze, "1")
        assert maze[(0, 0)] == CLOSED
        assert events == [((0, 0), Kind.OPEN)]

    def test_no_playable_cell(self, make_maze: MakeMaze,
                              monkeypatch: pytest.MonkeyPatch) -> None:
        """A maze with no playable cell raises GeneratorError."""
        maze = make_maze()
        monkeypatch.setattr(maze, "in_logo", lambda cell: True)
        with pytest.raises(GeneratorError, match="No playable cells"):
            WilsonsGenerator().generate(maze)

    def test_generator_error_is_an_exception(self) -> None:
        """GeneratorError can be caught as an Exception."""
        assert issubclass(GeneratorError, Exception)
