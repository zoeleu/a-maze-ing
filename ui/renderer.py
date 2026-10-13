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

"""The widget that draws a maze, and the colours it can draw it in."""
from enum import Enum, auto
from itertools import groupby
from typing import NamedTuple

from rich.style import Style
from rich.text import Text
from textual.app import App
from textual.color import Color
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from mazegen import Cell, Direction, Maze
from .mlx_window import Frame
from .session import CLOSED


class Swatch(NamedTuple):
    """A colour the user can cycle to, with the name shown for it."""

    name: str
    hex: str


WALL_COLOURS = [
    Swatch("chalk", "#D8DEE4"), Swatch("amber", "#E0A43A"),
    Swatch("moss", "#7FB069"), Swatch("cyan", "#4FB3D9"),
    Swatch("rose", "#E87A90"), Swatch("steel", "#6F7E8E"),
]
LOGO_COLOURS = [
    Swatch("violet", "#B48EF0"), Swatch("coral", "#F25F5C"),
    Swatch("mint", "#59D9A4"), Swatch("gold", "#F2C14E"),
]

GROUND = Color.parse("#0E1013")
GOLD = Color.parse("#E8C547")
CYAN = Color.parse("#5BC0EB")
UNTOUCHED = Color.parse("#1B1F26")


def drawing_width(cols: int, compact: bool) -> int:
    """How many terminal columns a maze `cols` cells wide takes to draw."""
    return (2 * cols + 1) * (1 if compact else 2)


def drawing_height(rows: int, compact: bool) -> int:
    """How many terminal rows a maze `rows` cells tall takes to draw."""
    tiles = 2 * rows + 1
    return (tiles + 1) // 2 if compact else tiles


class Tile(Enum):
    """What one square of the drawing shows. A maze of R x C cells is drawn
    as (2R + 1) x (2C + 1) tiles: cells on odd rows and columns, with the
    walls between them on the even ones."""

    # auto() numbers the members for us; the values themselves are never
    # used
    WALL = auto()
    LOGO = auto()
    OPEN = auto()
    UNTOUCHED = auto()
    PATH = auto()
    TRAIL = auto()
    HEAD = auto()
    ENTRY = auto()
    EXIT = auto()


