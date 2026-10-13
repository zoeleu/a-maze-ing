"""Direction: the wall flags and the geometry they carry."""
import random

import pytest

from lib import Direction

ALL = Direction.NORTH | Direction.EAST | Direction.SOUTH | Direction.WEST


@pytest.mark.parametrize(("side", "value"), [
    (Direction.NORTH, 1),
    (Direction.EAST, 2),
    (Direction.SOUTH, 4),
    (Direction.WEST, 8),
])
def test_bit_values_match_the_output_format(side: Direction,
                                            value: int) -> None:
    """Each side has the bit the output file uses for it."""
    assert side.value == value


def test_iterating_yields_the_four_sides_in_order() -> None:
    """Iterating gives north, east, south and west, in that order."""
    assert list(Direction) == [Direction.NORTH, Direction.EAST,
                               Direction.SOUTH, Direction.WEST]


@pytest.mark.parametrize(("side", "opposite"), [
    (Direction.NORTH, Direction.SOUTH),
    (Direction.SOUTH, Direction.NORTH),
    (Direction.EAST, Direction.WEST),
    (Direction.WEST, Direction.EAST),
])
def test_opposite(side: Direction, opposite: Direction) -> None:
    """Each side's opposite is the facing side, and back again."""
    assert side.opposite is opposite
    assert side.opposite.opposite is side


@pytest.mark.parametrize(("side", "step"), [
    (Direction.NORTH, (-1, 0)),
    (Direction.EAST, (0, 1)),
    (Direction.SOUTH, (1, 0)),
    (Direction.WEST, (0, -1)),
])
def test_step(side: Direction, step: tuple[int, int]) -> None:
    """Each side steps one cell in its direction, as (row, col)."""
    assert side.step == step


@pytest.mark.parametrize("side", list(Direction))
def test_between_is_the_inverse_of_step(side: Direction) -> None:
    """between() finds the side a step went through, both ways."""
    cell = (5, 5)
    other = (cell[0] + side.step[0], cell[1] + side.step[1])
    assert Direction.between(cell, other) is side
    assert Direction.between(other, cell) is side.opposite


@pytest.mark.parametrize("other", [(5, 5), (7, 5), (6, 6), (3, 3)])
def test_between_rejects_cells_that_are_not_adjacent(
        other: tuple[int, int]) -> None:
    """between() refuses cells that are not side by side."""
    with pytest.raises(ValueError, match="is not adjacent to"):
        Direction.between((5, 5), other)


@pytest.mark.parametrize(("walls", "text"), [
    (Direction.NORTH, "N"),
    (Direction.EAST, "E"),
    (Direction.SOUTH, "S"),
    (Direction.WEST, "W"),
    (Direction(0), "0"),
    (Direction.NORTH | Direction.SOUTH, "5"),
    (ALL, "f"),
])
def test_str(walls: Direction, text: str) -> None:
    """Single sides print as a letter, combinations as a hex digit."""
    assert str(walls) == text


@pytest.mark.parametrize("walls", [Direction(n) for n in range(16)])
def test_hex_format_is_one_digit(walls: Direction) -> None:
    """Every combination of walls formats as one hex digit."""
    assert f"{walls:01x}" == f"{walls.value:x}"


def test_has() -> None:
    """has() tells whether any of the given walls is present."""
    walls = Direction.NORTH | Direction.EAST
    assert walls.has(Direction.NORTH)
    assert walls.has(Direction.EAST)
    assert not walls.has(Direction.SOUTH)
    assert not walls.has(Direction.WEST)
    assert walls.has(Direction.NORTH | Direction.SOUTH)  # any of them
    assert not Direction(0).has(ALL)


def test_has_accepts_plain_ints() -> None:
    """has() works with plain ints as well as Directions."""
    assert Direction.WEST.has(8)
    assert not Direction.WEST.has(1)


def test_subtracting_removes_a_wall() -> None:
    """Subtracting a side removes that wall and stays a Direction."""
    walls = ALL - Direction.NORTH
    assert isinstance(walls, Direction)
    assert walls == Direction.EAST | Direction.SOUTH | Direction.WEST


def test_subtracting_a_missing_wall_changes_nothing() -> None:
    """Removing a wall that is not there changes nothing."""
    assert Direction.EAST - Direction.NORTH == Direction.EAST


def test_adding_puts_a_wall_back() -> None:
    """Adding a side puts the wall up, and adding it twice is harmless."""
    walls = Direction(0) + Direction.SOUTH
    assert isinstance(walls, Direction)
    assert walls == Direction.SOUTH
    assert walls + Direction.SOUTH == Direction.SOUTH  # idempotent


def test_add_and_subtract_accept_plain_ints() -> None:
    """+ and - work with plain ints as well as Directions."""
    assert Direction(0) + 15 == ALL
    assert ALL - 15 == Direction(0)


def test_random_returns_a_single_side() -> None:
    """random() returns one of the four sides, and not always the same one."""
    seen = {Direction.random() for _ in range(200)}
    assert seen <= set(Direction)
    assert len(seen) > 1


def test_random_follows_the_random_module_seed() -> None:
    """random() repeats itself when random is seeded the same way."""
    random.seed("same")
    first = [Direction.random() for _ in range(20)]
    random.seed("same")
    assert [Direction.random() for _ in range(20)] == first
