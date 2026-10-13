"""The widget that draws a maze, used here without an app."""
import re

import pytest
from rich.console import Console
from rich.style import Style
from rich.text import Text

from lib import Direction, Maze
from lib.ui.renderer import (CYAN, GOLD, GROUND, LOGO_COLOURS, UNTOUCHED,
                             WALL_COLOURS, AMazeIngRenderer, Swatch, Tile,
                             drawing_height, drawing_width)
from tests.helpers import MakeMaze

E, S = Direction.EAST, Direction.SOUTH
T = Tile
CONSOLE = Console()


@pytest.mark.parametrize(("cols", "compact", "width"), [
    (1, False, 6), (1, True, 3), (10, False, 42), (10, True, 21),
])
def test_drawing_width(cols: int, compact: bool, width: int) -> None:
    """A maze takes 2 columns per tile at full size, 1 when compact."""
    assert drawing_width(cols, compact) == width


@pytest.mark.parametrize(("rows", "compact", "height"), [
    (1, False, 3), (1, True, 2), (8, False, 17), (8, True, 9),
    (2, True, 3),
])
def test_drawing_height(rows: int, compact: bool, height: int) -> None:
    """A maze takes 1 row per tile at full size, half that when compact."""
    assert drawing_height(rows, compact) == height


@pytest.mark.parametrize("swatch", WALL_COLOURS + LOGO_COLOURS)
def test_swatches(swatch: Swatch) -> None:
    """Every colour has a name and an uppercase #RRGGBB value."""
    assert re.fullmatch(r"#[0-9A-F]{6}", swatch.hex)
    assert swatch.name.isalpha()


def test_swatch_names_are_unique() -> None:
    """No two colours share a name."""
    names = [swatch.name for swatch in WALL_COLOURS + LOGO_COLOURS]
    assert len(names) == len(set(names))


def corridor(make_maze: MakeMaze) -> Maze:
    """A 3x1 maze with every inner wall open, from (0, 0) to (2, 0)."""
    maze = make_maze(width=3, height=1, exit=(2, 0))
    maze.open_path((0, 0), E)
    maze.open_path((0, 1), E)
    return maze


class TestTiles:
    """How a maze is laid out as tiles before it is drawn."""

    def test_nothing_to_draw_before_show(self) -> None:
        """Before show(), the renderer draws nothing."""
        assert AMazeIngRenderer().render().plain == ""

    def test_corridor(self, make_maze: MakeMaze) -> None:
        """Cells and open passages are OPEN, the rest WALL, with the entry and
        exit on top."""
        renderer = AMazeIngRenderer()
        renderer.show(corridor(make_maze))
        wall = [T.WALL] * 7
        assert renderer._tiles() == [
            wall,
            [T.WALL, T.ENTRY, T.OPEN, T.OPEN, T.OPEN, T.EXIT, T.WALL],
            wall,
        ]

    def test_path(self, make_maze: MakeMaze) -> None:
        """The path covers its cells and the passages between them."""
        renderer = AMazeIngRenderer()
        renderer.show(corridor(make_maze), path=[(0, 0), (0, 1), (0, 2)])
        assert renderer._tiles()[1] == [T.WALL, T.ENTRY, T.PATH, T.PATH,
                                        T.PATH, T.EXIT, T.WALL]

    def test_hidden_path(self, make_maze: MakeMaze) -> None:
        """With show_path off, the path is not drawn."""
        renderer = AMazeIngRenderer()
        renderer.show(corridor(make_maze), path=[(0, 0), (0, 1), (0, 2)])
        renderer.show_path = False
        assert T.PATH not in renderer._tiles()[1]

    def test_trail_and_head(self, make_maze: MakeMaze) -> None:
        """The trail is drawn, with its last cell as the head."""
        maze = make_maze(width=4, height=1, entry=(3, 0), exit=(2, 0))
        renderer = AMazeIngRenderer()
        renderer.show(maze, trail=[(0, 0), (0, 1)])
        assert renderer._tiles()[1][:5] == [T.WALL, T.TRAIL, T.TRAIL,
                                            T.HEAD, T.WALL]

    def test_vertical_passages(self, make_maze: MakeMaze) -> None:
        """Passages to the south open the wall tile below the cell."""
        maze = make_maze(width=1, height=2, exit=(0, 1))
        maze.open_path((0, 0), S)
        renderer = AMazeIngRenderer()
        renderer.show(maze)
        assert [line[1] for line in renderer._tiles()] == [
            T.WALL, T.ENTRY, T.OPEN, T.EXIT, T.WALL]

    def test_untouched_cells(self, make_maze: MakeMaze) -> None:
        """Fully walled cells are dimmed only when the renderer is asked to."""
        maze = make_maze(width=4, height=1, exit=(3, 0))
        maze.open_path((0, 0), E)
        dim = AMazeIngRenderer(dim_untouched=True)
        dim.show(maze)
        assert dim._tiles()[1][3:6] == [T.OPEN, T.WALL, T.UNTOUCHED]
        plain = AMazeIngRenderer()
        plain.show(maze)
        assert plain._tiles()[1][5] == T.OPEN

    def test_logo_is_solid(self, make_maze: MakeMaze) -> None:
        """Logo cells and the walls between them form one solid shape."""
        maze = make_maze(width=8, height=6, entry=(7, 0), exit=(7, 5))
        renderer = AMazeIngRenderer()
        renderer.show(maze)
        tiles = renderer._tiles()
        # the 4's left stroke: cells (0, 0) to (2, 0), joined
        assert [tiles[r][1] for r in range(1, 6)] == [T.LOGO] * 5
        # (0, 0) and (0, 1) are not both logo, so the wall stays a wall
        assert tiles[1][2] == T.WALL
        logo_cells = sum(row[1::2].count(T.LOGO) for row in tiles[1::2])
        assert logo_cells == 18

    def test_entry_and_exit_are_x_y(self, make_maze: MakeMaze) -> None:
        """The entry and exit are placed from (x, y)."""
        maze = make_maze(width=2, height=3, entry=(1, 0), exit=(0, 2))
        renderer = AMazeIngRenderer()
        renderer.show(maze)
        tiles = renderer._tiles()
        assert tiles[1][3] == T.ENTRY
        assert tiles[5][1] == T.EXIT

    def test_lay_paints_the_passages(self) -> None:
        """_lay() paints each cell and the passage from the one before it."""
        tiles = [[T.WALL] * 5 for _ in range(5)]
        AMazeIngRenderer._lay(tiles, [(0, 0), (1, 0), (1, 1)], T.PATH)
        assert tiles[1][1] == tiles[2][1] == tiles[3][1] == T.PATH
        assert tiles[3][2] == tiles[3][3] == T.PATH
        assert tiles[1][2] == T.WALL


