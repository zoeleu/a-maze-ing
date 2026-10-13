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

"""The screen shown when the config stops a maze from being built."""
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Middle, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Static

from ..session import ConfigProblem
from .titlebar import TitleBar

INK = "#C7CCD1"
MUTED = "#8A939C"
GUTTER = "#5A626B"
RED = "#F25F5C"
RED_WASH = "#2A1A1C"  # red at 12% over the background
CONTEXT = 2  # lines shown around the offending one


class ProblemFound(Message):
    """Posted by a screen when the config stops a maze from being built."""

    def __init__(self, problem: ConfigProblem) -> None:
        """Carry *problem* to the app."""
        super().__init__()
        self.problem = problem


class ErrorScreen(Screen[None]):
    """Explains what is wrong with the config, pointing at the line when it
    can, and reloads it on request."""

    BINDINGS = [Binding("r", "reload", "Reload config", key_display="R")]

    class Reload(Message):
        """Posted when the user asks for the config to be read again."""

    def __init__(self, problem: ConfigProblem) -> None:
        """Create the screen for *problem*."""
        super().__init__()
        self.problem = problem

    def compose(self) -> ComposeResult:
        """Lay out the error panel in the middle of the screen."""
        problem = self.problem
        lines = problem.source()
        spot = problem.locate(lines)
        where = Path(problem.path).name
        # show line number if the problem can be located
        if spot is not None:
            where += f":L{spot[0] + 1}"

        yield TitleBar(problem.path)
        with Middle(id="error-body"):
            with Center():
                with Vertical(id="error-panel"):
                    yield Static(f"✗ {problem.title}", id="error-title")
                    yield Static(where, id="error-where")
                    if spot is None:
                        yield Static(problem.detail, id="error-detail")
                    else:
                        yield Static(self._excerpt(lines, *spot),
                                     id="excerpt")
                    yield Static(Text.assemble(
                        "Press ", ("R", INK),
                        " to reload the configuration."), id="error-hint")
        yield Footer()

    def on_mount(self) -> None:
        """Badge the title bar as an error."""
        self.query_one(TitleBar).show("ERROR", tone="red")

    def action_reload(self) -> None:
        """Ask the app to read the config again."""
        self.post_message(self.Reload())

    def _excerpt(self, lines: list[str], index: int, start: int,
                 end: int) -> Text:
        """The lines around *index*, with a caret under *start*:*end* and
        the problem's detail next to it."""
        # find CONTEXT lines around the offending line
        first = max(0, index - CONTEXT)
        last = min(len(lines), index + CONTEXT + 1)
        # digits of the last line number, for the gutter
        digits = len(str(last))
        # place the caret below the problematic section, add the detail next
        # to it
        caret = " " * start + "^" * (end - start) + " " + self.problem.detail
        # the widest row of the excerpt, gutter included: the offending
        # line is padded to it so its red background spans the whole block
        width = max(len(line) for line in lines[first:last] + [caret])
        width += digits + 5

        rows: list[Text] = []
        for number in range(first, last):
            line = lines[number]
            label = str(number + 1).rjust(digits)
            if number != index:
                rows.append(Text.assemble((f"  {label} │ ", GUTTER), line))
                continue
            # highlight the offending line
            # the line gets red, a marker on the gutter,
            # with the wrong part in bold red
            row = Text.assemble(
                (f"› {label} │ ", RED), line[:start],
                # the caret line goes under it
                (line[start:end], f"bold {RED}"), line[end:])
            # pad with spaces so the red background covers the full width
            row.pad_right(width - len(row))
            row.stylize(f"on {RED_WASH}")
            rows.append(row)
            rows.append(Text.assemble(
                (" " * (digits + 2) + " │ ", GUTTER), (caret, RED)))
        return Text("\n").join(rows)
