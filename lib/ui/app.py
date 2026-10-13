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

"""The Textual application: picks the screen to show and keeps the
console output the library prints while the UI owns the terminal."""
import sys
from typing import Any

from textual import events
from textual.app import App
from textual.binding import Binding
from textual.screen import Screen

from .screens.error import ErrorScreen, ProblemFound
from .screens.main import MainScreen
from .session import ConfigProblem, Session


class AMazeIngApp(App[None]):
    """Shows the maze built from a config file, or what is wrong with it."""

    CSS_PATH = "a_maze_ing.tcss"
    TITLE = "A-Maze-ing"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [Binding("q", "quit", "Quit", key_display="Q")]

    def __init__(self, config_path: str) -> None:
        """Create the app for the config at *config_path*."""
        super().__init__()
        self.config_path = config_path
        self._printed: list[tuple[str, bool]] = []

    def on_mount(self) -> None:
        """Hold back what the library prints, then load the config."""
        self.begin_capture_print(self)
        self.load()

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

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the app, then print what the library printed meanwhile.

        Each message is printed once, even if several mazes printed it.
        """
        super().run(*args, **kwargs)
        for stderr, stream in ((False, sys.stdout), (True, sys.stderr)):
            text = "".join(t for t, err in self._printed if err == stderr)
            for line in dict.fromkeys(text.splitlines()):
                print(line, file=stream)
