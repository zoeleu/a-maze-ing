"""MazeTransformer, the base class, and the TaintTransformer that braids a
perfect maze into a Pac-Man board."""
import pytest

from lib import (Cell, Direction, Maze, MazeHistoryCallbackCell,
                 MazeTransformer, TaintTransformer, WilsonsGenerator)
from tests.helpers import MakeMaze
from tests.test_generators import passages, playable, reachable, walls_agree

CLOSED = Direction(sum(Direction))
N, E, S, W = Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST
Kind = MazeHistoryCallbackCell
Events = list[tuple[Cell, MazeHistoryCallbackCell]]

SIZES = [
    (8, 6, (7, 0), (7, 5)),
    (10, 8, (0, 0), (9, 7)),
    (15, 12, (14, 0), (0, 11)),
    (25, 20, (0, 0), (24, 19)),
]
SEEDS = ["0", "42", "seed", "a-maze-ing"]


def generated(make_maze: MakeMaze, width: int, height: int,
              entry: tuple[int, int], exit: tuple[int, int],
              seed: str | None) -> Maze:
    """A perfect maze from Wilson's algorithm, ready to be braided."""
    maze = make_maze(width, height, entry, exit, perfect=False, seed=seed)
    WilsonsGenerator().generate(maze)
    return maze


def braided(make_maze: MakeMaze, width: int, height: int,
            entry: tuple[int, int], exit: tuple[int, int],
            seed: str | None) -> tuple[Maze, bool, Events]:
    """Generate a maze and braid it; returns the maze, whether every dead end
    was removed, and the reported events."""
    maze = generated(make_maze, width, height, entry, exit, seed)
    events: Events = []
    transformer = TaintTransformer()
    transformer.register_history_callback(
        lambda cell, kind: events.append((cell, kind)))
    return maze, transformer.transform(maze), events


def open_everything(maze: Maze) -> None:
    """Knock down every inner wall of *maze*."""
    for row, col, _ in maze:
        for side in (E, S):
            maze.open_path((row, col), side)


class Recorder(MazeTransformer):
    """Records the seed it is given, and reports one event."""

    def __init__(self) -> None:
        """Start with no recorded seed."""
        super().__init__()
        self.seeds: list[str | None] = []

    def _transform(self, maze: Maze, seed: str | None) -> bool:
        """Record *seed*, report (1, 2) as opened, and claim to have failed."""
        self.seeds.append(seed)
        self._emit((1, 2), Kind.OPEN)
        return False


