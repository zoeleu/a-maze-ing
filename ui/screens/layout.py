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

When the terminal is too narrow or too short to draw the maze at all, the
notice that replaces it offers to show the maze in an MLX window instead (see
ui/mlx_window.py), and says how that window is doing.
"""
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Static

from ..mlx_window import WindowState
from ..renderer import AMazeIngRenderer, drawing_height, drawing_width

if TYPE_CHECKING:
    # only for the type checker: the app imports this module
    from ..app import AMazeIngApp

# Sizes from the stylesheet, in terminal cells
PANEL_FRAME_WIDTH = 4  # #maze-panel's border and padding, left and right
PANEL_FRAME_HEIGHT = 2  # #maze-panel's border, top and bottom
GAP = 2  # #side's left margin
SIDE_WIDTH = 30  # #side's min-width
SCROLLBAR = 2  # kept free in case the maze still scrolls vertically

# Past this many times the terminal's width, the maze is not drawn at all
TOO_NARROW = 1.5
# Likewise for its height
TOO_SHORT = 1.5

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


class TooNarrowNotice(Vertical):
    """Replaces the maze when the terminal is too narrow or too short for
    it: says how many columns and rows it needs, and offers a button to open
    it in an MLX window, or says how that window is doing."""

    def compose(self) -> ComposeResult:
        """The explanation, and the button to open the window."""
        yield Static(id="too-narrow-text")
        yield Button("Open in a window (W)", id="open-window", compact=True,
                     action="app.open_window")

    def show_state(self, narrow: int | None, short: int | None,
                   state: WindowState, error: str | None) -> None:
        """Explain that the maze needs *narrow* columns and / or *short*
        rows (None when that dimension is fine), and offer the window
        according to its *state*, with *error* if it failed."""
        title = " and ".join(
            f"too {word}" for word, count in
            (("narrow", narrow), ("short", short)) if count is not None)
        needs = " and ".join(
            f"{count} {unit}" for count, unit in
            ((narrow, "columns"), (short, "rows")) if count is not None)
        text = Text.assemble(
            (f"Terminal {title}", "bold"),
            (f"\nThe maze needs at least {needs}.", MUTED))
        button = self.query_one(Button)
        if state is WindowState.OPEN:
            text.append("\n\nIt is shown in a separate window.")
        elif state is WindowState.FAILED:
            text.append(f"\n\nCould not open a window: {error}.")
            button.label = "Try again (W)"
        else:
            button.label = "Open in a window (W)"
        button.display = state is not WindowState.OPEN
        self.query_one("#too-narrow-text", Static).update(text)


class MazeBody(Horizontal):
    """The space between the title bar and the status line.

    The side panels sit beside the maze while the maze fits there, and move
    below it once it would have to scroll sideways. The maze uses full-size
    tiles when they fit in the space left to it, and compact ones otherwise.
    When even the compact maze is more than TOO_NARROW times the terminal's
    width (or height), a TooNarrowNotice replaces it, which offers the MLX
    window.
    """
    app: "AMazeIngApp"

    class Changed(Message):
        """Posted when the body was laid out again or removed, so the app
        can close the MLX window once the maze fits again."""

    def __init__(self, cols: int, rows: int) -> None:
        """Create the body for a maze of *cols* x *rows* cells."""
        super().__init__(id="body")
        self.cols = cols
        self.rows = rows
        self.too_narrow = False  # the terminal is too narrow for the maze
        self.too_short = False  # the terminal is too short for the maze
        self.window_state = WindowState.HIDDEN  # as the notice shows it
        self.window_error: str | None = None
        self._needed = 0  # terminal columns the maze needs
        self._needed_rows = 0  # terminal rows the maze needs

    @property
    def replaced(self) -> bool:
        """Whether the notice replaces the maze: the terminal is too narrow
        or too short to draw it."""
        return self.too_narrow or self.too_short

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
        # stacked is True when the maze and side panels are stacked
        # vertically, which happens when even the compact maze would have to
        # scroll sideways beside the side panels (always the case when the
        # terminal is too narrow to draw the maze at all)
        stacked = smallest > beside
        too_narrow = smallest > TOO_NARROW * self.screen.size.width
        # rows needed if the maze is drawn in a compact way
        shortest = drawing_height(self.rows, compact=True)
        too_short = shortest > TOO_SHORT * self.screen.size.height
        replaced = too_narrow or too_short
        # the room available for the maze, either beside or below
        # the side panels
        room = below if stacked else beside

        # fit the maze to the room available, and stack the side panels if
        # needed
        self.query_one(AMazeIngRenderer).fit(
            room, height - PANEL_FRAME_HEIGHT)
        self.set_class(stacked, "-stacked")
        # adjust the maze panel's width and visibility
        panel = self.query_one("#maze-panel")
        panel.styles.max_width = max(room, 0) + PANEL_FRAME_WIDTH
        panel.display = not replaced

        # show a notice if the terminal is too narrow
        self.too_narrow = too_narrow
        self.too_short = too_short
        self.query_one(TooNarrowNotice).display = replaced
        self._needed = self.screen.size.width - width + smallest \
            + PANEL_FRAME_WIDTH + SCROLLBAR
        self._needed_rows = self.screen.size.height - height + shortest \
            + PANEL_FRAME_HEIGHT
        self._update_notice()
        self.screen.refresh_bindings()  # whether expand / shrink apply
        # the app closes the window if the maze fits again; posted to it
        # directly, as the renderer does (see AMazeIngRenderer._changed)
        self.app.post_message(self.Changed())

    def on_unmount(self) -> None:
        """Let the app close the window if no maze is left to mirror."""
        self.app.post_message(self.Changed())

    def set_window_state(self, state: WindowState,
                         error: str | None) -> None:
        """Have the notice show the MLX window's *state*."""
        if (state, error) != (self.window_state, self.window_error):
            self.window_state, self.window_error = state, error
            self._update_notice()

    def _update_notice(self) -> None:
        """Bring the notice up to date."""
        self.query_one(TooNarrowNotice).show_state(
            self._needed if self.too_narrow else None,
            self._needed_rows if self.too_short else None,
            self.window_state, self.window_error)
