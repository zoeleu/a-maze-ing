"""The MLX window that mirrors the maze, driven through a fake MLX."""
from typing import Any, Callable

import pytest

from ui.mlx_window import (CLOSE_EVENT, ESCAPE, MAX_SCALE, Frame,
                           MazeWindow, WindowState, paint, scale_for)
from tests.ui.helpers import state_of

PADDING = 8  # extra bytes at the end of each image line, as MLX may add

# a 3 x 2 drawing in two colours
FRAME = Frame(width=3, height=2, tiles=bytes([0, 1, 0, 1, 1, 0]),
              colours=(0x112233, 0xAABBCC))
OTHER = FRAME._replace(tiles=bytes([1, 1, 1, 1, 1, 1]))
WIDER = Frame(width=4, height=2, tiles=bytes(8), colours=FRAME.colours)


class FakeMlx:
    """Stands in for the mlx package's Mlx: records the calls, keeps the
    images in memory, and runs queued events during mlx_loop."""

    SYNC_IMAGE_WRITABLE = 1

    def __init__(self, screen: tuple[int, int] = (1000, 800),
                 pixel_format: int = 0) -> None:
        """A display of *screen* pixels whose images use *pixel_format*."""
        self.screen = screen
        self.pixel_format = pixel_format
        self.calls: list[str] = []
        self.fail: set[str] = set()  # calls that return NULL
        self.loop_hook: Callable[[Any], None] | None = None
        self.hooks: dict[tuple[int, str], Callable[..., None]] = {}
        self.images: dict[int, tuple[bytearray, int]] = {}
        self.windows: dict[int, tuple[int, int, str]] = {}
        self.events: list[Callable[[], None]] = []
        self.next_id = 1

    def _new_id(self) -> int:
        """A fresh pointer value."""
        self.next_id += 1
        return self.next_id

    def mlx_init(self) -> int | None:
        """Connect, unless told to fail."""
        self.calls.append("init")
        return None if "init" in self.fail else 1

    def mlx_get_screen_size(self, ptr: int) -> tuple[int, int, int]:
        """The fake screen's size."""
        return (0, *self.screen)

    def mlx_loop_hook(self, ptr: int, function: Callable[[Any], None],
                      param: Any) -> None:
        """Keep the loop hook."""
        self.loop_hook = function

    def mlx_new_window(self, ptr: int, width: int, height: int,
                       title: str) -> int | None:
        """Open a window, unless told to fail."""
        self.calls.append(f"new_window {width}x{height}")
        if "window" in self.fail:
            return None
        window = self._new_id()
        self.windows[window] = (width, height, title)
        return window

    def mlx_new_image(self, ptr: int, width: int,
                      height: int) -> int | None:
        """Make an image with padded lines, unless told to fail."""
        if "image" in self.fail:
            return None
        image = self._new_id()
        size_line = width * 4 + PADDING
        self.images[image] = (bytearray(size_line * height), size_line)
        return image

    def mlx_get_data_addr(self,
                          image: int) -> tuple[memoryview, int, int, int]:
        """The image's pixels, as the real wrapper returns them."""
        data, size_line = self.images[image]
        return memoryview(data), 32, size_line, self.pixel_format

    def mlx_sync(self, ptr: int, command: int, image: int) -> None:
        """Record the wait for the image."""
        self.calls.append("sync")

    def mlx_put_image_to_window(self, ptr: int, window: int, image: int,
                                x: int, y: int) -> None:
        """Record the image being shown."""
        self.calls.append("put")

    def mlx_hook(self, window: int, event: int, mask: int,
                 function: Callable[[Any], None], param: Any) -> None:
        """Keep the close button's hook."""
        assert event == CLOSE_EVENT
        self.hooks[(window, "close")] = function

    def mlx_key_hook(self, window: int, function: Callable[[int, Any], None],
                     param: Any) -> None:
        """Keep the key hook."""
        self.hooks[(window, "key")] = function

    def mlx_expose_hook(self, window: int, function: Callable[[Any], None],
                        param: Any) -> None:
        """Keep the expose hook."""
        self.hooks[(window, "expose")] = function

    def mlx_loop(self, ptr: int) -> None:
        """One pass: run the queued events, then the loop hook."""
        self.calls.append("loop")
        events, self.events = self.events, []
        for event in events:
            event()
        assert self.loop_hook is not None
        self.loop_hook(None)

    def mlx_loop_exit(self, ptr: int) -> None:
        """Record the end of the pass."""
        self.calls.append("loop_exit")

    def mlx_destroy_image(self, ptr: int, image: int) -> None:
        """Forget the image."""
        del self.images[image]

    def mlx_destroy_window(self, ptr: int, window: int) -> None:
        """Forget the window."""
        del self.windows[window]
        self.calls.append("destroy_window")

    def mlx_release(self, ptr: int) -> None:
        """Record the disconnection."""
        self.calls.append("release")

    def click_close(self) -> None:
        """Queue a click on the only window's close button."""
        (window,) = self.windows
        self.events.append(lambda: self.hooks[(window, "close")](None))

    def press(self, key: int) -> None:
        """Queue a key press in the only window."""
        (window,) = self.windows
        self.events.append(lambda: self.hooks[(window, "key")](key, None))

    def pixel(self, x: int, y: int) -> bytes:
        """The 4 bytes of the only image's pixel at (*x*, *y*)."""
        (data, size_line), = self.images.values()
        offset = y * size_line + x * 4
        return bytes(data[offset:offset + 4])