class TestMazeTransformer:
    """MazeTransformer, the base class of every transformer."""

    def test_is_abstract(self) -> None:
        """MazeTransformer cannot be used without a transformation."""
        with pytest.raises(TypeError):
            MazeTransformer()  # type: ignore[abstract]

    def test_transform_passes_the_seed_and_result(
            self, make_maze: MakeMaze) -> None:
        """transform() hands over the config's seed and returns the result as
        is."""
        transformer = Recorder()
        assert transformer.transform(make_maze(seed="abc")) is False
        assert transformer.seeds == ["abc"]

    def test_callbacks(self, make_maze: MakeMaze) -> None:
        """Every registered callback hears every event."""
        events: Events = []
        transformer = Recorder()
        transformer.register_history_callback(
            lambda cell, kind: events.append((cell, kind)))
        transformer.register_history_callback(
            lambda cell, kind: events.append((cell, kind)))
        transformer.transform(make_maze())
        assert events == [((1, 2), Kind.OPEN)] * 2

    def test_callbacks_are_per_instance(self) -> None:
        """A callback on one transformer is not on another."""
        first, second = Recorder(), Recorder()
        first.register_history_callback(lambda c, k: None)
        assert second._history_callback == []


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize(("width", "height", "entry", "exit"), SIZES)
class TestTaintedMazes:
    """Properties every braided maze must have, checked over several sizes and
    seeds."""

    def test_removes_every_dead_end(self, make_maze: MakeMaze, width: int,
                                    height: int, entry: tuple[int, int],
                                    exit: tuple[int, int],
                                    seed: str) -> None:
        """Only dead ends boxed in by the logo and the border are left, and the
        two pockets inside the 2 are among them."""
        maze, done, _ = braided(make_maze, width, height, entry, exit, seed)
        assert done
        left = [(r, c) for r, c, _ in maze
                if TaintTransformer._is_dead_end(maze, (r, c))]
        # only cells boxed in by the logo and the border may stay dead ends
        assert not any(TaintTransformer._has_openable_wall(maze, cell)
                       for cell in left)
        # the two pockets inside the 2 are always among them
        row, col = maze.center_cell
        assert {(row - 1, col + 2), (row + 1, col + 2)} <= set(left)

    def test_no_open_three_by_three(self, make_maze: MakeMaze, width: int,
                                    height: int, entry: tuple[int, int],
                                    exit: tuple[int, int],
                                    seed: str) -> None:
        """Braiding never opens a 3x3 area."""
        maze, _, _ = braided(make_maze, width, height, entry, exit, seed)
        transformer = TaintTransformer()
        assert not any(transformer._has_open_block(maze, (r, c))
                       for r, c, _ in maze)

    def test_still_a_valid_connected_maze(self, make_maze: MakeMaze,
                                          width: int, height: int,
                                          entry: tuple[int, int],
                                          exit: tuple[int, int],
                                          seed: str) -> None:
        """The walls still agree, every playable cell is reachable, the exit
        too, and the logo is untouched."""
        maze, _, _ = braided(make_maze, width, height, entry, exit, seed)
        assert walls_agree(maze)
        assert reachable(maze, (entry[1], entry[0])) == set(playable(maze))
        assert maze.solve()
        for row, col, walls in maze:
            if maze.in_logo((row, col)):
                assert walls == CLOSED

    def test_only_opens_walls(self, make_maze: MakeMaze, width: int,
                              height: int, entry: tuple[int, int],
                              exit: tuple[int, int], seed: str) -> None:
        """Braiding only removes walls, and it adds loops."""
        before = generated(make_maze, width, height, entry, exit, seed)
        after, _, _ = braided(make_maze, width, height, entry, exit, seed)
        for (_, _, old), (_, _, new) in zip(before, after):
            assert new & ~old == 0  # no wall that was open is closed
        # a perfect maze has no loop; braiding adds some
        assert passages(after) > passages(before)

    def test_corners_are_opened(self, make_maze: MakeMaze,
                                width: int, height: int,
                                entry: tuple[int, int],
                                exit: tuple[int, int],
                                seed: str) -> None:
        """Each corner is opened towards every playable neighbour."""
        maze, _, _ = braided(make_maze, width, height, entry, exit, seed)
        last_row, last_col = maze.rows - 1, maze.cols - 1
        for corner in ((0, 0), (0, last_col), (last_row, 0),
                       (last_row, last_col)):
            if maze.in_logo(corner):
                continue
            # every side facing a playable cell is opened
            playable_sides = []
            for side in Direction:
                other = maze.neighbour(corner, side)
                if other is not None and other in maze \
                        and not maze.in_logo(other):
                    playable_sides.append(side)
            assert list(maze.open_sides(corner)) == playable_sides

    def test_opens_the_logo_corridor(self, make_maze: MakeMaze, width: int,
                                     height: int, entry: tuple[int, int],
                                     exit: tuple[int, int],
                                     seed: str) -> None:
        """The corridor between the 4 and the 2 is opened and marked."""
        maze, _, _ = braided(make_maze, width, height, entry, exit, seed)
        row, col = maze.center_cell
        for top in range(row - 1, row + 3):
            assert maze.is_open((top, col), S)
            assert {(top, col), (top + 1, col)} <= maze.marked

    def test_is_deterministic(self, make_maze: MakeMaze, width: int,
                              height: int, entry: tuple[int, int],
                              exit: tuple[int, int], seed: str) -> None:
        """The same seed gives the same braided maze and the same events."""
        first, _, first_events = braided(make_maze, width, height, entry,
                                         exit, seed)
        second, _, second_events = braided(make_maze, width, height, entry,
                                           exit, seed)
        assert first.grid == second.grid
        assert first_events == second_events

    def test_history_events(self, make_maze: MakeMaze, width: int,
                            height: int, entry: tuple[int, int],
                            exit: tuple[int, int], seed: str) -> None:
        """Events concern cells in the maze, and only playable cells are
        opened."""
        maze, _, events = braided(make_maze, width, height, entry, exit,
                                  seed)
        assert events
        assert all(cell in maze for cell, _ in events)
        # a corner on the logo is tried, but never opened
        opened = {cell for cell, kind in events if kind is Kind.OPEN}
        assert opened and opened <= set(playable(maze))
        assert Kind.MAZE_RESET not in {kind for _, kind in events}


