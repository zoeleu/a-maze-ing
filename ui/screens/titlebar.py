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

"""The bar across the top of every screen."""
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label

TONES = ("gold", "cyan", "red")


class TitleBar(Horizontal):
    """Shows the app name, the config file, the maze's size and seed, and a
    badge for what the screen is doing."""

    def __init__(self, config_path: str) -> None:
        """Create the bar for the config at *config_path*."""
        super().__init__()
        self.config_path = config_path

    def compose(self) -> ComposeResult:
        """Lay out the bar's labels, left to right."""
        yield Label("A-MAZE-ING", id="brand")
        yield Label(Path(self.config_path).name, id="source")
        yield Label(id="spacer")
        yield Label(id="dims")
        yield Label(id="seed")
        yield Label(id="badge")

    def show(self, badge: str, tone: str = "gold", dims: str = "",
             seed: str = "") -> None:
        """Update the bar. *tone* is one of TONES and colours the badge."""
        self.query_one("#dims", Label).update(dims)
        self.query_one("#seed", Label).update(f"seed {seed}" if seed else "")
        label = self.query_one("#badge", Label)
        label.update(badge)
        for name in TONES:
            label.set_class(name == tone, f"-{name}")