class AMazeIngRenderer(Widget):
    """Draws a maze with its 42 pattern, entry, exit and, optionally, the
    shortest path between them.

    For replays it can also dim the cells no passage reaches yet and
    highlight the trail being carved.
    """
    app: App[None]

    class Changed(Message):
        """Posted when what the renderer draws changed, so a copy of the
        drawing elsewhere (the MLX window) can follow."""

    DEFAULT_CSS = """
    AMazeIngRenderer {
        width: auto;
        height: auto;
    }
    """

    wall_colour = reactive(WALL_COLOURS[0].hex)
    logo_colour = reactive(LOGO_COLOURS[0].hex)
    show_path = reactive(True)
    # a tile is two columns by one row, or, when compact, one column by half
    # a row; terminal characters are about twice as tall as they are wide,
    # so both keep the tiles square
    compact = reactive(False)
    # full-size tiles even when they do not fit, so the maze scrolls
    expanded = reactive(False)

    def __init__(self, *, dim_untouched: bool = False,
                 id: str | None = None, classes: str | None = None) -> None:
        """Create an empty renderer; give it a maze with show()."""
        super().__init__(id=id, classes=classes)
        self.dim_untouched = dim_untouched
        self.maze: Maze | None = None
        self.path: list[Cell] = []
        self.trail: list[Cell] = []
        self._room: tuple[int, int] | None = None
        self.fits = True  # whether full-size tiles fit in the room

    def show(self, maze: Maze, path: list[Cell] | None = None,
             trail: list[Cell] | None = None) -> None:
        """Draw *maze*, with *path* from entry to exit and the *trail* being
        carved, whose last cell is drawn as its head."""
        self.maze = maze
        self.path = path or []
        self.trail = trail or []
        self._fit()
        self._size_to_drawing()
        self.refresh()
        self._changed()

    def _changed(self) -> None:
        """Tell the app the drawing changed; only once mounted, as nobody
        listens before that. Posted to the app directly: a message does not
        bubble past its sender, and the replay redraws from its screen's
        timer, so the screen is the sender and the app would never see it."""
        if self.is_mounted:
            self.app.post_message(self.Changed())

    def watch_wall_colour(self) -> None:
        """The walls changed colour."""
        self._changed()

    def watch_logo_colour(self) -> None:
        """The 42 pattern changed colour."""
        self._changed()

    def watch_show_path(self) -> None:
        """The path was shown or hidden."""
        self._changed()

    def frame(self) -> Frame | None:
        """The drawing as a Frame for the MLX window: the same tiles, each
        one its Tile's position in the enum, with their colours. None before
        show()."""
        if self.maze is None:
            return None
        tiles = self._tiles()
        colours = self._colours()
        order = list(Tile)
        code = {tile: index for index, tile in enumerate(order)}
        rgb = [Color.parse(colours[tile]).rgb for tile in order]
        return Frame(
            width=len(tiles[0]), height=len(tiles),
            tiles=bytes(code[tile] for line in tiles for tile in line),
            colours=tuple((r << 16) | (g << 8) | b for r, g, b in rgb))

    # called by MazeBody whenever its size changes, to pick the tile size
    # that fits
    def fit(self, width: int, height: int) -> None:
        """Use full-size tiles if the maze fits in *width* x *height*
        terminal cells that way, and compact ones otherwise."""
        self._room = (width, height)
        self._fit()

    def _fit(self) -> None:
        """Pick the tile size for the current maze and room."""
        # nothing to fit until show() gave a maze and fit() gave the room
        if self.maze is None or self._room is None:
            return
        width, height = self._room
        # check if the maze fits in the room with full-size tiles, and if not,
        # use compact tiles instead
        self.fits = drawing_width(self.maze.cols, False) <= width \
            and drawing_height(self.maze.rows, False) <= height
        # if the maze fits, use full-size tiles; if not, use compact ones
        # however, if the user manually expands the maze, we should
        # draw it with full-size tiles even if it does not fit and would
        # overflow
        self.compact = not self.fits and not self.expanded

    # called whenever expanded changes, to resize the widget to the new tile
    # size
    def watch_expanded(self) -> None:
        """Switch tile size now that the user chose one."""
        self._fit()

    # called whenever compact changes, to resize the widget to the new tile
    # size
    def watch_compact(self) -> None:
        """Resize to the drawing at its new tile size."""
        self._size_to_drawing()

    def _size_to_drawing(self) -> None:
        """Set the widget's size to the drawing's, in terminal cells.

        This goes through the styles rather than get_content_width(): Textual
        caches box models, and a style change is what reliably invalidates
        them when the tile size flips right after a new maze is shown.
        """
        # if the maze is None, this was called before show() was called
        if self.maze is None:
            return
        # set the widget's size to the drawing's, in terminal cells
        # this also refreshes the box model, clearing Textual's caching
        # of the previous size, so the new size is used for layout
        self.styles.width = drawing_width(self.maze.cols, self.compact)
        self.styles.height = drawing_height(self.maze.rows, self.compact)

    def render(self) -> Text:
        """Draw the maze at the current tile size."""
        # if the maze is None, this was called before show() was called
        # ignore and return early
        if self.maze is None:
            return Text()
        colours = self._colours()
        text = Text(no_wrap=True, end="")
        # choose drawing method, half cells or full cells
        if self.compact:
            self._draw_halves(text, self._tiles(), colours)
        else:
            self._draw_wide(text, self._tiles(), colours)
        return text

    def _colours(self) -> dict[Tile, str]:
        """The colour of each tile, as a hex string."""
        return {
            Tile.WALL: self.wall_colour,
            Tile.LOGO: self.logo_colour,
            Tile.OPEN: GROUND.hex,
            Tile.UNTOUCHED: UNTOUCHED.hex,
            Tile.PATH: GROUND.blend(GOLD, 0.4).hex,
            Tile.TRAIL: GROUND.blend(CYAN, 0.4).hex,
            Tile.HEAD: GOLD.hex,
            Tile.ENTRY: CYAN.hex,
            Tile.EXIT: CYAN.hex,
        }

    @staticmethod
    def _draw_wide(text: Text, tiles: list[list[Tile]],
                   colours: dict[Tile, str]) -> None:
        """One terminal row per row of tiles, each tile two columns wide,
        with the entry and exit labelled."""
        labels = {Tile.ENTRY: "IN", Tile.EXIT: "EX"}
        for number, line in enumerate(tiles):
            if number:
                text.append("\n")
            for tile, run in groupby(line):
                count = len(list(run))
                if tile in labels:
                    text.append(labels[tile] * count, Style(
                        color=GROUND.hex, bgcolor=colours[tile], bold=True))
                else:
                    text.append("  " * count, Style(bgcolor=colours[tile]))

    @staticmethod
    def _draw_halves(text: Text, tiles: list[list[Tile]],
                     colours: dict[Tile, str]) -> None:
        """Two rows of tiles per terminal row, using the upper half block:
        its foreground is the upper tile and its background the lower one."""
        # going in pairs of rows
        for number in range(0, len(tiles), 2):
            # new line for every row of tiles except the first
            if number:
                text.append("\n")
            # the upper row of tiles, and the lower one if it exists (last row
            # could be alone)
            upper = tiles[number]
            lower: list[Tile | None] = [None] * len(upper)
            # if there is a lower row, copy it into the list of lower tiles
            if number + 1 < len(tiles):
                lower = list(tiles[number + 1])
            # for each group of the same upper and lower tile
            # draw in the half blocks
            # groupby returns in this format:
            # given a string "aaabbaabccccaa", it returns
            # ('a', <iterator of 3 a's>), ('b', <iterator of 2 b's>),
            # ('a', <iterator of 2 a's>), ('b', <iterator of 1 b>),
            # ('c', <iterator of 4 c's>), ('a', <iterator of 2 a's>)
            # then, we get the length of the iterator to know how many
            # characters to draw, so the count (length of the second element
            # of the tuple) is the number of half blocks to draw.
            # in this string example, it will be something like this:
            # (chr, count): ('a',3),('b',2),('a',2),('b',1),('c',4),('a',2)
            # in the same principle, we get matching cells in the rows and draw
            # them together.
            for (top, bottom), run in groupby(zip(upper, lower)):
                count = len(list(run))
                # we only need the half cell character, because we can
                # manipulate the color to our favor.
                #
                #   top tile  bottom tile  foreground  background  looks like
                #   --------  -----------  ----------  ----------  ----------
                #   wall      open         wall        open        ▀
                #   open      wall         open        wall        ▄
                #   wall      wall         wall        wall        █
                #   open      open         open        open        (blank)
                #   wall      (none)       wall        none        ▀
                #
                # by simply manipulating the foreground and background colors,
                # we can draw every single combination of tiles!
                text.append("▀" * count, Style(
                    color=colours[top],
                    bgcolor=None if bottom is None else colours[bottom]))

    def _tiles(self) -> list[list[Tile]]:
        """Lay the maze out as tiles, then the path and trail over it."""
        maze = self.maze
        assert maze is not None  # type checker, maze will never be None here
        # maze will never be none because this is only called from render(),
        # and render returns early if maze is None

        # creates a grid of closed tiles, that will be opened up later
        tiles = [[Tile.WALL] * (2 * maze.cols + 1)
                 for _ in range(2 * maze.rows + 1)]
        # 2 * {rows, cols} + 1 because of the walls drawn between the cells

        # draw the maze's cells and walls, coloring the logo appropriately
        # iterate over every cell in the maze
        for row, col, walls in maze:
            cell = (row, col)
            top, left = 2 * row + 1, 2 * col + 1
            if maze.in_logo(cell):
                # the logo cell itself, in the logo colour
                tiles[top][left] = Tile.LOGO

                # joins the edges of the logo, drawing the wall between the
                # logo cells with the logo colour, not the wall colour
                for dr, dc in ((0, 1), (1, 0)):
                    if maze.in_logo((row + dr, col + dc)):
                        tiles[top + dr][left + dc] = Tile.LOGO

                # a logo cell never has an open passage
                continue

            # the cell itself, dimmed if replays asked for it and none of
            # its walls is down yet
            untouched = self.dim_untouched and walls == CLOSED
            tiles[top][left] = Tile.UNTOUCHED if untouched else Tile.OPEN

            # mark the open sides, tearing the wall open between the cells
            for side in (Direction.EAST, Direction.SOUTH):
                if maze.is_open(cell, side):
                    tiles[top + side.step[0]][left + side.step[1]] = Tile.OPEN

        # draws the path
        if self.show_path:
            self._lay(tiles, self.path, Tile.PATH)

        # draw the trail being carved, with the last cell as its head
        self._lay(tiles, self.trail, Tile.TRAIL)

        # draw the head of the trail when generating
        if self.trail:
            self._lay(tiles, self.trail[-1:], Tile.HEAD)

        # draw entry and exit
        entry, goal = maze.config.entry, maze.config.exit
        tiles[2 * entry[1] + 1][2 * entry[0] + 1] = Tile.ENTRY
        tiles[2 * goal[1] + 1][2 * goal[0] + 1] = Tile.EXIT

        return tiles

    @staticmethod
    def _lay(tiles: list[list[Tile]], cells: list[Cell], tile: Tile) -> None:
        """Mark a chain of adjacent cells, and the passages between them."""
        for index, (row, col) in enumerate(cells):
            # paint the cell's own tile
            tiles[2 * row + 1][2 * col + 1] = tile

            # from the second cell on,
            if index:
                # paint the passage from the previous cell to this one
                before_row, before_col = cells[index - 1]

                # the wall tile between two adjacent cells sits halfway
                # between theirs: ((2r + 1) + (2r' + 1)) / 2 = r + r' + 1,
                # and the same for columns
                tiles[row + before_row + 1][col + before_col + 1] = tile
