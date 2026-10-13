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

"""The screen shown while a maze is built on a thread of its own, and how
that thread talks to the interface.

The threads only talk through app.call_from_thread(), which runs a function
on the interface's thread: Textual widgets must only be touched from there.
The build itself is started by AMazeIngApp.build().
"""
from typing import Any, Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, ProgressBar, Static

from mazegen import progress_callback
from ..session import describe


class BuildingScreen(Screen[None]):
    """How far the maze being built has got. Only the keys of the screen
    on top work, and the app's: no other build can start meanwhile, but Q
    still quits."""

    def __init__(self) -> None:
        """Create the screen, with no progress reported yet."""
        super().__init__()
        # the latest progress reported. It is kept because the build thread
        # starts at the same time as this screen, so its first report can
        # arrive before the screen has its widgets to show it on. Steps
        # like "writing" report only once: without this, they would be
        # lost, and the screen would show an old step until the end.
        self.latest: tuple[str, int, int] | None = None

    def compose(self) -> ComposeResult:
        """Lay out a panel with the step and a progress bar, and the
        keys."""
        with Vertical(id="building-panel"):
            yield Static("Building the maze", id="building-title")
            yield Static("starting...", id="building-step")
            # no total yet: the bar shows it is busy without a percentage
            yield ProgressBar(total=None, show_percentage=False)
        yield Footer()

    def show(self, step: str, done: int, total: int) -> None:
        """Show that *done* out of *total* of *step* is done; a total of 0
        means the step cannot tell how far it has got."""
        self.latest = (step, done, total)
        if self.is_mounted:
            self._draw()

    def on_mount(self) -> None:
        """Show the progress reported before the screen was drawn, if
        any."""
        self._draw()

    def _draw(self) -> None:
        """Bring the step and the bar up to date with the latest
        progress."""
        if self.latest is None:
            return
        step, done, total = self.latest
        self.query_one("#building-step", Static).update(
            describe(step, done, total))
        self.query_one(ProgressBar).update(total=total or None,
                                           progress=done)


def from_thread(app: App[Any], callback: Callable[..., object],
                *args: Any) -> None:
    """Run *callback* with *args* on the interface's thread, from the build
    thread, and wait for it, and for what it returns if it can be awaited.
    Does nothing if the app has stopped: the user quit while the maze was
    being built."""
    if not app.is_running:
        return
    # Textual is not thread-safe: its widgets must only be changed by the
    # interface's thread, or two threads could change one at the same time
    # and leave it half-updated. call_from_thread() hands *callback* to the
    # interface's thread, which runs it between its own tasks, and makes
    # this thread wait until it has.
    app.call_from_thread(callback, *args)


def progress_reporter(app: App[Any]) -> progress_callback:
    """A progress callback for a Session whose mazes are built off the
    interface's thread: it shows the progress on the BuildingScreen."""
    def show(step: str, done: int, total: int) -> None:
        """On the interface's thread: update the BuildingScreen, if it is
        the screen on top."""
        if isinstance(app.screen, BuildingScreen):
            app.screen.show(step, done, total)

    def report(step: str, done: int, total: int) -> None:
        """On the build thread: pass the progress to the interface's
        thread."""
        from_thread(app, show, step, done, total)
    return report