class TestTaint:
    """TaintTransformer in particular cases, and its helpers."""

    def test_without_a_seed(self, make_maze: MakeMaze) -> None:
        """Without a seed the maze is still braided and solvable."""
        maze, done, _ = braided(make_maze, 10, 8, (0, 0), (9, 7), None)
        assert done
        assert maze.solve()

    def test_maze_without_the_logo(self, make_maze: MakeMaze) -> None:
        """Without a logo there is no corridor to open; only corners get
        marked."""
        maze, done, _ = braided(make_maze, 7, 5, (0, 0), (6, 4), "1")
        assert done
        # there is no logo corridor, so only corners can be marked
        assert maze.marked <= {(0, 0), (0, 6), (4, 0), (4, 6)}

    def test_reports_dead_ends_it_could_not_remove(
            self, make_maze: MakeMaze,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """When no opening is allowed, every try is undone and transform()
        returns False."""
        # with 1x1 blocks every opening counts as an open area, so none
        # is kept
        monkeypatch.setattr(TaintTransformer, "BLOCK", 1)
        maze = generated(make_maze, 10, 8, (0, 0), (9, 7), "42")
        before = [walls for _, _, walls in maze]
        events: Events = []
        transformer = TaintTransformer()
        transformer.register_history_callback(
            lambda cell, kind: events.append((cell, kind)))
        assert transformer.transform(maze) is False
        assert Kind.RESET in {kind for _, kind in events}
        # only the logo corridor was opened; every other try was undone
        changed = {(r, c) for (r, c, new), old in zip(maze, before)
                   if new != old}
        assert changed <= maze.marked

    def test_is_dead_end(self, make_maze: MakeMaze) -> None:
        """A dead end is a cell with exactly one opening."""
        maze = make_maze(width=3, height=1, exit=(2, 0))
        maze.open_path((0, 0), E)
        assert TaintTransformer._is_dead_end(maze, (0, 0))
        assert TaintTransformer._is_dead_end(maze, (0, 1))
        assert not TaintTransformer._is_dead_end(maze, (0, 2))  # walled in
        maze.open_path((0, 1), E)
        assert not TaintTransformer._is_dead_end(maze, (0, 1))

    def test_logo_cells_are_not_dead_ends(self, make_maze: MakeMaze,
                                          monkeypatch: pytest.MonkeyPatch
                                          ) -> None:
        """Logo cells never count as dead ends."""
        maze = make_maze(width=2, height=1, exit=(1, 0))
        maze.open_path((0, 0), E)
        monkeypatch.setattr(maze, "in_logo", lambda cell: True)
        assert not TaintTransformer._is_dead_end(maze, (0, 0))

    def test_has_openable_wall(self, make_maze: MakeMaze) -> None:
        """A wall can be opened if it faces a playable cell, not the logo."""
        maze = make_maze(width=10, height=8)
        assert TaintTransformer._has_openable_wall(maze, (0, 0))
        # (2, 0) is closed towards the logo at (2, 1) but not towards
        # (1, 0) and (3, 0)
        assert TaintTransformer._has_openable_wall(maze, (2, 0))
        maze.open_path((2, 0), N)
        maze.open_path((2, 0), S)
        assert not TaintTransformer._has_openable_wall(maze, (2, 0))

    def test_border_only_walls_are_not_openable(self,
                                                make_maze: MakeMaze) -> None:
        """Walls on the border cannot be opened."""
        maze = make_maze(width=1, height=2, exit=(0, 1))
        maze.open_path((0, 0), S)
        assert not TaintTransformer._has_openable_wall(maze, (0, 0))

    def test_has_open_block(self, make_maze: MakeMaze) -> None:
        """Every cell of a fully open 4x4 maze is in an open 3x3 area."""
        maze = make_maze(width=4, height=4, exit=(3, 3))
        transformer = TaintTransformer()
        assert not transformer._has_open_block(maze, (1, 1))
        open_everything(maze)
        assert all(transformer._has_open_block(maze, (r, c))
                   for r, c, _ in maze)

    def test_one_closed_wall_breaks_the_block(self,
                                              make_maze: MakeMaze) -> None:
        """One closed wall inside a 3x3 area is enough to break it."""
        maze = make_maze(width=3, height=3, exit=(2, 2))
        open_everything(maze)
        maze[(1, 1)] += E
        maze[(1, 2)] += W
        assert not TaintTransformer()._has_open_block(maze, (1, 1))

    def test_two_by_two_is_not_a_block(self, make_maze: MakeMaze) -> None:
        """An open area smaller than 3x3 is fine."""
        maze = make_maze(width=2, height=2, exit=(1, 1))
        open_everything(maze)
        assert not TaintTransformer()._has_open_block(maze, (0, 0))

    def test_remove_dead_end_prefers_another_dead_end(
            self, make_maze: MakeMaze) -> None:
        """A dead end is joined to a neighbouring dead end when it can be,
        fixing both."""
        # two corridors: (0, 0)-(1, 0), and (1, 1)-(0, 1)-(0, 2)-(1, 2)
        maze = make_maze(width=3, height=2, exit=(2, 1))
        maze.open_path((0, 0), S)
        maze.open_path((0, 1), S)
        maze.open_path((0, 1), E)
        maze.open_path((0, 2), S)
        # (1, 0) can join (1, 1), which is a dead end too
        assert TaintTransformer()._remove_dead_end(maze, (1, 0))
        assert maze.is_open((1, 0), E)

    def test_remove_dead_end_gives_up(self, make_maze: MakeMaze) -> None:
        """A dead end with no wall to open is reported as tried and reset."""
        maze = make_maze(width=1, height=2, exit=(0, 1))
        maze.open_path((0, 0), S)
        events: Events = []
        transformer = TaintTransformer()
        transformer.register_history_callback(
            lambda cell, kind: events.append((cell, kind)))
        assert not transformer._remove_dead_end(maze, (0, 0))
        assert events == [((0, 0), Kind.MAYBE), ((0, 0), Kind.RESET)]

    def test_open_corners_skips_a_three_by_three(
            self, make_maze: MakeMaze) -> None:
        """A corner wall stays closed if opening it opens a 3x3 area."""
        maze = make_maze(width=3, height=3, exit=(2, 2))
        open_everything(maze)
        maze[(0, 0)] += E
        maze[(0, 1)] += W
        TaintTransformer()._open_corners(maze)
        # opening that wall again would make the whole maze one open area
        assert not maze.is_open((0, 0), E)