class TestDrawing:
    """Turning tiles into coloured text."""

    def test_wide(self, make_maze: MakeMaze) -> None:
        """Full-size tiles are two spaces wide, with IN and EX labels."""
        renderer = AMazeIngRenderer()
        renderer.show(corridor(make_maze))
        lines = renderer.render().plain.split("\n")
        assert len(lines) == drawing_height(1, compact=False)
        assert all(len(line) == drawing_width(3, compact=False)
                   for line in lines)
        assert lines[1] == "  IN" + " " * 6 + "EX  "

    def test_compact(self, make_maze: MakeMaze) -> None:
        """Compact drawing packs two rows of tiles into each line of half
        blocks."""
        maze = make_maze(width=3, height=2, exit=(2, 1))
        renderer = AMazeIngRenderer()
        renderer.show(maze)
        renderer.fit(1, 1)
        assert renderer.compact
        lines = renderer.render().plain.split("\n")
        assert len(lines) == drawing_height(2, compact=True)
        assert all(line == "▀" * drawing_width(3, compact=True)
                   for line in lines)

    def test_compact_halves(self) -> None:
        """In a half block, the upper tile is the foreground and the lower the
        background."""
        tiles = [[T.WALL, T.OPEN], [T.OPEN, T.WALL], [T.WALL, T.WALL]]
        colours = {T.WALL: "#ffffff", T.OPEN: "#000000"}
        out = Text()
        AMazeIngRenderer._draw_halves(out, tiles, colours)
        assert out.plain == "▀▀\n▀▀"
        styles = [out.get_style_at_offset(CONSOLE, i)
                  for i in (0, 1, 3)]
        assert styles[0].color is not None
        assert styles[0].color.name == "#ffffff"
        assert styles[0].bgcolor is not None
        assert styles[0].bgcolor.name == "#000000"
        assert styles[1].color is not None
        assert styles[1].color.name == "#000000"
        # the last row has nothing below it
        assert styles[2].bgcolor is None

    def test_colours(self, make_maze: MakeMaze) -> None:
        """Walls and the logo take the chosen colours."""
        maze = make_maze(width=8, height=6, entry=(7, 0), exit=(7, 5))
        renderer = AMazeIngRenderer()
        renderer.show(maze)
        renderer.wall_colour = WALL_COLOURS[2].hex
        renderer.logo_colour = LOGO_COLOURS[1].hex
        text = renderer.render()
        backgrounds = {span.style.bgcolor.name.upper()
                       for span in text.spans
                       if isinstance(span.style, Style)
                       and span.style.bgcolor is not None}
        assert WALL_COLOURS[2].hex in backgrounds
        assert LOGO_COLOURS[1].hex in backgrounds
        assert UNTOUCHED.hex not in backgrounds
        assert CYAN.hex in backgrounds  # entry and exit

    def test_labels_are_dark_on_cyan(self, make_maze: MakeMaze) -> None:
        """The entry and exit labels are bold, dark on cyan."""
        renderer = AMazeIngRenderer()
        renderer.show(corridor(make_maze))
        text = renderer.render()
        label = text.get_style_at_offset(CONSOLE, text.plain.index("IN"))
        assert label.bold
        assert label.color is not None
        assert label.color.name.upper() == GROUND.hex
        assert label.bgcolor is not None
        assert label.bgcolor.name.upper() == CYAN.hex

    def test_head_is_gold(self, make_maze: MakeMaze) -> None:
        """The head of the trail is gold."""
        maze = make_maze(width=4, height=1, entry=(3, 0), exit=(2, 0))
        renderer = AMazeIngRenderer()
        renderer.show(maze, trail=[(0, 0)])
        text = renderer.render()
        line = text.plain.split("\n")[0]
        style = text.get_style_at_offset(CONSOLE, len(line) + 1 + 2)
        assert style.bgcolor is not None
        assert style.bgcolor.name.upper() == GOLD.hex


