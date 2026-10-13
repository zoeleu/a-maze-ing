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

"""The dialog shown before building a maze that may not fit in memory."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class MemoryWarning(ModalScreen[bool]):
    """Warns that the maze may not fit in memory, and lets the user build
    it anyway or quit. Its result, given to the screen's callback, is True
    to build it.

    A modal screen covers the screen below and only its own keys work, so
    nothing else can happen until the user answers.
    """

    BINDINGS = [Binding("q,escape", "quit", "Quit", key_display="Q")]

    def __init__(self, warning: str) -> None:
        """Create the dialog, explaining the risk with *warning*."""
        super().__init__()
        self.warning = warning

    def compose(self) -> ComposeResult:
        """Lay out the warning and its two buttons."""
        with Vertical(id="memory-panel"):
            yield Static("This maze may not fit in memory",
                         id="memory-title")
            yield Static(self.warning, id="memory-detail")
            with Horizontal(id="memory-buttons"):
                yield Button("Accept the risk and build", id="accept",
                             variant="warning")
                yield Button("Quit", id="quit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Answer with the button pressed: build only on accept."""
        self.dismiss(event.button.id == "accept")

    def action_quit(self) -> None:
        """Answer no: Q and Esc quit, like the Quit button."""
        self.dismiss(False)
