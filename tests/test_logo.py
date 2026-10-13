"""The 42 logo helpers, which work without a Maze."""
import pytest

from lib import in_logo, logo_center, logo_fits

# the logo drawn on the smallest maze that holds it, 8 wide by 6 tall
SMALLEST = """\
#...###.
#.....#.
###.###.
..#.#...
..#.###.
........
"""


@pytest.mark.parametrize(("rows", "cols", "fits"), [
    (6, 8, True),
    (100, 100, True),
    (5, 8, False),
    (6, 7, False),
    (1, 1, False),
    (0, 0, False),
])
def test_logo_fits(rows: int, cols: int, fits: bool) -> None:
    """The logo needs a maze of at least 8 columns by 6 rows."""
    assert logo_fits(rows, cols) is fits


@pytest.mark.parametrize(("rows", "cols", "center"), [
    (6, 8, (2, 3)),
    (7, 9, (3, 4)),
    (8, 10, (3, 4)),
    (1, 1, (0, 0)),
])
def test_logo_center(rows: int, cols: int, center: tuple[int, int]) -> None:
    """The logo is centred on the middle cell, rounding up and left."""
    assert logo_center(rows, cols) == center


def test_logo_draws_42() -> None:
    """The logo's cells spell 42 in the smallest maze that holds it."""
    drawing = "".join(
        "".join("#" if in_logo((row, col), 6, 8) else "."
                for col in range(8)) + "\n"
        for row in range(6))
    assert drawing == SMALLEST


@pytest.mark.parametrize(("rows", "cols"), [(6, 8), (8, 10), (25, 40)])
def test_logo_has_18_cells(rows: int, cols: int) -> None:
    """The logo is always 18 cells, whatever the maze's size."""
    cells = [(r, c) for r in range(rows) for c in range(cols)
             if in_logo((r, c), rows, cols)]
    assert len(cells) == 18


def test_logo_follows_the_center() -> None:
    """The logo moves with the centre of the maze."""
    for rows, cols in ((6, 8), (11, 13), (20, 21)):
        center_row, center_col = logo_center(rows, cols)
        # the top-left stroke of the 4 sits two up and three left
        assert in_logo((center_row - 2, center_col - 3), rows, cols)
        # the centre itself is the gap between the 4 and the 2
        assert not in_logo((center_row, center_col), rows, cols)


@pytest.mark.parametrize(("rows", "cols"), [(5, 8), (6, 7), (1, 1)])
def test_no_logo_when_too_small(rows: int, cols: int) -> None:
    """A maze too small for the logo has no logo cell at all."""
    assert not any(in_logo((r, c), rows, cols)
                   for r in range(rows) for c in range(cols))


def test_cells_outside_the_maze_are_never_logo() -> None:
    """Cells outside the maze are never part of the logo."""
    assert not in_logo((-1, -1), 6, 8)
    assert not in_logo((100, 100), 6, 8)
