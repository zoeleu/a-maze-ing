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

"""The Textual application: picks the screen to show, keeps the console
output the library prints while the UI owns the terminal, and mirrors the
maze in an MLX window when the terminal is too narrow for it."""
import sys
from pathlib import Path
from typing import Any

from textual import events, on
from textual.app import App
from textual.binding import Binding
from textual.screen import Screen

from .mlx_window import MazeWindow, WindowState
from .renderer import AMazeIngRenderer
from .screens.error import ErrorScreen, ProblemFound
from .screens.layout import MazeBody
from .screens.main import MainScreen
from .session import ConfigProblem, Session

# How often the MLX window's events are handled, per second
WINDOW_FPS = 30


class AMazeIngApp(App[None]):
    """Shows the maze built from a config file, or what is wrong with it."""

    CSS_PATH = "a_maze_ing.tcss"
    TITLE = "A-Maze-ing"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("w", "open_window", "Open window", key_display="W"),
        Binding("q", "quit", "Quit", key_display="Q"),
    ]

    def __init__(self, config_path: str) -> None:
        """Create the app for the config at *config_path*."""
        super().__init__()
        self.config_path = config_path
        self._printed: list[tuple[str, bool]] = []
        self.maze_window = MazeWindow(
            f"A-Maze-ing - {Path(config_path).name}")
        self._window_seen: tuple[bool, WindowState] | None = None

    def on_mount(self) -> None:
        """Hold back what the library prints, load the config, and start
        handling the MLX window's events."""
        self.begin_capture_print(self)
        self.set_interval(1 / WINDOW_FPS, self._pump_window)
        self.load()

    def _pump_window(self) -> None:
        """Handle the MLX window's events; if the user closed it, offer
        the button again."""
        if self.maze_window.pump():
            self.sync_window()

    def load(self) -> None:
        """Read the config and build a maze, or explain why that failed."""
        try:
            session = Session(self.config_path)
        except ConfigProblem as problem:
            self._show(ErrorScreen(problem))
        else:
            self._show(MainScreen(session))

    def _show(self, screen: Screen[None]) -> None:
        """Make *screen* the only one above the default screen."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen)

    def on_print(self, event: events.Print) -> None:
        """Keep printed text, to pass on to the console on exit."""
        self._printed.append((event.text, event.stderr))

    def on_problem_found(self, message: ProblemFound) -> None:
        """Show what is wrong with the config."""
        self._show(ErrorScreen(message.problem))

    def on_error_screen_reload(self, message: ErrorScreen.Reload) -> None:
        """Read the config again."""
        self.load()

    def _maze_body(self) -> MazeBody | None:
        """The current screen's MazeBody, if it shows a maze."""
        return next(iter(self.screen.query(MazeBody)), None)

    def _window_wanted(self) -> bool:
        """Whether the maze is too wide for the terminal, so the MLX
        window may show it."""
        body = self._maze_body()
        return body is not None and body.too_narrow

    @on(AMazeIngRenderer.Changed)
    @on(MazeBody.Changed)
    def sync_window(self) -> None:
        """Keep the MLX window, if the user opened it, in step with the
        current screen's drawing, close it once the maze fits again, and
        tell the screen how it is doing. Never opens it."""
        wanted = self._window_wanted()
        if not wanted:
            self.maze_window.hide()
        elif self.maze_window.state is WindowState.OPEN:
            frame = self.screen.query_one(AMazeIngRenderer).frame()
            if frame is not None:
                self.maze_window.show(frame)
        body = self._maze_body()
        if body is not None:
            body.set_window_state(self.maze_window.state,
                                  self.maze_window.error)
        # the W key depends on both; only refresh when they change, as this
        # runs for every frame of a replay
        seen = (wanted, self.maze_window.state)
        if seen != self._window_seen:
            self._window_seen = seen
            self.refresh_bindings()

    def check_action(self, action: str,
                     parameters: tuple[object, ...]) -> bool | None:
        """Offer W only when the maze does not fit and its window is not
        open."""
        if action == "open_window":
            return self._window_wanted() and \
                self.maze_window.state is not WindowState.OPEN
        return True

    def action_open_window(self) -> None:
        """Open the MLX window on the current drawing (W, or the notice's
        button)."""
        if not self._window_wanted():
            return
        frame = self.screen.query_one(AMazeIngRenderer).frame()
        if frame is not None:
            self.maze_window.open(frame)
        self.sync_window()

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the app, close the MLX window, then print what the library
        printed meanwhile.

        Each message is printed once, even if several mazes printed it.
        """
        try:
            super().run(*args, **kwargs)
        finally:
            self.maze_window.close()
        for stderr, stream in ((False, sys.stdout), (True, sys.stderr)):
            text = "".join(t for t, err in self._printed if err == stderr)
            for line in dict.fromkeys(text.splitlines()):
                print(line, file=stream)
