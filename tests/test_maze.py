"""Maze: the wall grid, its passages, the solver and the output file."""
import pytest

from mazegen import Cell, Direction, Maze
from tests.helpers import MakeMaze

N, E, S, W = Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST
CLOSED = N | E | S | W


def open_all(maze: Maze) -> None:
    """Knock down every wall inside the maze that is not the logo's."""
    for row, col, _ in maze:
        for side in (E, S):
            maze.open_path((row, col), side)


def walk(start: Cell, sides: list[Direction]) -> list[Cell]:
    """The cells visited by following *sides* from *start*."""
    cells = [start]
    for side in sides:
        last = cells[-1]
        cells.append((last[0] + side.step[0], last[1] + side.step[1]))
    return cells


class TestConstruction:
    """A new maze, before anything is carved."""

    def test_size_comes_from_the_config(self, make_maze: MakeMaze) -> None:
        """The grid is HEIGHT rows of WIDTH cells."""
        maze = make_maze(width=10, height=8)
        assert (maze.rows, maze.cols) == (8, 10)
        assert len(maze.grid) == 8
        assert all(len(row) == 10 for row in maze.grid)

    def test_every_wall_starts_closed(self, make_maze: MakeMaze) -> None:
        """Every cell starts with its four walls up."""
        maze = make_maze()
        assert all(walls == CLOSED for _, _, walls in maze)

    def test_rows_are_independent(self, make_maze: MakeMaze) -> None:
        """Changing one cell does not change the cells of another row."""
        maze = make_maze()
        maze[(0, 0)] = Direction(0)
        assert maze[(1, 0)] == CLOSED

    def test_keeps_its_config(self, make_maze: MakeMaze) -> None:
        """The maze keeps the config it was built from."""
        maze = make_maze(seed="abc")
        assert maze.config.seed == "abc"

    def test_nothing_is_marked(self, make_maze: MakeMaze) -> None:
        """No cell is marked to begin with."""
        assert make_maze().marked == set()

    def test_logo_and_center(self, make_maze: MakeMaze,
                             capsys: pytest.CaptureFixture[str]) -> None:
        """A maze big enough has the logo, centred, and prints no warning."""
        maze = make_maze(width=10, height=8)
        assert maze.has_logo
        assert maze.center_cell == (3, 4)
        assert capsys.readouterr().err == ""

    def test_too_small_for_the_logo_warns(
            self, make_maze: MakeMaze,
            capsys: pytest.CaptureFixture[str]) -> None:
        """A maze too small for the logo says so on stderr."""
        maze = make_maze(width=7, height=6)
        assert not maze.has_logo
        assert "too small for the 42 logo" in capsys.readouterr().err


