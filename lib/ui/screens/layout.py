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

"""How the maze screens arrange the maze and the side panels in the space
they have.

The screens compose a MazeBody holding `#too-narrow`, `#maze-panel` (the
maze, inside `#maze-holder`, which centers it once stacked) and `#side` (the
panels). The body lays them out again whenever its own size changes.
"""
from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Static

from ..renderer import AMazeIngRenderer, drawing_width

# Sizes from the stylesheet, in terminal cells
PANEL_FRAME_WIDTH = 4  # #maze-panel's border and padding, left and right
PANEL_FRAME_HEIGHT = 2  # #maze-panel's border, top and bottom
GAP = 2  # #side's left margin
SIDE_WIDTH = 30  # #side's min-width
SCROLLBAR = 2  # kept free in case the maze still scrolls vertically

# Past this many times the terminal's width, the maze is not drawn at all
TOO_NARROW = 1.5

MUTED = "#8A939C"

# Keys for a maze that was shrunk to fit: show it full size anyway, and back
ZOOM_BINDINGS = [
    Binding("z", "expand", "Expand", key_display="Z"),
    Binding("z", "shrink", "Shrink", key_display="Z"),
]


def zoom_allowed(screen: Screen[None], action: str) -> bool | None:
    """Whether *screen* offers the expand or shrink *action* right now, or
    None if *action* is not one of them.

    They are only offered when full-size tiles do not fit and the maze is
    drawn at all.
    """
    if action not in ("expand", "shrink"):
        return None
    renderer = screen.query_one(AMazeIngRenderer)
    if renderer.fits or not screen.query_one("#maze-panel").display:
        return False
    return renderer.expanded == (action == "shrink")


class MazeBody(Horizontal):
    """The space between the title bar and the status line.

    The side panels sit beside the maze while the maze fits there, and move
    below it once it would have to scroll sideways. The maze uses full-size
    tiles when they fit in the space left to it, and compact ones otherwise.
    When even the compact maze is more than TOO_NARROW times the terminal's
    width, a notice replaces it.
    """

    def __init__(self, cols: int, rows: int) -> None:
        """Create the body for a maze of *cols* x *rows* cells."""
        super().__init__(id="body")
        self.cols = cols
        self.rows = rows

    def on_resize(self) -> None:
        """Lay the maze and the panels out for the new size."""
        # measured without scrollbars, so showing one does not flip the
        # layout back and forth
        #
        # this is the space the maze and side panels have
        width = self.outer_size.width - self.styles.gutter.width
        height = self.outer_size.height - self.styles.gutter.height

        # width needed if the maze is drawn in a compact way
        smallest = drawing_width(self.cols, compact=True)
        # beside is the space available for the maze when the side panels
        # are beside it
        beside = width - PANEL_FRAME_WIDTH - GAP - SIDE_WIDTH - SCROLLBAR
        # below is the space available for the maze when the side panels are
        # below it
        below = width - PANEL_FRAME_WIDTH - SCROLLBAR
        # stacked is True when the maze and side panels are stacked vertically
        # they should be stacked vertically when the maze would have to
        # scroll sideways to fit beside the side panels, or when the maze is
        # too narrow to be drawn at all
        stacked = smallest > beside
        too_narrow = smallest > TOO_NARROW * self.screen.size.width
        # the room available for the maze, either beside or below
        # the side panels
        room = below if stacked else beside

        # fit the maze to the room available, and stack the side panels if
        # needed
        self.query_one(AMazeIngRenderer).fit(
            room, height - PANEL_FRAME_HEIGHT)
        self.set_class(stacked, "-stacked")
        # adjust the side panel's width and visibility
        panel = self.query_one("#maze-panel")
        panel.styles.max_width = max(room, 0) + PANEL_FRAME_WIDTH
        panel.display = not too_narrow

        # show a notice if the terminal is too narrow
        notice = self.query_one("#too-narrow", Static)
        notice.display = too_narrow
        needed = self.screen.size.width - width + smallest \
            + PANEL_FRAME_WIDTH + SCROLLBAR
        notice.update(Text.assemble(
            ("Terminal too narrow", "bold"),
            (f"\nThe maze needs at least {needed} columns.", MUTED)))
        self.screen.refresh_bindings()  # whether expand / shrink apply