def window_with(mlx: FakeMlx) -> MazeWindow:
    """A MazeWindow that loads *mlx*."""
    return MazeWindow("Test", mlx_loader=lambda: mlx)


class TestPaint:
    """Turning a frame into image pixels."""

    def test_each_tile_is_a_block_of_its_colour(self) -> None:
        """Every pixel of a tile has the tile's colour, as B, G, R, A."""
        data = bytearray((3 * 2 * 4 + PADDING) * 2 * 2)
        paint(FRAME, 2, data, 3 * 2 * 4 + PADDING, 0)
        size_line = 3 * 2 * 4 + PADDING
        dark, light = bytes((0x33, 0x22, 0x11, 0xFF)), \
            bytes((0xCC, 0xBB, 0xAA, 0xFF))
        assert data[0:size_line - PADDING] == dark * 2 + light * 2 + dark * 2
        # the second pixel row of the first tile row is the same line
        assert data[size_line:2 * size_line - PADDING] == \
            dark * 2 + light * 2 + dark * 2
        assert data[2 * size_line:2 * size_line + 8] == light * 2

    def test_line_padding_is_left_alone(self) -> None:
        """Bytes past the end of a line are not written."""
        size_line = 3 * 4 + PADDING
        data = bytearray(b"\x07" * size_line * 2)
        paint(FRAME, 1, data, size_line, 0)
        assert data[12:size_line] == b"\x07" * PADDING

    def test_argb_format(self) -> None:
        """With format 1, pixels are stored as A, R, G, B."""
        data = bytearray(3 * 4 * 2)
        paint(FRAME, 1, data, 3 * 4, 1)
        assert data[0:4] == bytes((0xFF, 0x11, 0x22, 0x33))


@pytest.mark.parametrize(("screen", "scale"), [
    ((1000, 800), MAX_SCALE),   # small maze: capped
    ((30, 30), 8),              # 80% of 30 is 24, over 3 tiles
    ((10, 10), 2),              # limited by the width: 8 // 3
    ((1, 1), 1),                # never below one pixel
])
def test_scale_for(screen: tuple[int, int], scale: int) -> None:
    """The window fits in 80% of the screen, between 1 and MAX_SCALE."""
    assert scale_for(FRAME, screen) == scale


class TestOpening:
    """Opening the window and drawing frames in it."""

    def test_nothing_happens_until_opened(self) -> None:
        """Creating the handle, or showing frames, does not load MLX."""
        loaded: list[bool] = []
        window = MazeWindow("Test", mlx_loader=lambda: loaded.append(True))
        window.show(FRAME)
        assert window.state is WindowState.HIDDEN
        assert loaded == []

    def test_open_makes_a_window_of_the_frame_size(self) -> None:
        """open() connects, opens a window scaled to the screen, and draws
        the frame in it."""
        mlx = FakeMlx(screen=(30, 30))
        window = window_with(mlx)
        window.open(FRAME)
        assert window.state is WindowState.OPEN
        assert mlx.calls == ["init", "new_window 24x16", "put"]
        (title,) = [title for _, _, title in mlx.windows.values()]
        assert title == "Test"
        assert mlx.pixel(0, 0) == bytes((0x33, 0x22, 0x11, 0xFF))
        assert mlx.pixel(8, 0) == bytes((0xCC, 0xBB, 0xAA, 0xFF))

    def test_open_does_nothing_when_open(self) -> None:
        """An open window is not opened again."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        mlx.calls.clear()
        window.open(OTHER)
        assert mlx.calls == []

    def test_a_new_frame_is_drawn_once_the_image_is_free(self) -> None:
        """show() with a different frame waits for the image, then redraws
        it."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        mlx.calls.clear()
        window.show(OTHER)
        assert mlx.calls == ["sync", "put"]
        assert mlx.pixel(0, 0) == bytes((0xCC, 0xBB, 0xAA, 0xFF))

    def test_the_same_frame_is_not_drawn_again(self) -> None:
        """Showing the frame already drawn does nothing."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        mlx.calls.clear()
        window.show(FRAME)
        assert mlx.calls == []

    def test_a_new_size_opens_a_new_window(self) -> None:
        """A frame of another size replaces the window."""
        mlx = FakeMlx(screen=(40, 40))
        window = window_with(mlx)
        window.open(FRAME)
        window.show(WIDER)
        assert len(mlx.windows) == 1
        assert "destroy_window" in mlx.calls
        assert mlx.calls[-2] == "new_window 32x16"

    def test_expose_puts_the_image_back(self) -> None:
        """When the window must be redrawn, the image is put back."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        mlx.calls.clear()
        (handle,) = mlx.windows
        mlx.hooks[(handle, "expose")](None)
        assert mlx.calls == ["put"]