class TestGridAccess:
    """Reading and writing cells, and walking over them."""

    @pytest.mark.parametrize(("cell", "inside"), [
        ((0, 0), True), ((7, 9), True), ((3, 4), True),
        ((-1, 0), False), ((0, -1), False), ((8, 0), False),
        ((0, 10), False),
    ])
    def test_contains(self, make_maze: MakeMaze, cell: Cell,
                      inside: bool) -> None:
        """Only cells inside the grid are in the maze."""
        assert (cell in make_maze(width=10, height=8)) is inside

    def test_iterates_row_by_row(self, make_maze: MakeMaze) -> None:
        """Iterating goes along each row, top to bottom."""
        maze = make_maze(width=3, height=2)
        assert [(r, c) for r, c, _ in maze] == [
            (0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]

    def test_iteration_yields_the_walls(self, make_maze: MakeMaze) -> None:
        """Iterating yields each cell's walls with its position."""
        maze = make_maze(width=3, height=2)
        maze[(1, 2)] = N
        assert list(maze)[-1] == (1, 2, N)

    def test_get_and_set(self, make_maze: MakeMaze) -> None:
        """Indexing by (row, col) reads and writes the grid."""
        maze = make_maze()
        maze[(2, 3)] = N | W
        assert maze[(2, 3)] == N | W
        assert maze.grid[2][3] == N | W


class TestNeighbour:
    """Maze.neighbour, which steps from a cell to the next one."""

    @pytest.mark.parametrize(("side", "expected"), [
        (N, (1, 2)), (E, (2, 3)), (S, (3, 2)), (W, (2, 1)),
    ])
    def test_steps_to_the_side(self, make_maze: MakeMaze, side: Direction,
                               expected: Cell) -> None:
        """The neighbour is one step towards the given side."""
        assert make_maze().neighbour((2, 2), side) == expected

    def test_may_step_outside_the_maze(self, make_maze: MakeMaze) -> None:
        """Stepping off the edge gives a cell outside the maze, not None."""
        # callers check the result is in the maze
        assert make_maze().neighbour((0, 0), N) == (-1, 0)

    def test_none_for_a_cell_outside_the_maze(self,
                                              make_maze: MakeMaze) -> None:
        """A cell outside the maze has no neighbour."""
        assert make_maze().neighbour((-1, 0), S) is None


class TestPassages:
    """Opening walls between cells, and telling which are open."""

    def test_closed_maze_has_no_passage(self, make_maze: MakeMaze) -> None:
        """A new maze has no open passage anywhere."""
        maze = make_maze()
        assert not any(maze.is_open((r, c), side)
                       for r, c, _ in maze for side in Direction)

    def test_open_path_opens_both_sides(self, make_maze: MakeMaze) -> None:
        """Opening a passage removes the wall from both cells."""
        maze = make_maze()
        assert maze.open_path((0, 0), E)
        assert maze[(0, 0)] == N | S | W
        assert maze[(0, 1)] == N | E | S
        assert maze.is_open((0, 0), E)
        assert maze.is_open((0, 1), W)

    def test_a_wall_on_either_side_closes_the_passage(
            self, make_maze: MakeMaze) -> None:
        """A passage is only open when neither cell has the wall."""
        maze = make_maze()
        maze[(0, 0)] = maze[(0, 0)] - E  # only one side knocked down
        assert not maze.is_open((0, 0), E)
        assert not maze.is_open((0, 1), W)

    def test_the_border_is_never_open(self, make_maze: MakeMaze) -> None:
        """The outer border counts as closed even without walls."""
        maze = make_maze(width=3, height=3)
        for row, col, _ in maze:
            maze[(row, col)] = Direction(0)
        assert not maze.is_open((0, 0), N)
        assert not maze.is_open((0, 0), W)
        assert not maze.is_open((2, 2), S)
        assert not maze.is_open((2, 2), E)

    def test_outside_cell_is_never_open(self, make_maze: MakeMaze) -> None:
        """A cell outside the maze has no open side."""
        assert not make_maze().is_open((-5, -5), S)

    def test_open_path_refuses_an_open_passage(self,
                                               make_maze: MakeMaze) -> None:
        """Opening a passage that is already open reports failure."""
        maze = make_maze()
        maze.open_path((0, 0), S)
        assert not maze.open_path((0, 0), S)
        assert not maze.open_path((1, 0), N)

    def test_open_path_refuses_the_border(self, make_maze: MakeMaze) -> None:
        """The border cannot be opened."""
        maze = make_maze()
        assert not maze.open_path((0, 0), N)
        assert maze[(0, 0)] == CLOSED

    def test_open_path_refuses_a_cell_outside(self,
                                              make_maze: MakeMaze) -> None:
        """A cell outside the maze cannot be opened."""
        assert not make_maze().open_path((20, 20), N)

    @pytest.mark.parametrize(("cell", "side"), [
        ((1, 0), E),  # into the logo, at (1, 1)
        ((1, 1), E),  # out of the logo
        ((1, 1), S),  # between two logo cells
    ])
    def test_open_path_never_touches_the_logo(self, make_maze: MakeMaze,
                                              cell: Cell,
                                              side: Direction) -> None:
        """No passage can lead into, out of or across the logo."""
        maze = make_maze(width=10, height=8)
        assert not maze.open_path(cell, side)
        assert maze[cell] == CLOSED

    def test_open_sides(self, make_maze: MakeMaze) -> None:
        """open_sides() lists the open sides, in Direction order."""
        maze = make_maze()
        maze.open_path((4, 0), N)
        maze.open_path((4, 0), S)
        assert list(maze.open_sides((4, 0))) == [N, S]
        assert list(maze.open_sides((0, 9))) == []

    def test_in_logo(self, make_maze: MakeMaze) -> None:
        """The maze knows its logo cells, and has none when too small."""
        maze = make_maze(width=10, height=8)
        assert maze.in_logo((1, 1))
        assert not maze.in_logo((0, 0))
        assert not make_maze(width=7, height=6).in_logo((1, 0))


class TestSolve:
    """Maze.solve, the shortest path from the entry to the exit."""

    def test_straight_corridor(self, make_maze: MakeMaze) -> None:
        """A straight corridor is solved in a straight line."""
        maze = make_maze(width=4, height=1, entry=(0, 0), exit=(3, 0))
        open_all(maze)
        assert maze.solve() == [E, E, E]

    def test_reads_entry_and_exit_as_x_y(self, make_maze: MakeMaze) -> None:
        """The entry and exit are read as (x, y), not (row, col)."""
        maze = make_maze(width=1, height=4, entry=(0, 3), exit=(0, 0))
        open_all(maze)
        assert maze.solve() == [N, N, N]

    def test_finds_a_shortest_path(self, make_maze: MakeMaze) -> None:
        """With every wall open, the path is as short as possible and ends on
        the exit."""
        maze = make_maze(width=5, height=5, entry=(0, 0), exit=(4, 4))
        open_all(maze)
        path = maze.solve()
        assert len(path) == 8
        assert walk((0, 0), path)[-1] == (4, 4)

    def test_path_goes_around_walls(self, make_maze: MakeMaze) -> None:
        """The path follows the open passages, around the walls."""
        # a U: down the left column, along the bottom, up the right
        maze = make_maze(width=3, height=3, entry=(0, 0), exit=(2, 0))
        for cell, side in [((0, 0), S), ((1, 0), S), ((2, 0), E),
                           ((2, 1), E), ((2, 2), N), ((1, 2), N)]:
            maze.open_path(cell, side)
        path = maze.solve()
        assert path == [S, S, E, E, N, N]
        cells = walk((0, 0), path)
        assert all(maze.is_open(a, Direction.between(a, b))
                   for a, b in zip(cells, cells[1:]))

    def test_unreachable_exit(self, make_maze: MakeMaze) -> None:
        """An exit that cannot be reached raises ValueError."""
        maze = make_maze(width=3, height=3)
        with pytest.raises(ValueError, match="No path between the entry and "
                                             "the exit"):
            maze.solve()


class TestOutput:
    """The text written to the output file."""

    def test_single_row(self, make_maze: MakeMaze) -> None:
        """One row of hex digits, a blank line, the entry, the exit and the
        path."""
        maze = make_maze(width=2, height=1, entry=(0, 0), exit=(1, 0))
        maze.open_path((0, 0), E)
        assert maze.get_output() == "d7\n\n0,0\n1,0\nE\n"

    def test_rows_and_footer(self, make_maze: MakeMaze) -> None:
        """Each row is on its own line, and the footer uses (x, y)."""
        maze = make_maze(width=2, height=2, entry=(1, 0), exit=(0, 1))
        maze.open_path((0, 1), W)
        maze.open_path((0, 0), S)
        # (0, 0): N W closed, (0, 1): N E S, (1, 0): E S W, (1, 1): all
        assert maze.get_output() == "97\nef\n\n1,0\n0,1\nWS\n"

    def test_one_hex_digit_per_cell(self, make_maze: MakeMaze) -> None:
        """Every cell is written as one hex digit of its walls."""
        maze = make_maze(width=3, height=1, entry=(0, 0), exit=(2, 0))
        open_all(maze)
        grid = maze.get_output().split("\n\n")[0]
        assert grid == "d57"

    def test_unsolvable_maze_has_no_output(self, make_maze: MakeMaze) -> None:
        """A maze without a path cannot be written out."""
        with pytest.raises(ValueError):
            make_maze().get_output()


class TestDebugRender:
    """Maze.debug_render, the ASCII drawing used for debugging."""

    def test_shape(self, make_maze: MakeMaze) -> None:
        """There is a line per row and wall row, all the same width."""
        maze = make_maze(width=4, height=3, entry=(0, 0), exit=(3, 2))
        open_all(maze)
        lines = maze.debug_render().splitlines()
        assert len(lines) == 2 * 3 + 1
        assert all(len(line) == 4 * 4 + 1 for line in lines)
        assert lines[0] == lines[-1] == "+---+---+---+---+"

    def test_marks_entry_exit_and_path(self, make_maze: MakeMaze) -> None:
        """The entry is E, the exit X and the path dots."""
        maze = make_maze(width=3, height=1, entry=(0, 0), exit=(2, 0))
        open_all(maze)
        assert maze.debug_render().splitlines()[1] == "| E . . . X |"

    def test_walls_and_openings(self, make_maze: MakeMaze) -> None:
        """Closed walls are drawn and open ones left blank."""
        maze = make_maze(width=2, height=2, entry=(0, 0), exit=(0, 1))
        maze.open_path((0, 0), S)
        maze.open_path((0, 0), E)
        assert maze.debug_render() == ("+---+---+\n"
                                       "| E     |\n"
                                       "+ . +---+\n"
                                       "| X |   |\n"
                                       "+---+---+")

    def test_logo_and_marked_cells(self, make_maze: MakeMaze) -> None:
        """Logo cells show 42 and marked cells O."""
        maze = make_maze(width=10, height=8)
        open_all(maze)
        maze.marked.add((7, 0))
        text = maze.debug_render()
        assert text.count("42 ") == 18
        assert "| O " in text.splitlines()[15]

    def test_path_through_the_bottom_row(self, make_maze: MakeMaze) -> None:
        """A path through a south wall is drawn as a dot in the wall row."""
        maze = make_maze(width=1, height=2, entry=(0, 0), exit=(0, 1))
        maze.open_path((0, 0), S)
        assert maze.debug_render().splitlines()[2] == "+ . +"