class TestSizing:
    """Choosing between full-size and compact tiles."""

    def test_full_size_until_fitted(self, make_maze: MakeMaze) -> None:
        """Until told how much room there is, the maze is drawn full size."""
        renderer = AMazeIngRenderer()
        renderer.show(make_maze(width=10, height=8))
        assert not renderer.compact
        assert renderer.fits
        assert renderer.styles.width is not None
        assert renderer.styles.width.value == drawing_width(10, False)
        assert renderer.styles.height is not None
        assert renderer.styles.height.value == drawing_height(8, False)

    def test_fit_before_show_is_remembered(self,
                                           make_maze: MakeMaze) -> None:
        """Room given before the maze is shown is used once it is."""
        renderer = AMazeIngRenderer()
        renderer.fit(5, 5)
        renderer.show(make_maze(width=10, height=8))
        assert renderer.compact

    @pytest.mark.parametrize(("room", "fits"), [
        ((42, 17), True),
        ((41, 17), False),
        ((42, 16), False),
        ((200, 200), True),
    ])
    def test_fit(self, make_maze: MakeMaze, room: tuple[int, int],
                 fits: bool) -> None:
        """Full-size tiles are used exactly when they fit."""
        renderer = AMazeIngRenderer()
        renderer.show(make_maze(width=10, height=8))
        renderer.fit(*room)
        assert renderer.fits is fits
        assert renderer.compact is not fits
        assert renderer.styles.width is not None
        assert renderer.styles.width.value == drawing_width(10, not fits)

    def test_expanded_keeps_full_size(self, make_maze: MakeMaze) -> None:
        """Expanded keeps full-size tiles even when they do not fit."""
        renderer = AMazeIngRenderer()
        renderer.show(make_maze(width=10, height=8))
        renderer.fit(5, 5)
        renderer.expanded = True
        assert not renderer.fits
        assert not renderer.compact
        renderer.expanded = False
        assert renderer.compact


class TestFrame:
    """The drawing exported for the MLX window."""

    def test_no_frame_before_show(self) -> None:
        """Before show(), there is nothing to export."""
        assert AMazeIngRenderer().frame() is None

    def test_same_tiles(self, make_maze: MakeMaze) -> None:
        """The frame holds the drawing's tiles, row by row, each as its
        position in Tile."""
        renderer = AMazeIngRenderer()
        renderer.show(corridor(make_maze), path=[(0, 0), (0, 1), (0, 2)])
        frame = renderer.frame()
        assert frame is not None
        assert (frame.width, frame.height) == (7, 3)
        order = list(Tile)
        assert [order[code] for code in frame.tiles] == \
            [tile for line in renderer._tiles() for tile in line]

    def test_colours(self, make_maze: MakeMaze) -> None:
        """Every Tile has its colour, as 0xRRGGBB, following the renderer's
        choices."""
        renderer = AMazeIngRenderer()
        renderer.show(corridor(make_maze))
        renderer.wall_colour = WALL_COLOURS[1].hex
        frame = renderer.frame()
        assert frame is not None
        assert len(frame.colours) == len(Tile)
        order = list(Tile)
        assert frame.colours[order.index(T.WALL)] == \
            int(WALL_COLOURS[1].hex[1:], 16)
        assert frame.colours[order.index(T.ENTRY)] == int(CYAN.hex[1:], 16)

    def test_hidden_path(self, make_maze: MakeMaze) -> None:
        """A hidden path is not in the frame either."""
        renderer = AMazeIngRenderer()
        renderer.show(corridor(make_maze), path=[(0, 0), (0, 1), (0, 2)])
        renderer.show_path = False
        frame = renderer.frame()
        assert frame is not None
        assert list(Tile).index(T.PATH) not in frame.tiles