class TestPumpAndClose:
    """Handling the window's events, and closing it."""

    def test_pump_runs_one_pass(self) -> None:
        """pump() runs MLX's loop once, and the loop hook ends it."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        mlx.calls.clear()
        assert window.pump() is False
        assert mlx.calls == ["loop", "loop_exit"]

    def test_pump_does_nothing_without_a_window(self) -> None:
        """Nothing to pump before the window opens."""
        mlx = FakeMlx()
        assert window_with(mlx).pump() is False
        assert mlx.calls == []

    @pytest.mark.parametrize("close", ["button", "escape"])
    def test_the_user_closes_the_window(self, close: str) -> None:
        """The close button or Escape closes the window at the next pump,
        and new frames do not bring it back."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        if close == "button":
            mlx.click_close()
        else:
            mlx.press(ESCAPE)
        assert window.pump() is True
        assert window.state is WindowState.HIDDEN
        assert mlx.windows == {}
        window.show(OTHER)
        assert mlx.windows == {}

    def test_other_keys_do_not_close(self) -> None:
        """Only Escape closes the window."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        mlx.press(ord("q"))
        assert window.pump() is False
        assert window.state is WindowState.OPEN

    def test_open_again_after_closing(self) -> None:
        """A closed window can be opened again, reusing the connection."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        mlx.click_close()
        window.pump()
        window.open(OTHER)
        assert window.state is WindowState.OPEN
        assert mlx.pixel(0, 0) == bytes((0xCC, 0xBB, 0xAA, 0xFF))
        assert mlx.calls.count("init") == 1

    def test_hide_closes_the_window(self) -> None:
        """hide() closes the window; frames do not reopen it, open() does."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        window.hide()
        assert window.state is WindowState.HIDDEN
        assert mlx.windows == {}
        window.show(FRAME)
        assert mlx.windows == {}
        window.open(FRAME)
        assert state_of(window) is WindowState.OPEN
        assert len(mlx.windows) == 1

    def test_close_releases_the_display(self) -> None:
        """close() closes the window and disconnects, once."""
        mlx = FakeMlx()
        window = window_with(mlx)
        window.open(FRAME)
        window.close()
        window.close()
        assert mlx.windows == {}
        assert mlx.calls.count("release") == 1


class TestFailures:
    """When the window cannot be shown."""

    def test_mlx_not_installed(self) -> None:
        """A missing mlx package is reported, not raised."""
        def missing() -> Any:
            """Stand-in for load_mlx without the package."""
            raise ImportError("No module named 'mlx'")
        window = MazeWindow("Test", mlx_loader=missing)
        window.open(FRAME)
        assert window.state is WindowState.FAILED
        assert window.error is not None
        assert "mlx package is not installed" in window.error

    @pytest.mark.parametrize(("failing", "error"), [
        ("init", "cannot connect to the display"),
        ("window", "the window could not be created"),
        ("image", "the image could not be created"),
    ])
    def test_mlx_refuses(self, failing: str, error: str) -> None:
        """A NULL from MLX is reported, and nothing is left open."""
        mlx = FakeMlx()
        mlx.fail.add(failing)
        window = window_with(mlx)
        window.open(FRAME)
        assert window.state is WindowState.FAILED
        assert window.error == error
        assert mlx.windows == {}

    def test_open_tries_again_after_a_failure(self) -> None:
        """New frames do not retry a failed window; open() does, and can
        succeed."""
        mlx = FakeMlx()
        mlx.fail.add("window")
        window = window_with(mlx)
        window.open(FRAME)
        window.show(OTHER)
        assert mlx.calls.count("new_window 72x48") == 1
        mlx.fail.clear()
        window.open(FRAME)
        assert window.state is WindowState.OPEN
        assert window.error is None

    def test_hide_forgets_a_failure(self) -> None:
        """Once the window is not wanted, the failure is forgotten."""
        mlx = FakeMlx()
        mlx.fail.add("init")
        window = window_with(mlx)
        window.open(FRAME)
        window.hide()
        assert window.state is WindowState.HIDDEN
        assert window.error is None
