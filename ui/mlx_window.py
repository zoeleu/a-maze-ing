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

"""A MiniLibX window that mirrors the maze drawing, for when the terminal
is too narrow to show it.

Everything runs in the interface's thread. mlx_loop() normally never
returns, so the window is driven one pass at a time instead: a loop hook
calls mlx_loop_exit() straight away, and pump() runs one such pass, which
handles the window's pending events (close button, Escape, expose). The app
opens the window when the user asks, calls pump() from a timer, and show()
whenever the drawing changes.

Nothing here imports Textual: frames carry plain tiles and colours.
"""
import importlib
from enum import Enum
from typing import Any, Callable, NamedTuple

# Window pixels per tile, at most: a small maze is not blown up to fill the
# screen
MAX_SCALE = 24
# Share of the screen the window may take, in each direction
SCREEN_SHARE = 0.8

ESCAPE = 0xFF1B  # keysym of the Escape key
CLOSE_EVENT = 33  # ClientMessage: the window manager's close button


class Frame(NamedTuple):
    """One drawing of the maze: *width* x *height* tiles, row by row, each
    tile an index into *colours* (0xRRGGBB)."""

    width: int
    height: int
    tiles: bytes
    colours: tuple[int, ...]


class WindowState(Enum):
    """Where a MazeWindow stands."""

    HIDDEN = "hidden"  # no window: never opened, or closed since
    OPEN = "open"
    FAILED = "failed"  # it could not be opened; see MazeWindow.error


