"""MazeGen, the generator as a single class."""
import pytest

from mazegen import (BacktrackerGenerator, Config, Direction, Generator,
                     Maze, MazeGen, TaintTransformer, WilsonsGenerator)

ALGORITHMS: list[type[Generator]] = [WilsonsGenerator, BacktrackerGenerator]


def by_hand(perfect: bool, algorithm: type[Generator]) -> Maze:
    """The 20x15 maze for seed 42, built from the lower-level pieces."""
    maze = Maze(Config.from_dict({
        "WIDTH": 20, "HEIGHT": 15, "ENTRY": (0, 0), "EXIT": (19, 14),
        "OUTPUT_FILE": "unused", "PERFECT": perfect, "SEED": "42"}))
    algorithm().generate(maze)
    if not perfect:
        TaintTransformer().transform(maze)
    return maze


@pytest.mark.parametrize("perfect", [True, False])
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_matches_the_lower_level_pieces(perfect: bool,
                                        algorithm: type[Generator]) -> None:
    """MazeGen builds the same maze and solution as the pieces it wraps,
    with the algorithm it is given."""
    result = MazeGen(20, 15, (0, 0), (19, 14), perfect, "42",
                     algorithm).generate()
    expected = by_hand(perfect, algorithm)
    assert result["grid"] == expected.grid
    assert result["solution"] == expected.solve()


def test_uses_wilsons_algorithm_by_default() -> None:
    """Without an algorithm, MazeGen uses Wilson's."""
    generator = MazeGen(20, 15, (0, 0), (19, 14), seed="42")
    assert isinstance(generator.generator, WilsonsGenerator)
    assert generator.generate()["grid"] == by_hand(True,
                                                   WilsonsGenerator).grid


def test_algorithms_give_different_mazes() -> None:
    """The backtracker carves a different maze from the same seed."""
    wilsons = MazeGen(20, 15, (0, 0), (19, 14), seed="42").generate()
    backtracker = MazeGen(20, 15, (0, 0), (19, 14), seed="42",
                          algorithm=BacktrackerGenerator).generate()
    assert wilsons["grid"] != backtracker["grid"]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_pac_man_mode_is_braided(algorithm: type[Generator]) -> None:
    """Without perfect, every algorithm's maze is braided."""
    result = MazeGen(20, 15, (0, 0), (19, 14), False, "42",
                     algorithm).generate()
    assert result["fully_braided"] is True


def test_perfect_maze_is_not_braided() -> None:
    """A perfect maze has no braiding to report."""
    result = MazeGen(20, 15, (0, 0), (19, 14), seed="42").generate()
    assert result["fully_braided"] is None


def test_grid_is_a_copy() -> None:
    """Changing the returned grid does not change the generator's maze."""
    generator = MazeGen(20, 15, (0, 0), (19, 14), seed="42")
    grid = generator.generate()["grid"]
    grid[0][0] = Direction(0)
    assert generator.maze.grid[0][0] != Direction(0)


@pytest.mark.parametrize("width, height, entry, exit, message", [
    (0, 15, (0, 0), (0, 14), "WIDTH"),
    (20, 15, (0, 0), (25, 14), "x must be between 0 and 19"),
    (20, 15, (0, -1), (19, 14), "y must be between 0 and 14"),
    (20, 15, (3, 3), (3, 3), "different cell from ENTRY"),
    (20, 15, (0, 0), (6, 5), "42 pattern"),
])
def test_rejects_impossible_parameters(width: int, height: int,
                                       entry: tuple[int, int],
                                       exit: tuple[int, int],
                                       message: str) -> None:
    """Parameters that cannot make a maze raise ValueError, instead of
    generating forever or returning nonsense."""
    with pytest.raises(ValueError, match=message):
        MazeGen(width, height, entry, exit)
