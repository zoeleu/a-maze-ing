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

"""The list of generation algorithms, shared by the maze screens: it shows
which one built the maze, and a click on another rebuilds the maze with
it."""
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

# read from the module each time, so a changed list shows
from .. import session

GOLD = "#E8C547"
MUTED = "#8A939C"


class AlgorithmPicker(Static):
    """One line per algorithm, the selected one marked and in gold. Clicking
    a line posts AlgorithmPicker.Chosen; the screen does the rebuilding."""
    selected: int

    class Chosen(Message):
        """Posted when the user clicks an algorithm."""

        def __init__(self, index: int) -> None:
            """*index* is the clicked algorithm's place in
            session.ALGORITHMS."""
            super().__init__()
            self.index = index

    def __init__(self, selected: int) -> None:
        """Create the list with session.ALGORITHMS[*selected*] marked."""
        super().__init__(id="algorithms", classes="panel")
        self.tooltip = "Click an algorithm to rebuild the maze with it"
        self.select(selected)

    def select(self, selected: int) -> None:
        """Mark session.ALGORITHMS[*selected*] as the one in use."""
        self.selected = selected
        self.update(Text("\n").join(
            Text(f"▸ {name}" if index == selected else f"  {name}",
                 GOLD if index == selected else MUTED)
            for index, (name, _) in enumerate(session.ALGORITHMS)))

    def on_click(self, event: events.Click) -> None:
        """Post Chosen for the algorithm on the clicked line, unless it is
        the one already in use."""
        offset = event.get_content_offset(self)
        if offset is None:  # on the border
            return
        if 0 <= offset.y < len(session.ALGORITHMS) \
                and offset.y != self.selected:
            self.post_message(self.Chosen(offset.y))