def scale_for(frame: Frame, screen: tuple[int, int]) -> int:
    """Window pixels per tile, so the drawing fits in SCREEN_SHARE of the
    *screen*'s (width, height), between 1 and MAX_SCALE."""
    width, height = screen
    return max(1, min(MAX_SCALE,
                      int(width * SCREEN_SHARE) // frame.width,
                      int(height * SCREEN_SHARE) // frame.height))


def paint(frame: Frame, scale: int, data: Any, size_line: int,
          pixel_format: int) -> None:
    """Draw *frame* into an image's *data*, each tile *scale* pixels wide.

    *pixel_format* is MLX's: 0 stores pixels as B, G, R, A bytes, 1 as A, R,
    G, B. Each row of tiles is built once as a line of pixels, then copied
    down *scale* times, so the work in Python is per tile, not per pixel.
    """
    pixels = []
    for colour in frame.colours:
        red, green, blue = colour >> 16, (colour >> 8) & 0xFF, colour & 0xFF
        if pixel_format == 0:
            pixels.append(bytes((blue, green, red, 0xFF)))
        else:
            pixels.append(bytes((0xFF, red, green, blue)))
    blocks = [pixel * scale for pixel in pixels]
    for row in range(frame.height):
        start = row * frame.width
        line = b"".join(blocks[tile]
                        for tile in frame.tiles[start:start + frame.width])
        for dy in range(scale):
            offset = (row * scale + dy) * size_line
            data[offset:offset + len(line)] = line


def load_mlx() -> Any:
    """The MLX wrapper. Imported here, not at the top of the module: the
    package is only needed once a window is wanted."""
    return importlib.import_module("mlx").Mlx()


class MazeWindow:
    """An MLX window showing frames of the maze drawing.

    open() opens the window on a frame, show() draws a new frame in it if it
    is open, hide() closes it, and pump() must be called regularly while it
    is open. Nothing ever opens it but open().
    """

    def __init__(self, title: str,
                 mlx_loader: Callable[[], Any] = load_mlx) -> None:
        """Create the handle; MLX is not touched until a window is wanted.
        *mlx_loader* returns the MLX wrapper (tests pass a fake)."""
        self.title = title
        self.mlx_loader = mlx_loader
        self.state = WindowState.HIDDEN
        self.error: str | None = None
        self.mlx: Any = None
        self.ptr: Any = None  # the connection to the display
        self.window: Any = None
        self.image: Any = None
        self.size: tuple[int, int] | None = None  # the window's, in tiles
        self.scale = 1  # window pixels per tile
        self.screen = (0, 0)
        self._drawn: Frame | None = None  # last frame drawn
        self._close_requested = False

    def open(self, frame: Frame) -> None:
        """Open the window on *frame*, or try again after a failure. Does
        nothing if it is already open."""
        if self.state is not WindowState.OPEN:
            self._open(frame)

    def show(self, frame: Frame) -> None:
        """Draw *frame* in the window, if it is open."""
        if self.state is WindowState.OPEN and frame != self._drawn:
            self._draw(frame)

    def hide(self) -> None:
        """Close the window, if it is open, and forget any failure."""
        self._destroy_window()
        self.state = WindowState.HIDDEN
        self.error = None

    def pump(self) -> bool:
        """Handle the window's pending events. Returns True if that closed
        the window."""
        if self.state is not WindowState.OPEN:
            return False
        self.mlx.mlx_loop(self.ptr)  # one pass: _on_loop exits right away
        if not self._close_requested:
            return False
        self.hide()
        return True

    def close(self) -> None:
        """Close the window and the connection to the display, for good."""
        self.hide()
        if self.ptr:
            self.mlx.mlx_release(self.ptr)
            self.ptr = None

    def _open(self, frame: Frame) -> None:
        """Connect to the display if needed, then open the window."""
        try:
            if not self.ptr:
                self._connect()
            self._draw(frame)
        except (ImportError, OSError, RuntimeError) as error:
            self._destroy_window()
            self.state = WindowState.FAILED
            self.error = str(error) or type(error).__name__
            return
        self.state = WindowState.OPEN
        self.error = None

    def _connect(self) -> None:
        """Load MLX and connect to the display."""
        try:
            self.mlx = self.mlx_loader()
        except ImportError:
            raise ImportError("the mlx package is not installed "
                              "(see make install)") from None
        self.ptr = self.mlx.mlx_init()
        if not self.ptr:
            raise RuntimeError("cannot connect to the display")
        _, width, height = self.mlx.mlx_get_screen_size(self.ptr)
        self.screen = (width, height)
        self.mlx.mlx_loop_hook(self.ptr, self._on_loop, None)

    def _draw(self, frame: Frame) -> None:
        """Draw *frame*, first making a window of its size if needed."""
        if self.size != (frame.width, frame.height):
            self._make_window(frame)
        else:
            # wait until the image is no longer being shown from
            self.mlx.mlx_sync(self.ptr, self.mlx.SYNC_IMAGE_WRITABLE,
                              self.image)
        data, _, size_line, pixel_format = \
            self.mlx.mlx_get_data_addr(self.image)
        paint(frame, self.scale, data, size_line, pixel_format)
        self.mlx.mlx_put_image_to_window(self.ptr, self.window, self.image,
                                         0, 0)
        self._drawn = frame

    def _make_window(self, frame: Frame) -> None:
        """(Re)create the window and its image for *frame*'s size."""
        self._destroy_window()
        self.scale = scale_for(frame, self.screen)
        width = frame.width * self.scale
        height = frame.height * self.scale
        self.window = self.mlx.mlx_new_window(self.ptr, width, height,
                                              self.title)
        if not self.window:
            raise RuntimeError("the window could not be created")
        self.image = self.mlx.mlx_new_image(self.ptr, width, height)
        if not self.image:
            raise RuntimeError("the image could not be created")
        self.size = (frame.width, frame.height)
        self._close_requested = False
        # hooks belong to a window, so each new window gets its own
        self.mlx.mlx_hook(self.window, CLOSE_EVENT, 0, self._on_close, None)
        self.mlx.mlx_key_hook(self.window, self._on_key, None)
        self.mlx.mlx_expose_hook(self.window, self._on_expose, None)

    def _destroy_window(self) -> None:
        """Destroy the image and the window, if there are any."""
        if self.image:
            self.mlx.mlx_destroy_image(self.ptr, self.image)
            self.image = None
        if self.window:
            self.mlx.mlx_destroy_window(self.ptr, self.window)
            self.window = None
        self.size = None
        self._drawn = None

    def _on_loop(self, _: Any) -> None:
        """MLX's loop hook: end the pass pump() started."""
        self.mlx.mlx_loop_exit(self.ptr)

    def _on_close(self, _: Any) -> None:
        """The window's close button was clicked."""
        self._close_requested = True

    def _on_key(self, key: int, _: Any) -> None:
        """Escape closes the window."""
        if key == ESCAPE:
            self._close_requested = True

    def _on_expose(self, _: Any) -> None:
        """Put the image back when the window has to be redrawn."""
        if self.image:
            self.mlx.mlx_put_image_to_window(self.ptr, self.window,
                                             self.image, 0, 0)
