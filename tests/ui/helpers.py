"""Helpers for the tests that drive the Textual app."""
from typing import Any, Awaitable, Callable, Protocol

from rich.console import Console
from rich.text import Text
from textual.app import App
from textual.pilot import Pilot
from textual.widget import Widget
from textual.widgets import Label, Static

from ui import AMazeIngApp
from ui.mlx_window import Frame, MazeWindow, WindowState

Scenario = Callable[[Pilot[None]], Awaitable[None]]


class FakeMazeWindow:
    """Stands in for MazeWindow in the UI tests, so no real window opens;
    follows the same states and records what it was asked to do."""

    def __init__(self, title: str) -> None:
        """Start hidden, with nothing recorded."""
        self.title = title
        self.state = WindowState.HIDDEN
        self.error: str | None = None
        self.frames: list[Frame] = []
        self.closed = False
        self.close_on_next_pump = False

    def open(self, frame: Frame) -> None:
        """Open the window on *frame*, unless it is open already."""
        if self.state is not WindowState.OPEN:
            self.state = WindowState.OPEN
            self.error = None
            self.frames.append(frame)

    def show(self, frame: Frame) -> None:
        """Record *frame*, if the window is open."""
        if self.state is WindowState.OPEN:
            self.frames.append(frame)

    def hide(self) -> None:
        """Close the window, and forget any failure."""
        self.state = WindowState.HIDDEN
        self.error = None

    def pump(self) -> bool:
        """Close the window if the test asked for it, as if the user had."""
        if self.close_on_next_pump and self.state is WindowState.OPEN:
            self.close_on_next_pump = False
            self.hide()
            return True
        return False

    def close(self) -> None:
        """Close for good."""
        self.closed = True
        self.hide()


def fake_window(app: App[Any]) -> FakeMazeWindow:
    """The app's MLX window, which the tests replace with a fake."""
    assert isinstance(app, AMazeIngApp)
    window = app.maze_window
    assert isinstance(window, FakeMazeWindow)
    return window


class Drive(Protocol):
    """The type of the drive fixture."""

    def __call__(self, config_path: str, scenario: Scenario,
                 size: tuple[int, int] = ...) -> AMazeIngApp:
        """Run the app on *config_path*, play *scenario* and return the app."""
        ...


def plain(widget: Widget) -> str:
    """The text a Static or Label shows, without its styling."""
    assert isinstance(widget, (Static, Label))
    content = widget.content
    if isinstance(content, str):
        return content
    if isinstance(content, Text):
        return content.plain
    console = Console(width=80, color_system=None)
    with console.capture() as capture:
        console.print(content)
    return capture.get()


def state_of(window: MazeWindow | FakeMazeWindow) -> WindowState:
    """The window's state, read afresh: after an assert on it, mypy keeps
    the narrowed value and rejects asserting another one later."""
    return window.state
